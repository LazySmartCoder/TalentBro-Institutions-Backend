"""Tests for the AI profile review that runs when a candidate saves their profile.

The interview that used to be the only gate is gone, so the review is advisory:
it reports and prunes, but it never blocks anybody. The rules worth pinning
down are:

* **When it runs.** Only when the candidate's own claims - skills and target
  roles - really moved. Re-saving the same list in a new order, or with different
  capitalisation, must not spend a model call.
* **The floors.** The reviewer's judgement is advisory. Every rule that actually
  protects a candidate is Python's: only names already on the profile can
  survive, at most half may be dropped, and one skill and one role always stay.
* **It cannot break the save.** An unreachable model, an unusable reply or a
  review that blows up mid-write must all leave the profile exactly as the
  candidate typed it.
* **No machine output.** It is a JSON-only call behind the save, so there is no
  path by which a candidate reads the reviewer's raw words.

Gemini is never called: ``_review_profile_claims`` is patched, so these tests are
about our rules, not the model's behaviour.
"""

from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from TalentBroIns import views
from TalentBroIns.models import (
    CandidateProfile,
    ClientProfile,
    Institution,
)

USER_MODEL = get_user_model()
NAMESPACE = 'TalentBroIns'


def url(name, **kwargs):
    return reverse(f'{NAMESPACE}:{name}', kwargs=kwargs)


def _institution(name, email_domain):
    owner = USER_MODEL.objects.create_user(
        email=f'owner@{email_domain}', username=f'owner-{email_domain}', password='pw',
    )
    return Institution.objects.create(
        user=owner,
        name=name,
        institution_type='College',
        email_domain=email_domain,
        address='1 College Road',
        city='Bengaluru',
        state='Karnataka',
        pin_code='560001',
        placement_department_name='Placement Cell',
        placement_office_email=f'placement@{email_domain}',
        approximate_student_strength=1000,
    )


def _staff(email, institution):
    user = USER_MODEL.objects.create_user(username=email, email=email, password='pw')
    ClientProfile.objects.create(user=user, institution=institution)
    return user


def _student(first_name, last_name, institution, **overrides):
    """A candidate whose profile is complete enough to pass the chat's own gate."""
    user = USER_MODEL.objects.create_user(
        username=f'{first_name}.{last_name}'.lower(),
        email=f'{first_name}.{last_name}@student.test'.lower(),
        password='pw',
        first_name=first_name,
        last_name=last_name,
    )
    fields = {
        'user': user,
        'college': institution,
        'department': 'CSE',
        'program': 'B.Tech',
        'start_year': 2024,
        'end_year': 2027,
        'cgpa': Decimal('8.00'),
        'mobile_number': '9876543210',
        'date_of_birth': date(2004, 7, 12),
        'gender': 'female',
        'linkedin_url': 'https://linkedin.com/in/test',
        'placement_status': 'not_started',
    }
    fields.update(overrides)
    return CandidateProfile.objects.create(**fields)


def _review(skills, roles, final_skills, final_roles, **extra):
    payload = {
        'summary': 'Solid on the backend side.',
        'skills': skills,
        'roles': roles,
        'final_skills': final_skills,
        'final_preferred_roles': final_roles,
        'additions': [],
    }
    payload.update(extra)
    return payload


def _entry(name, status='verified', reason='', evidence=''):
    return {'name': name, 'status': status, 'reason': reason, 'evidence': evidence}


class ProfileReviewOnSaveTests(TestCase):
    """When the review runs, and when it deliberately does not."""

    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.profile = _student(
            'Asha', 'Rao', self.institution,
            skills=['React', 'SQL'], preferred_roles=['Frontend Engineer'],
            projects=['Expense tracker'],
        )
        self.user = self.profile.user
        self.client.force_login(self.user)

    def _save(self, payload):
        return self.client.patch(url('auth-profile'), payload,
                                 content_type='application/json')

    def test_changing_the_skills_earns_a_review(self):
        with mock.patch.object(views, '_review_profile_claims', return_value=None) as call:
            self._save({'skills': ['React', 'SQL', 'Docker']})
        self.assertEqual(call.call_count, 1)

    def test_changing_the_target_roles_earns_a_review(self):
        with mock.patch.object(views, '_review_profile_claims', return_value=None) as call:
            self._save({'preferred_roles': ['Frontend Engineer', 'Backend Engineer']})
        self.assertEqual(call.call_count, 1)

    def test_saving_the_same_list_in_another_order_does_not(self):
        # Presentation is not a change of what the candidate claims, and a
        # drag-and-drop in the editor must not cost a model call.
        with mock.patch.object(views, '_review_profile_claims', return_value=None) as call:
            response = self._save({'skills': ['SQL', 'React']})
        self.assertEqual(call.call_count, 0)
        self.assertEqual(response.status_code, 200)

    def test_capitalisation_does_not_count_as_a_change(self):
        with mock.patch.object(views, '_review_profile_claims', return_value=None) as call:
            self._save({'skills': ['react', 'SQL']})
        self.assertEqual(call.call_count, 0)

    def test_editing_an_unrelated_field_does_not(self):
        with mock.patch.object(views, '_review_profile_claims', return_value=None) as call:
            self._save({'cgpa': 9.1})
        self.assertEqual(call.call_count, 0)

    def test_the_review_comes_back_on_the_response(self):
        # Three skills after the save and only one kept, so the floor puts one back.
        # The response says so rather than hiding it.
        review = _review(
            [_entry('React', evidence='Expense tracker'), _entry('SQL'),
             _entry('Docker', status='unbacked')],
            [_entry('Frontend Engineer', reason='matches the React work')],
            ['React'], ['Frontend Engineer'],
        )
        with mock.patch.object(views, '_review_profile_claims', return_value=review):
            body = self._save({'skills': ['React', 'SQL', 'Docker']}).json()
        self.assertIn('review', body)
        self.assertEqual(body['review']['summary'], 'Solid on the backend side.')
        self.assertEqual(body['review']['retained_by_floor'], ['SQL'])
        self.assertEqual(
            [entry['name'] for entry in body['review']['skills']],
            ['React', 'SQL', 'Docker'],
        )

    def test_no_review_key_when_nothing_was_reviewed(self):
        # Absent rather than null, so the client can tell "nothing to report" from
        # "reported nothing wrong".
        with mock.patch.object(views, '_review_profile_claims', return_value=None):
            body = self._save({'cgpa': 9.0}).json()
        self.assertNotIn('review', body)


class ProfileReviewCannotBreakTheSaveTests(TestCase):
    """The review is advisory. The candidate's save is not."""

    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.profile = _student(
            'Asha', 'Rao', self.institution,
            skills=['React', 'SQL'], preferred_roles=['Frontend Engineer'],
        )
        self.user = self.profile.user
        self.client.force_login(self.user)

    def _save(self, payload):
        return self.client.patch(url('auth-profile'), payload,
                                 content_type='application/json')

    def test_an_unreachable_model_leaves_the_profile_as_typed(self):
        with mock.patch.object(views, '_review_profile_claims', return_value=None):
            response = self._save({'skills': ['React', 'SQL', 'Docker']})
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.skills, ['React', 'SQL', 'Docker'])
        self.assertNotIn('review', response.json())

    def test_a_review_that_explodes_mid_write_is_rolled_back(self):
        with mock.patch.object(views, '_review_profile_claims', return_value={'x': 1}), \
                mock.patch.object(views, '_apply_profile_review',
                                  side_effect=RuntimeError('boom')):
            response = self._save({'skills': ['React', 'SQL', 'Docker']})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('review', response.json())
        # The typed skills are still there: a failed review must not cost the
        # candidate their save, nor leave the row in whatever state it reached.
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.skills, ['React', 'SQL', 'Docker'])

    def test_changing_the_claims_earns_the_review(self):
        with mock.patch.object(views, '_review_profile_claims', return_value=None) as reviewer:
            self._save({'skills': ['Rust', 'Go']})
        self.assertEqual(reviewer.call_count, 1)

    def test_saving_an_unrelated_field_earns_no_review(self):
        with mock.patch.object(views, '_review_profile_claims', return_value=None) as reviewer:
            self._save({'cgpa': 9.0})
        self.assertEqual(reviewer.call_count, 0)


class ProfileReviewFloorsTests(TestCase):
    """The rules that actually protect a candidate, in Python rather than prose."""

    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.profile = _student(
            'Asha', 'Rao', self.institution,
            skills=['React', 'SQL', 'Python', 'Docker'],
            preferred_roles=['Frontend Engineer', 'Backend Engineer'],
            projects=['Expense tracker'],
        )

    def apply(self, review):
        result = views._apply_profile_review(self.profile, review)
        self.profile.refresh_from_db()
        return result

    def test_a_passing_review_writes_the_vetted_profile_back(self):
        self.apply(_review(
            [_entry('React', evidence='Expense tracker'), _entry('SQL')],
            [_entry('Frontend Engineer')],
            ['React', 'SQL'], ['Frontend Engineer'],
        ))
        self.assertEqual(self.profile.skills, ['React', 'SQL'])
        self.assertEqual(self.profile.preferred_roles, ['Frontend Engineer'])

    def test_the_reviewer_cannot_add_a_claim_that_was_not_on_the_profile(self):
        self.apply(_review(
            [_entry('React'), _entry('Rust')],
            [_entry('Frontend Engineer')],
            ['React', 'Rust'], ['Frontend Engineer'],
        ))
        self.assertNotIn('Rust', self.profile.skills)

    def test_no_more_than_half_the_skills_can_be_removed(self):
        result = self.apply(_review(
            [_entry('React', status='unbacked'), _entry('SQL', status='unbacked'),
             _entry('Python'), _entry('Docker')],
            [_entry('Frontend Engineer')],
            ['Python', 'Docker'], ['Frontend Engineer'],
        ))
        # Four skills, at most two go.
        self.assertEqual(len(self.profile.skills), 2)
        self.assertEqual(self.profile.skills, ['Python', 'Docker'])
        self.assertEqual(result['retained_by_floor'], [])

    def test_the_floor_puts_back_the_best_evidenced_of_what_was_rejected(self):
        # Five skills, so the floor is three. The reviewer only kept one, so two of
        # its rejections have to survive - and the ones with evidence behind them
        # are the ones worth keeping.
        self.profile.skills = ['React', 'SQL', 'Python', 'Docker', 'Kubernetes']
        self.profile.save(update_fields=['skills'])
        result = self.apply(_review(
            [
                _entry('React', evidence='Expense tracker'),
                _entry('SQL'),
                _entry('Python'),
                _entry('Docker', status='unbacked'),
                _entry('Kubernetes', status='unbacked'),
            ],
            [_entry('Frontend Engineer')],
            ['Kubernetes'], ['Frontend Engineer'],
        ))
        self.assertEqual(len(self.profile.skills), 3)
        self.assertIn('Kubernetes', self.profile.skills)
        self.assertIn('React', self.profile.skills)
        # React carried evidence, so it outranks SQL which was merely called
        # verified and both of the unbacked ones.
        self.assertEqual(sorted(result['retained_by_floor']), ['React', 'SQL'])

    def test_a_single_skill_always_survives(self):
        self.profile.skills = ['React']
        self.profile.save(update_fields=['skills'])
        self.apply(_review([], [_entry('Frontend Engineer')], [], ['Frontend Engineer']))
        self.assertEqual(self.profile.skills, ['React'])

    def test_at_least_one_role_always_survives(self):
        self.apply(_review(
            [_entry('React')], [_entry('Frontend Engineer', status='unbacked')],
            ['React'], [],
        ))
        self.assertEqual(self.profile.preferred_roles, ['Frontend Engineer'])

    def test_proof_is_appended_only_to_the_allowed_fields(self):
        self.apply(_review(
            [_entry('React', evidence='Expense tracker')], [_entry('Frontend Engineer')],
            ['React'], ['Frontend Engineer'],
            additions=[
                {'field': 'projects', 'value': 'Expense tracker (React) - built the auth flow'},
                {'field': 'skills', 'value': 'Kubernetes'},
                {'field': 'certifications', 'value': 'AWS Cloud Practitioner'},
                {'field': 'projects', 'value': 'Expense tracker (React) - built the auth flow'},
            ],
        ))
        self.assertEqual(self.profile.projects, [
            'Expense tracker',
            'Expense tracker (React) - built the auth flow',
        ])
        self.assertEqual(self.profile.certifications, ['AWS Cloud Practitioner'])
        self.assertNotIn('Kubernetes', self.profile.skills)

    def test_a_review_with_nothing_useful_in_it_changes_nothing(self):
        # An empty or nonsense reply must not empty somebody's profile.
        self.apply({})
        self.assertEqual(self.profile.skills,
                         ['React', 'SQL', 'Python', 'Docker'])
        self.assertEqual(self.profile.preferred_roles,
                         ['Frontend Engineer', 'Backend Engineer'])


class ProfileReviewCallTests(TestCase):
    """The shape of the call itself: JSON-only, and skipped when there is nothing
    on the profile to review."""

    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.profile = _student('Asha', 'Rao', self.institution, skills=['React'])
        self.user = self.profile.user

    def test_nothing_to_review_costs_no_call(self):
        self.profile.skills = []
        self.profile.preferred_roles = []
        self.profile.save(update_fields=['skills', 'preferred_roles'])
        with mock.patch.object(views, '_model_json') as model:
            self.assertIsNone(views._review_profile_claims(self.user, self.profile))
        self.assertEqual(model.call_count, 0)

    def test_the_reviewer_only_ever_sees_the_profile_slice(self):
        with mock.patch.object(views, '_model_json', return_value=None) as model:
            views._review_profile_claims(self.user, self.profile)
        messages, system_prompt = model.call_args.args[0], model.call_args.args[1]
        self.assertEqual(messages, [{'role': 'user', 'content': 'Review this profile.'}])
        self.assertNotIn(self.user.email, system_prompt)
        self.assertNotIn(self.user.password, system_prompt)
        self.assertIn('React', system_prompt)

    def test_the_call_is_charged_to_the_candidate(self):
        with mock.patch.object(views, '_model_json', return_value=None) as model:
            views._review_profile_claims(self.user, self.profile)
        self.assertEqual(model.call_args.kwargs.get('user'), self.user)

    def test_an_unusable_reply_reads_as_no_review(self):
        for reply in (None, 'a string', 42, []):
            with mock.patch.object(views, '_model_json', return_value=reply):
                self.assertIsNone(views._review_profile_claims(self.user, self.profile))
