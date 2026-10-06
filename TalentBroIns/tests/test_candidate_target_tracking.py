"""Tests for the candidate's own side of a target.

The officer's board already answers "how is my batch doing". What is easy to get
wrong here, and invisible to `manage.py check`, is the student's half:

* that only targets covering *this* student appear. The audience is a department
  plus an explicit M2M, so getting the union wrong either exposes another
  student's target or hides a real one.
* that the stored `client_targets` is a cache and not the record. It is re-derived
  on every read, so a practice row deleted after the fact cannot leave the profile
  claiming credit for work that no longer exists.
* that practice outside the target's window is not counted. Lifetime practice
  would let a student pass a target on work done before it was launched.
* that an unsolved question is not an accomplishment. The same rows that count
  towards the target are the rows named back to the student, so the sentence and
  the progress bar cannot disagree.
* that a student with no target is left alone rather than tracked against zero.
"""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from TalentBroIns.models import (
    APLRTraining,
    APLR_STATUS_ACTIVE,
    APLR_STATUS_SOLVED,
    CandidateProfile,
    ClientProfile,
    DSATraining,
    DSA_STATUS_ACTIVE,
    DSA_STATUS_SOLVED,
    GdTraining,
    Institution,
    MockInterview,
    MOCK_INTERVIEW_STATUS_COMPLETED,
    Students_Target,
)

USER_MODEL = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model()

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


def _student(email, institution, department='CSE'):
    user = USER_MODEL.objects.create_user(username=email, email=email, password='pw')
    return CandidateProfile.objects.create(
        user=user,
        college=institution,
        first_name=email.split('@')[0].title(),
        department=department,
    )


class CandidateTargetTrackingTests(TestCase):
    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.other = _institution('Beta Institute', 'beta.test')
        self.today = timezone.localdate()

        self.asha = _student('asha@alpha.test', self.institution, 'CSE')
        self.ece = _student('ece@alpha.test', self.institution, 'ECE')
        self.outsider = _student('zed@beta.test', self.other, 'CSE')

        self.target = Students_Target.objects.create(
            institution=self.institution,
            title='CSE DSA sprint',
            department='CSE',
            dsa_count=5,
            mock_interview_count=2,
            due_on=self.today + datetime.timedelta(days=14),
        )

    def _dsa(self, user, count, status=DSA_STATUS_SOLVED, days_ago=0):
        rows = DSATraining.objects.bulk_create([
            DSATraining(user=user, title='Stack', status=status, points_awarded=8)
            for _ in range(count)
        ])
        self._backdate(DSATraining, rows, days_ago)

    def _mock(self, user, count, days_ago=0):
        rows = MockInterview.objects.bulk_create([
            MockInterview(user=user, company_name='Acme', status=MOCK_INTERVIEW_STATUS_COMPLETED)
            for _ in range(count)
        ])
        self._backdate(MockInterview, rows, days_ago)

    def _backdate(self, model, rows, days_ago):
        if not rows:
            return
        when = timezone.now() - datetime.timedelta(days=days_ago)
        model.objects.filter(pk__in=[row.pk for row in rows]).update(created_at=when)

    def _read(self, profile=None):
        target_profile = profile or self.asha
        self.client.force_login(target_profile.user)
        response = self.client.get(url('my-training-targets'))
        self.assertEqual(response.status_code, 200)
        return response.json()

    # --- who sees what ----------------------------------------------------

    def test_a_student_sees_the_target_covering_their_department(self):
        body = self._read()

        self.assertTrue(body['has_targets'])
        self.assertEqual(len(body['targets']), 1)
        self.assertEqual(body['targets'][0]['target_id'], str(self.target.pk))

    def test_a_student_outside_the_department_sees_nothing(self):
        # ECE is not in the target's audience and was never attached to it, so
        # "no target covers me" is the honest answer and not a rendering failure.
        body = self._read(self.ece)

        self.assertFalse(body['has_targets'])
        self.assertEqual(body['targets'], [])

    def test_another_colleges_student_sees_nothing(self):
        body = self._read(self.outsider)

        self.assertFalse(body['has_targets'])

    def test_an_explicitly_attached_student_sees_a_target_with_no_department(self):
        individually = Students_Target.objects.create(
            institution=self.institution,
            title='One-off catch-up',
            dsa_count=3,
            due_on=self.today + datetime.timedelta(days=7),
        )
        individually.candidates.set([self.ece])

        body = self._read(self.ece)

        titles = [entry['title'] for entry in body['targets']]
        self.assertIn('One-off catch-up', titles)
        self.assertNotIn('CSE DSA sprint', titles)

    def test_a_student_who_joins_the_department_later_picks_the_target_up(self):
        # The audience is resolved live, so a target set before a student enrolled
        # still reaches them.
        late = _student('late@alpha.test', self.institution, 'CSE')

        body = self._read(late)

        self.assertTrue(body['has_targets'])

    def test_a_blank_department_does_not_catch_every_target(self):
        # An unfiled profile must not match a target that happens to have no
        # department set, or every unfiled student inherits every open target.
        unfiled = _student('unfiled@alpha.test', self.institution, '')
        no_department_target = Students_Target.objects.create(
            institution=self.institution,
            title='Everyone with no department',
            dsa_count=1,
            due_on=self.today + datetime.timedelta(days=7),
        )
        no_department_target.candidates.set([self.asha])

        body = self._read(unfiled)

        titles = [entry['title'] for entry in body['targets']]
        self.assertNotIn('Everyone with no department', titles)

    def test_institution_staff_cannot_use_the_student_endpoint(self):
        # The endpoint resolves the signed-in candidate's own profile, so an
        # officer has no candidate profile and gets nothing rather than a way to
        # read a student's progress by guessing an id.
        self.client.force_login(_staff('cell@alpha.test', self.institution))
        response = self.client.get(url('my-training-targets'))

        self.assertEqual(response.status_code, 404)

    def test_anonymous_gets_401(self):
        self.client.logout()

        self.assertEqual(self.client.get(url('my-training-targets')).status_code, 401)

    # --- progress ---------------------------------------------------------

    def test_progress_starts_at_zero(self):
        entry = self._read()['targets'][0]

        self.assertEqual(entry['self_training'], {'target': 5, 'done': 0, 'met': False})
        self.assertEqual(entry['mock_interview'], {'target': 2, 'done': 0, 'met': False})
        self.assertEqual(entry['percent'], 0)
        self.assertFalse(entry['met'])

    def test_solved_items_move_the_count_and_the_bar(self):
        self._dsa(self.asha.user, 3)

        entry = self._read()['targets'][0]

        self.assertEqual(entry['self_training']['done'], 3)
        self.assertEqual(entry['modules']['dsa'], {'target': 5, 'done': 3, 'met': False})
        self.assertEqual(entry['percent'], 60)
        self.assertFalse(entry['met'])

    def test_an_unsolved_question_is_not_progress(self):
        self._dsa(self.asha.user, 3, status=DSA_STATUS_ACTIVE)

        entry = self._read()['targets'][0]

        self.assertEqual(entry['self_training']['done'], 0)
        self.assertEqual(entry['accomplishments'], [])

    def test_practice_from_before_the_launch_is_not_counted(self):
        # The launch date is the start of the window, so a student cannot pass a
        # fresh target on a fortnight of work done beforehand.
        self._dsa(self.asha.user, 5, days_ago=30)

        entry = self._read()['targets'][0]

        self.assertEqual(entry['self_training']['done'], 0)

    def test_the_target_is_met_when_both_pillars_are_done(self):
        self._dsa(self.asha.user, 5)
        self._mock(self.asha.user, 2)

        entry = self._read()['targets'][0]

        self.assertTrue(entry['met'])
        self.assertEqual(entry['percent'], 100)
        self.assertTrue(entry['self_training']['met'])
        self.assertTrue(entry['mock_interview']['met'])

    def test_an_abandoned_mock_interview_does_not_count(self):
        self._mock(self.asha.user, 2)
        MockInterview.objects.create(user=self.asha.user, company_name='Acme', status='active')

        entry = self._read()['targets'][0]

        self.assertEqual(entry['mock_interview']['done'], 2)

    def test_the_bar_caps_at_one_hundred_for_an_overachiever(self):
        self._dsa(self.asha.user, 12)
        self._mock(self.asha.user, 9)

        entry = self._read()['targets'][0]

        self.assertEqual(entry['percent'], 100)
        self.assertEqual(entry['self_training']['done'], 5)
        self.assertEqual(entry['mock_interview']['done'], 2)

    def test_a_mock_only_target_needs_no_self_training_to_be_met(self):
        mock_only = Students_Target.objects.create(
            institution=self.institution,
            title='Mock interview month',
            department='CSE',
            mock_interview_count=1,
            due_on=self.today + datetime.timedelta(days=30),
        )
        self._mock(self.asha.user, 1)

        entry = next(
            item for item in self._read()['targets'] if item['target_id'] == str(mock_only.pk)
        )

        self.assertTrue(entry['met'])
        self.assertEqual(entry['percent'], 100)

    def test_a_group_discussion_target_is_tracked_too(self):
        gd = Students_Target.objects.create(
            institution=self.institution,
            title='GD drive',
            department='CSE',
            group_discussion_count=2,
            due_on=self.today + datetime.timedelta(days=10),
        )
        rows = GdTraining.objects.bulk_create([
            GdTraining(user=self.asha.user, topic='AI ethics', overall_score=80)
            for _ in range(2)
        ])
        self._backdate(GdTraining, rows, 0)

        entry = next(
            item for item in self._read()['targets'] if item['target_id'] == str(gd.pk)
        )

        self.assertEqual(entry['modules']['group_discussion']['done'], 2)
        self.assertTrue(entry['modules']['group_discussion']['met'])

    def test_two_targets_are_both_reported_independently(self):
        second = Students_Target.objects.create(
            institution=self.institution,
            title='APLR week',
            department='CSE',
            aplr_count=4,
            due_on=self.today + datetime.timedelta(days=5),
        )
        APLRTraining.objects.bulk_create([
            APLRTraining(user=self.asha.user, title='Sets', status=APLR_STATUS_SOLVED)
            for _ in range(4)
        ])

        entries = {entry['target_id']: entry for entry in self._read()['targets']}

        self.assertEqual(len(entries), 2)
        self.assertTrue(entries[str(second.pk)]['met'])
        self.assertFalse(entries[str(self.target.pk)]['met'])

    # --- accomplishments --------------------------------------------------

    def test_a_solved_item_is_named_back_with_its_score(self):
        self._dsa(self.asha.user, 2)

        accomplishments = self._read()['targets'][0]['accomplishments']

        self.assertEqual(len(accomplishments), 2)
        self.assertEqual(accomplishments[0]['module'], 'dsa')
        self.assertEqual(accomplishments[0]['label'], 'DSA (Data Structures & Algorithms)')
        self.assertIn('8 points', accomplishments[0]['detail'])

    def test_a_completed_mock_interview_is_named_with_the_company(self):
        self._mock(self.asha.user, 1)

        accomplishments = self._read()['targets'][0]['accomplishments']

        self.assertEqual(accomplishments[0]['module'], 'mock_interview')
        self.assertIn('Acme', accomplishments[0]['detail'])

    def test_accomplishments_come_out_newest_first(self):
        self._dsa(self.asha.user, 1, days_ago=5)
        self._dsa(self.asha.user, 1, days_ago=1)

        accomplishments = self._read()['targets'][0]['accomplishments']

        stamps = [item['at'] for item in accomplishments]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_the_accomplishment_list_is_capped(self):
        from TalentBroIns.views import TARGET_ACCOMPLISHMENT_TOTAL_LIMIT

        self._dsa(self.asha.user, TARGET_ACCOMPLISHMENT_TOTAL_LIMIT + 5)

        accomplishments = self._read()['targets'][0]['accomplishments']

        self.assertLessEqual(len(accomplishments), TARGET_ACCOMPLISHMENT_TOTAL_LIMIT)

    def test_work_outside_the_window_is_not_listed_as_an_accomplishment(self):
        self._dsa(self.asha.user, 2, days_ago=30)

        self.assertEqual(self._read()['targets'][0]['accomplishments'], [])

    # --- the stored field -------------------------------------------------

    def test_progress_is_stored_on_the_profile_row(self):
        self._dsa(self.asha.user, 2)

        self._read()
        self.asha.refresh_from_db()

        stored = self.asha.client_targets
        self.assertEqual(stored['version'], 1)
        self.assertEqual(stored['targets'][str(self.target.pk)]['self_training']['done'], 2)

    def test_the_field_is_empty_for_a_student_with_no_target(self):
        self.ece  # ECE, not in the audience.
        self._read(self.ece)

        self.ece.refresh_from_db()

        self.assertEqual(self.ece.client_targets, {'version': 1, 'targets': {}})

    def test_a_withdrawn_target_leaves_the_stored_field(self):
        self._dsa(self.asha.user, 2)
        self._read()
        self.asha.refresh_from_db()
        self.assertIn(str(self.target.pk), self.asha.client_targets['targets'])

        self.target.delete()
        self._read()
        self.asha.refresh_from_db()

        self.assertNotIn(str(self.target.pk), self.asha.client_targets['targets'])

    def test_deleted_practice_is_not_left_credited_on_the_profile(self):
        # The stored JSON is a cache. Re-reading after the practice rows are gone
        # must take the credit back, or the profile keeps claiming a target the
        # student can no longer evidence.
        self._dsa(self.asha.user, 3)
        self._read()
        self.asha.refresh_from_db()
        self.assertEqual(self.asha.client_targets['targets'][str(self.target.pk)]
                         ['self_training']['done'], 3)

        DSATraining.objects.all().delete()
        body = self._read()
        self.asha.refresh_from_db()

        self.assertEqual(body['targets'][0]['self_training']['done'], 0)
        self.assertEqual(
            self.asha.client_targets['targets'][str(self.target.pk)]['self_training']['done'], 0,
        )

    def test_the_model_helper_syncs_without_a_request(self):
        self._dsa(self.asha.user, 4)

        entries = self.asha.sync_client_targets()

        self.assertEqual(entries[str(self.target.pk)]['self_training']['done'], 4)

    def test_a_profile_with_no_user_account_is_cleared_rather_than_left_stale(self):
        self._dsa(self.asha.user, 3)
        self._read()
        self.asha.refresh_from_db()
        self.assertTrue(self.asha.client_targets['targets'])

        self.asha.user = None
        self.asha.sync_client_targets()
        self.asha.refresh_from_db()

        self.assertEqual(self.asha.client_targets, {})

    def test_the_model_defaults_to_an_empty_object(self):
        fresh = _student('fresh@alpha.test', self.institution, 'ECE')

        self.assertEqual(fresh.client_targets, {})

    def test_the_board_syncs_the_students_it_reports_on(self):
        # The officer's board and the student's own screen must not disagree, so
        # reading the board is enough to bring the stored field up to date.
        self._dsa(self.asha.user, 2)
        self.client.force_login(_staff('cell@alpha.test', self.institution))

        self.client.get(url('students-targets'))
        self.asha.refresh_from_db()

        self.assertEqual(
            self.asha.client_targets['targets'][str(self.target.pk)]['self_training']['done'], 2,
        )