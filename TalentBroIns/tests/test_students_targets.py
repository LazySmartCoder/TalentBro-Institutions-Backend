"""Tests for the launched training target endpoints.

Four things here are easy to get wrong and invisible to `manage.py check`:

* the scoping. The college comes from the signed-in user and the students are
  filtered to that college's own profiles, so a target cannot be aimed at another
  institution's batch by naming one in the body, and another college's target is
  invisible and undeletable.
* the audience. A target is scoped either by department or by named students, and
  both must resolve — a department target that quietly matched nobody would read
  as a passing target rather than as a broken one.
* the window. Progress is measured between the start and the due date, and the due
  day itself must count. Counting lifetime practice instead would let a student
  pass a target on work done before it was launched.
* what counts as done. The question-per-chat modules only count on `solved`, so a
  student cannot sit a target by opening questions and solving none of them.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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
    Institution,
    MockInterview,
    MOCK_INTERVIEW_STATUS_ACTIVE,
    MOCK_INTERVIEW_STATUS_COMPLETED,
    STUDENT_TARGET_MODULES,
    Students_Target,
)

USER_MODEL = get_user_model()

# TalentBroIns/urls.py sets app_name, so every pattern is namespaced.
NAMESPACE = 'TalentBroIns'


def url(name, **kwargs):
    return reverse(f'{NAMESPACE}:{name}', kwargs=kwargs)


def _institution(name, email_domain):
    """Institution rows require an owning user and a pile of non-blank fields."""
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


class StudentsTargetTests(TestCase):
    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.other = _institution('Beta Institute', 'beta.test')
        self.user = _staff('cell@alpha.test', self.institution)
        self.client.force_login(self.user)

        self.today = timezone.localdate()
        self.due = (self.today + datetime.timedelta(days=14)).isoformat()

        # One student with an account, so progress can be measured against them.
        self.asha = _student('asha@alpha.test', self.institution, 'CSE')
        # Two more CSE students with no account: they must still be part of the
        # audience, and must not break the progress rollup.
        self.no_account = [
            _student(f'cse{i}@alpha.test', self.institution, 'CSE') for i in range(2)
        ]
        self.ece = _student('ece@alpha.test', self.institution, 'ECE')

    def _launch(self, **overrides):
        body = {
            'title': 'CSE DSA sprint',
            'department': 'CSE',
            'modules': {'dsa': 5},
            'mock_interview_count': 2,
            'due_on': self.due,
        }
        body.update(overrides)
        return self.client.post(
            url('students-target-create'), body, content_type='application/json',
        )

    def _dsa(self, user, count, status=DSA_STATUS_SOLVED, days_ago=0):
        rows = DSATraining.objects.bulk_create([
            DSATraining(user=user, title='Stack', status=status) for _ in range(count)
        ])
        self._backdate(DSATraining, rows, days_ago)

    def _mock(self, user, count, status=MOCK_INTERVIEW_STATUS_COMPLETED, days_ago=0):
        rows = MockInterview.objects.bulk_create([
            MockInterview(user=user, company_name='Acme', status=status) for _ in range(count)
        ])
        self._backdate(MockInterview, rows, days_ago)

    @staticmethod
    def _backdate(model, rows, days_ago):
        """Move practice rows to `days_ago`.

        `created_at` is `auto_now_add`, so a stamp passed to the constructor is
        overwritten on insert and a test asking for "practice from three months ago"
        would silently get practice from now. It has to be written after the fact.

        The default of 0 days means "just now", which is inside the window of a
        target launched today — the common case, where a default of one day would
        quietly sit *before* the window opens and read as no practice at all.
        """
        if not rows:
            return
        when = timezone.now() - datetime.timedelta(days=days_ago)
        model.objects.filter(pk__in=[row.pk for row in rows]).update(created_at=when)

    # --- create ------------------------------------------------------------

    def test_create_saves_one_record_with_every_count(self):
        response = self._launch(modules={'dsa': 5, 'aplr': 3})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Students_Target.objects.count(), 1)
        target = Students_Target.objects.get()
        self.assertEqual(target.title, 'CSE DSA sprint')
        self.assertEqual(target.department, 'CSE')
        self.assertEqual(target.dsa_count, 5)
        self.assertEqual(target.aplr_count, 3)
        self.assertEqual(target.mock_interview_count, 2)
        self.assertEqual(target.due_on, self.today + datetime.timedelta(days=14))
        self.assertEqual(target.institution, self.institution)
        self.assertEqual(target.created_by, self.user)

    def test_one_target_is_one_record_however_many_students_it_covers(self):
        # The whole point of the department scope: three students, one commitment.
        self._launch()

        self.assertEqual(Students_Target.objects.count(), 1)
        self.assertEqual(Students_Target.objects.get().candidate_queryset().count(), 3)

    def test_create_reads_the_module_keys_the_catalogue_advertises(self):
        # The form is built from the `modules` catalogue the list endpoint sends, so
        # it POSTs back whatever `key` it was given. This is the body the real client
        # produces: every key it was shown, filled in. Reading the count map by column
        # name instead made every one of these land on zero and the server answered
        # "set at least one number" to a form the officer had filled in.
        catalogue = self.client.get(url('students-targets')).json()['modules']
        self.assertTrue(catalogue, 'the list endpoint must advertise a module catalogue')

        response = self._launch(modules={module['key']: 5 for module in catalogue})

        self.assertEqual(response.status_code, 201)
        target = Students_Target.objects.get()
        for _field, key, _label, _short in STUDENT_TARGET_MODULES:
            with self.subTest(module=key):
                self.assertEqual(getattr(target, f'{key}_count'), 5)
        self.assertEqual(target.self_training_count, 5 * len(STUDENT_TARGET_MODULES))

    def test_the_stored_row_is_read_back_under_the_same_keys(self):
        # The catalogue, the request and the response all agree on the keys, so the
        # grid the officer fills in is the grid that comes back filled in.
        self._launch(modules={'dsa': 4})

        board = self.client.get(url('students-targets')).json()

        # The catalogue the form is built from, the stored row and the target's
        # payload all speak the same keys, so a filled-in grid is a filled-in row.
        catalogue = {module['key'] for module in board['modules']}
        row = board['targets'][0]
        self.assertEqual(set(row['modules']), catalogue)
        self.assertEqual(row['modules']['dsa'], 4)
        self.assertEqual(row['self_training_count'], 4)

    def test_create_rejects_a_module_column_name_in_the_count_map(self):
        # Belt and braces on the same vocabulary rule: the column name is not a key
        # the API offers, so posting it is an error rather than a silent zero.
        response = self._launch(modules={'dsa_count': 5})

        self.assertEqual(response.status_code, 400)
        self.assertIn('Unknown module', response.json()['detail'])
        self.assertFalse(Students_Target.objects.exists())

    def test_create_rejects_an_unknown_module_key(self):
        # A typo must not be read as "that module was left at zero".
        response = self._launch(modules={'dsa': 5, 'writing': 2})

        self.assertEqual(response.status_code, 400)
        self.assertIn('writing', response.json()['detail'])
        self.assertFalse(Students_Target.objects.exists())

    def test_create_attaches_the_named_students(self):
        response = self._launch(
            department='',
            candidate_ids=[str(self.ece.candidate_id), str(self.asha.candidate_id)],
        )

        self.assertEqual(response.status_code, 201)
        target = Students_Target.objects.get()
        self.assertEqual(
            set(target.candidates.values_list('candidate_id', flat=True)),
            {self.ece.candidate_id, self.asha.candidate_id},
        )
        self.assertEqual(target.audience_label, '2 students')

    def test_create_combines_a_department_and_named_students(self):
        self._launch(candidate_ids=[str(self.ece.candidate_id)])

        target = Students_Target.objects.get()
        self.assertEqual(target.candidate_queryset().count(), 4)
        self.assertEqual(target.audience_label, 'CSE + 1')

    def test_create_rejects_a_target_with_no_audience(self):
        response = self._launch(department='', candidate_ids=[])

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Students_Target.objects.exists())

    def test_create_rejects_a_target_with_no_numbers(self):
        response = self._launch(modules={}, mock_interview_count=0)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Students_Target.objects.exists())

    def test_a_mock_only_target_is_allowed(self):
        # One mock interview a week is a real ask, and it needs no module counts.
        response = self._launch(modules={}, mock_interview_count=1)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Students_Target.objects.get().self_training_count, 0)

    def test_create_rejects_a_missing_due_date(self):
        response = self._launch(due_on='')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Students_Target.objects.exists())

    def test_create_rejects_an_unparseable_due_date(self):
        response = self._launch(due_on='next friday')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Students_Target.objects.exists())

    def test_create_rejects_a_due_date_before_the_start(self):
        response = self._launch(
            starts_on=(self.today + datetime.timedelta(days=7)).isoformat(),
            due_on=(self.today + datetime.timedelta(days=1)).isoformat(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Students_Target.objects.exists())

    def test_create_rejects_a_negative_count(self):
        response = self._launch(modules={'dsa': -1})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Students_Target.objects.exists())

    def test_create_rejects_a_count_above_the_cap(self):
        response = self._launch(modules={'dsa': 100000})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Students_Target.objects.exists())

    def test_create_rejects_a_fractional_count(self):
        # Not rounded to 7: a commitment is either an integer or it is a typo.
        response = self._launch(modules={'dsa': 7.9})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Students_Target.objects.exists())

    def test_create_rejects_a_non_numeric_count(self):
        response = self._launch(modules={'dsa': 'lots'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Students_Target.objects.exists())

    def test_create_accepts_a_count_sent_as_a_string(self):
        # A form input is a string until something parses it, so a numeric one is
        # a legitimate way to send the same number.
        response = self._launch(modules={'dsa': '7'})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Students_Target.objects.get().dsa_count, 7)

    def test_create_names_the_target_when_no_title_is_given(self):
        self._launch(title='')

        self.assertEqual(Students_Target.objects.get().title, 'CSE training target')

    def test_create_names_the_target_from_the_students_when_there_is_no_department(self):
        self._launch(title='', department='', candidate_ids=[str(self.ece.candidate_id)])

        self.assertEqual(Students_Target.objects.get().title, '1 student training target')

    def test_create_ignores_an_institution_named_in_the_body(self):
        self._launch(institution=str(self.other.pk))

        self.assertEqual(Students_Target.objects.get().institution, self.institution)

    def test_create_will_not_attach_another_colleges_student(self):
        stranger = _student('stranger@beta.test', self.other, 'CSE')

        response = self._launch(
            department='',
            candidate_ids=[str(self.asha.candidate_id), str(stranger.candidate_id)],
        )

        self.assertEqual(response.status_code, 201)
        target = Students_Target.objects.get()
        self.assertEqual(
            set(target.candidates.values_list('candidate_id', flat=True)),
            {self.asha.candidate_id},
        )

    def test_create_requires_authentication(self):
        self.client.logout()

        response = self._launch()

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Students_Target.objects.exists())

    # --- list --------------------------------------------------------------

    def test_list_returns_the_targets_with_their_numbers(self):
        self._launch()

        body = self.client.get(url('students-targets')).json()

        self.assertEqual(body['counts'], {'open': 1, 'closed': 0})
        row = body['targets'][0]
        self.assertEqual(row['title'], 'CSE DSA sprint')
        self.assertEqual(row['modules']['dsa'], 5)
        self.assertEqual(row['self_training_count'], 5)
        self.assertEqual(row['mock_interview_count'], 2)
        self.assertEqual(row['total_count'], 7)
        self.assertTrue(row['is_open'])

    def test_list_sends_the_module_catalogue_the_form_is_built_from(self):
        self._launch()

        body = self.client.get(url('students-targets')).json()

        catalogue = [module['key'] for module in body['modules']]
        self.assertEqual(catalogue, [
            'communication', 'group_discussion', 'aplr', 'basic_math',
            'english', 'situational', 'technical', 'dsa',
        ])
        # Every key the form can send must be a key the row reads back, or the
        # officer fills a field in and the board shows nothing.
        self.assertEqual(set(catalogue), set(body['targets'][0]['modules']))
        # And a module nobody asked about is present as a zero rather than absent.
        self.assertEqual(body['targets'][0]['modules']['aplr'], 0)

    def test_list_sends_the_departments_the_college_has_students_in(self):
        body = self.client.get(url('students-targets')).json()

        self.assertEqual(
            body['departments'],
            [
                {'name': 'CSE', 'students': 3},
                {'name': 'ECE', 'students': 1},
            ],
        )

    def test_list_ignores_a_blank_department(self):
        _student('nodept@alpha.test', self.institution, department='')

        body = self.client.get(url('students-targets')).json()

        self.assertEqual(
            [row['name'] for row in body['departments']], ['CSE', 'ECE'],
        )

    def test_list_puts_open_targets_first_and_closed_after(self):
        self._launch(title='Open one', due_on=(self.today + datetime.timedelta(days=5)).isoformat())
        self._launch(
            title='Closed one',
            due_on=(self.today - datetime.timedelta(days=2)).isoformat(),
        )

        body = self.client.get(url('students-targets')).json()

        self.assertEqual([row['title'] for row in body['targets']], ['Open one', 'Closed one'])
        self.assertEqual(body['counts'], {'open': 1, 'closed': 1})

    def test_a_target_due_today_is_still_open(self):
        self._launch(due_on=self.today.isoformat())

        body = self.client.get(url('students-targets')).json()

        self.assertTrue(body['targets'][0]['is_open'])
        self.assertEqual(body['targets'][0]['days_left'], 0)

    def test_a_target_due_yesterday_is_closed(self):
        self._launch(due_on=(self.today - datetime.timedelta(days=1)).isoformat())

        body = self.client.get(url('students-targets')).json()

        self.assertFalse(body['targets'][0]['is_open'])
        self.assertEqual(body['targets'][0]['days_left'], -1)

    def test_list_reports_how_far_the_students_have_got(self):
        self._launch(modules={'dsa': 2}, mock_interview_count=1)
        self._dsa(self.asha.user, 2)
        self._mock(self.asha.user, 1)

        body = self.client.get(url('students-targets')).json()
        progress = body['targets'][0]['progress']

        # Three CSE students, one of whom has an account and therefore the only one
        # whose practice can be counted.
        self.assertEqual(progress['students'], 3)
        self.assertEqual(progress['students_met'], 1)
        self.assertEqual(progress['self_training_done'], 2)
        self.assertEqual(progress['mock_done'], 1)
        self.assertEqual(progress['percent_met'], 33)

    def test_progress_is_null_when_nobody_is_assigned(self):
        # A target with no audience reads as "not started", not as "0% met".
        target = Students_Target.objects.create(
            institution=self.institution,
            title='Draft',
            dsa_count=5,
            due_on=self.today + datetime.timedelta(days=7),
        )

        body = self.client.get(url('students-targets')).json()

        self.assertIsNone(body['targets'][0]['progress']['percent_met'])

    def test_unresolved_dsa_work_does_not_count_towards_a_target(self):
        self._launch(modules={'dsa': 2}, mock_interview_count=0)
        # Two questions opened and abandoned is not two items of practice.
        self._dsa(self.asha.user, 2, status=DSA_STATUS_ACTIVE)

        progress = self.client.get(url('students-targets')).json()['targets'][0]['progress']

        self.assertEqual(progress['self_training_done'], 0)
        self.assertEqual(progress['students_met'], 0)

    def test_an_unfinished_mock_interview_does_not_count(self):
        self._launch(modules={}, mock_interview_count=1)
        self._mock(self.asha.user, 1, status=MOCK_INTERVIEW_STATUS_ACTIVE)

        progress = self.client.get(url('students-targets')).json()['targets'][0]['progress']

        self.assertEqual(progress['mock_done'], 0)
        self.assertEqual(progress['students_met'], 0)

    def test_progress_counts_from_the_day_the_target_was_launched(self):
        # A blank start date means "from today", not "from the deadline". Judging a
        # three-week target on the due day alone would report every student as
        # starting from zero a fortnight late.
        self._launch(modules={'dsa': 1}, mock_interview_count=0)
        self._dsa(self.asha.user, 1)

        progress = self.client.get(url('students-targets')).json()['targets'][0]['progress']

        self.assertEqual(progress['self_training_done'], 1)
        self.assertEqual(progress['students_met'], 1)

    def test_an_explicit_start_date_is_honoured(self):
        self._launch(
            modules={'dsa': 1},
            mock_interview_count=0,
            starts_on=(self.today - datetime.timedelta(days=7)).isoformat(),
        )
        self._dsa(self.asha.user, 1, days_ago=3)

        progress = self.client.get(url('students-targets')).json()['targets'][0]['progress']

        self.assertEqual(progress['self_training_done'], 1)

    def test_practice_from_before_the_target_started_does_not_count(self):
        self._launch(
            modules={'dsa': 1},
            mock_interview_count=0,
            starts_on=(self.today - datetime.timedelta(days=7)).isoformat(),
        )
        # Done three months ago, long before the window opened.
        self._dsa(self.asha.user, 1, days_ago=90)

        progress = self.client.get(url('students-targets')).json()['targets'][0]['progress']

        self.assertEqual(progress['self_training_done'], 0)

    def test_practice_on_the_due_date_itself_counts(self):
        # The window ends the day *after* the due date, so nothing done on the last
        # day is trimmed off by a time-of-day boundary.
        self._launch(
            modules={'dsa': 1}, mock_interview_count=0,
            due_on=self.today.isoformat(),
        )
        self._dsa(self.asha.user, 1, days_ago=0)

        progress = self.client.get(url('students-targets')).json()['targets'][0]['progress']

        self.assertEqual(progress['self_training_done'], 1)
        self.assertEqual(progress['students_met'], 1)

    def test_practice_after_the_due_date_does_not_count(self):
        # A closed target is history: work done after the deadline is not part of
        # how it was met, however much it would have helped at the time.
        self._launch(
            modules={'dsa': 1}, mock_interview_count=0,
            starts_on=(self.today - datetime.timedelta(days=10)).isoformat(),
            due_on=(self.today - datetime.timedelta(days=1)).isoformat(),
        )
        self._dsa(self.asha.user, 1, days_ago=0)

        progress = self.client.get(url('students-targets')).json()['targets'][0]['progress']

        self.assertEqual(progress['self_training_done'], 0)
        self.assertEqual(progress['students_met'], 0)

    def test_a_module_the_target_asks_nothing_about_is_not_counted(self):
        # APLR work must not be able to complete a DSA target.
        self._launch(modules={'dsa': 1}, mock_interview_count=0)
        APLRTraining.objects.create(user=self.asha.user, status=APLR_STATUS_SOLVED)

        progress = self.client.get(url('students-targets')).json()['targets'][0]['progress']

        self.assertEqual(progress['self_training_done'], 0)

    def test_list_hides_another_colleges_targets(self):
        Students_Target.objects.create(
            institution=self.other,
            title='Beta private target',
            dsa_count=5,
            due_on=self.today + datetime.timedelta(days=7),
        )

        body = self.client.get(url('students-targets')).json()

        self.assertEqual(body['targets'], [])
        self.assertEqual(body['counts'], {'open': 0, 'closed': 0})

    def test_list_is_empty_when_nothing_is_launched(self):
        body = self.client.get(url('students-targets')).json()

        self.assertEqual(body['targets'], [])
        self.assertEqual(body['counts'], {'open': 0, 'closed': 0})

    def test_list_requires_authentication(self):
        self.client.logout()

        self.assertEqual(self.client.get(url('students-targets')).status_code, 401)

    # --- delete ------------------------------------------------------------

    def test_delete_withdraws_the_target(self):
        self._launch()
        target = Students_Target.objects.get()

        response = self.client.delete(
            url('students-target-detail', target_id=target.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Students_Target.objects.exists())

    def test_delete_cannot_reach_another_colleges_target(self):
        target = Students_Target.objects.create(
            institution=self.other,
            title='Beta private target',
            dsa_count=5,
            due_on=self.today + datetime.timedelta(days=7),
        )

        response = self.client.delete(url('students-target-detail', target_id=target.pk))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Students_Target.objects.filter(pk=target.pk).exists())

    def test_delete_unknown_target_is_a_404(self):
        import uuid

        response = self.client.delete(
            url('students-target-detail', target_id=uuid.uuid4()),
        )

        self.assertEqual(response.status_code, 404)

    def test_delete_requires_authentication(self):
        self._launch()
        target = Students_Target.objects.get()
        self.client.logout()

        response = self.client.delete(url('students-target-detail', target_id=target.pk))

        self.assertEqual(response.status_code, 401)
        self.assertTrue(Students_Target.objects.filter(pk=target.pk).exists())

    # --- model -------------------------------------------------------------

    def test_model_rejects_a_due_date_before_the_start(self):
        # Objects.create() never runs full_clean(), which is why the view checks
        # this itself; this pins the model-level guard for admin and shell use.
        target = Students_Target(
            institution=self.institution,
            title='Backwards',
            dsa_count=1,
            starts_on=self.today,
            due_on=self.today - datetime.timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            target.full_clean()

    def test_model_rejects_a_target_asking_for_nothing(self):
        target = Students_Target(
            institution=self.institution,
            title='Empty',
            due_on=self.today + datetime.timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            target.full_clean()

    def test_a_blank_department_with_no_students_covers_nobody(self):
        # Not the whole college: an empty draft should be visible on the board,
        # not quietly read as campus-wide.
        target = Students_Target.objects.create(
            institution=self.institution,
            title='Draft',
            dsa_count=3,
            due_on=self.today + datetime.timedelta(days=1),
        )

        self.assertEqual(target.candidate_queryset().count(), 0)
        self.assertEqual(target.audience_label, 'No one yet')

    def test_a_department_target_picks_up_a_student_who_joins_later(self):
        # Resolved at read time rather than snapshotted, which is what "all of CSE
        # by the 30th" has to mean.
        target = Students_Target.objects.create(
            institution=self.institution,
            title='CSE sprint',
            department='cse',
            dsa_count=3,
            due_on=self.today + datetime.timedelta(days=1),
        )
        self.assertEqual(target.candidate_queryset().count(), 3)

        latecomer = _student('late@alpha.test', self.institution, 'CSE')

        self.assertIn(latecomer, target.candidate_queryset())

    def test_created_by_is_kept_when_the_author_is_deleted(self):
        self._launch()
        target = Students_Target.objects.get()

        self.user.delete()

        target.refresh_from_db()
        self.assertIsNone(target.created_by)

    def test_a_target_survives_the_students_it_names_being_deleted(self):
        self._launch(department='', candidate_ids=[str(self.ece.candidate_id)])
        target = Students_Target.objects.get()

        self.ece.delete()

        target.refresh_from_db()
        self.assertEqual(target.audience_label, 'No one yet')
