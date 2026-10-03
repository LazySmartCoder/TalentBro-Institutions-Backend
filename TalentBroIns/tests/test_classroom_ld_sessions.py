"""Tests for the classroom L&D session endpoints.

Two things here are easy to get wrong and invisible in `manage.py check`:

* the scoping. Every institution endpoint resolves the college from the signed-in
  user and ignores whatever the body names, so a session created by one college
  must never appear on - or be deletable from - another college's board.
* the split. The board shows "upcoming" and "done", and which list a session
  lands in is decided against its *end*, not its start. A class that is still
  running must not be reported as done.
"""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from TalentBroIns.models import ClassroomLDSession, ClientProfile, Institution

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


def _iso(moment):
    return moment.isoformat()


class ClassroomLDSessionTests(TestCase):
    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.other = _institution('Beta Institute', 'beta.test')
        self.user = _staff('cell@alpha.test', self.institution)
        self.client.force_login(self.user)

        self.now = timezone.now()

    def _create(self, starts_delta, ends_delta, **overrides):
        body = {
            'topic': 'Aptitude mock test',
            'agenda': 'Quant, reasoning, review',
            'venue': 'Seminar Hall B',
            'department': 'CSE',
            'faculty_name': 'Dr Rao',
            'starts_at': _iso(self.now + starts_delta),
            'ends_at': _iso(self.now + ends_delta),
        }
        body.update(overrides)
        return self.client.post(url('classroom-ld-session-create'), body, content_type='application/json')

    # --- create ------------------------------------------------------------

    def test_create_saves_every_field(self):
        response = self._create(timedelta(days=2), timedelta(days=2, hours=2))

        self.assertEqual(response.status_code, 201)
        session = ClassroomLDSession.objects.get()
        self.assertEqual(session.topic, 'Aptitude mock test')
        self.assertEqual(session.agenda, 'Quant, reasoning, review')
        self.assertEqual(session.venue, 'Seminar Hall B')
        self.assertEqual(session.department, 'CSE')
        self.assertEqual(session.faculty_name, 'Dr Rao')
        self.assertEqual(session.institution, self.institution)
        self.assertEqual(session.created_by, self.user)

    def test_create_tolerates_only_the_required_fields(self):
        # Venue, department and faculty are often undecided when a session is
        # first put on the calendar, so they must not block the row existing.
        response = self.client.post(
            url('classroom-ld-session-create'),
            {
                'topic': 'GD practice',
                'starts_at': _iso(self.now + timedelta(days=1)),
                'ends_at': _iso(self.now + timedelta(days=1, hours=1)),
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ClassroomLDSession.objects.get().venue, '')

    def test_create_rejects_a_missing_topic(self):
        response = self._create(timedelta(days=1), timedelta(days=1, hours=1), topic='')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClassroomLDSession.objects.exists())

    def test_create_rejects_an_end_before_the_start(self):
        response = self._create(timedelta(days=2), timedelta(days=1))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClassroomLDSession.objects.exists())

    def test_create_rejects_an_end_equal_to_the_start(self):
        # A zero-length class is a typo, not a session.
        response = self._create(timedelta(days=2), timedelta(days=2))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClassroomLDSession.objects.exists())

    def test_create_rejects_unparseable_times(self):
        response = self._create(timedelta(days=2), timedelta(days=2, hours=1), starts_at='next tuesday')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClassroomLDSession.objects.exists())

    def test_create_ignores_an_institution_named_in_the_body(self):
        # The college always comes from the session's own account.
        self._create(
            timedelta(days=1),
            timedelta(days=1, hours=1),
            institution=str(self.other.pk),
        )

        session = ClassroomLDSession.objects.get()
        self.assertEqual(session.institution, self.institution)

    def test_create_requires_authentication(self):
        self.client.logout()

        response = self._create(timedelta(days=1), timedelta(days=1, hours=1))

        self.assertEqual(response.status_code, 401)
        self.assertFalse(ClassroomLDSession.objects.exists())

    # --- list --------------------------------------------------------------

    def test_list_splits_upcoming_from_done(self):
        self._create(timedelta(days=3), timedelta(days=3, hours=1), topic='Later')
        self._create(timedelta(days=-5), timedelta(days=-5, hours=1), topic='Earlier')

        body = self.client.get(url('classroom-ld-sessions')).json()

        self.assertEqual(body['counts'], {'upcoming': 1, 'done': 1})
        self.assertEqual(body['upcoming'][0]['topic'], 'Later')
        self.assertEqual(body['done'][0]['topic'], 'Earlier')

    def test_list_orders_upcoming_soonest_first(self):
        self._create(timedelta(days=9), timedelta(days=9, hours=1), topic='Third')
        self._create(timedelta(days=1), timedelta(days=1, hours=1), topic='First')
        self._create(timedelta(days=4), timedelta(days=4, hours=1), topic='Second')

        body = self.client.get(url('classroom-ld-sessions')).json()

        self.assertEqual(
            [row['topic'] for row in body['upcoming']],
            ['First', 'Second', 'Third'],
        )

    def test_list_orders_done_most_recent_first(self):
        self._create(timedelta(days=-30), timedelta(days=-30, hours=1), topic='Ancient')
        self._create(timedelta(days=-2), timedelta(days=-2, hours=1), topic='Recent')

        body = self.client.get(url('classroom-ld-sessions')).json()

        self.assertEqual([row['topic'] for row in body['done']], ['Recent', 'Ancient'])

    def test_a_running_session_is_not_yet_done(self):
        # Started an hour ago, ends in an hour: still happening, so the officer
        # must not be told it is history.
        self._create(timedelta(hours=-1), timedelta(hours=1), topic='Running now')

        body = self.client.get(url('classroom-ld-sessions')).json()

        self.assertEqual(body['counts'], {'upcoming': 1, 'done': 0})
        self.assertFalse(body['upcoming'][0]['is_past'])

    def test_list_is_empty_when_nothing_is_scheduled(self):
        body = self.client.get(url('classroom-ld-sessions')).json()

        self.assertEqual(body, {
            'upcoming': [],
            'done': [],
            'counts': {'upcoming': 0, 'done': 0},
        })

    def test_list_hides_another_colleges_sessions(self):
        ClassroomLDSession.objects.create(
            institution=self.other,
            topic='Beta private session',
            starts_at=self.now + timedelta(days=1),
            ends_at=self.now + timedelta(days=1, hours=1),
        )

        body = self.client.get(url('classroom-ld-sessions')).json()

        self.assertEqual(body['counts'], {'upcoming': 0, 'done': 0})

    def test_list_reports_the_duration_in_minutes(self):
        self._create(timedelta(days=1), timedelta(days=1, minutes=90), topic='90 minutes')

        body = self.client.get(url('classroom-ld-sessions')).json()

        self.assertEqual(body['upcoming'][0]['duration_minutes'], 90)

    def test_list_requires_authentication(self):
        self.client.logout()

        self.assertEqual(self.client.get(url('classroom-ld-sessions')).status_code, 401)

    # --- delete ------------------------------------------------------------

    def test_delete_removes_the_session(self):
        self._create(timedelta(days=1), timedelta(days=1, hours=1))
        session = ClassroomLDSession.objects.get()

        response = self.client.delete(url('classroom-ld-session-detail', session_id=session.pk))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ClassroomLDSession.objects.exists())

    def test_delete_cannot_reach_another_colleges_session(self):
        session = ClassroomLDSession.objects.create(
            institution=self.other,
            topic='Beta private session',
            starts_at=self.now + timedelta(days=1),
            ends_at=self.now + timedelta(days=1, hours=1),
        )

        response = self.client.delete(url('classroom-ld-session-detail', session_id=session.pk))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(ClassroomLDSession.objects.filter(pk=session.pk).exists())

    def test_delete_unknown_session_is_a_404(self):
        import uuid

        response = self.client.delete(
            url('classroom-ld-session-detail', session_id=uuid.uuid4()),
        )

        self.assertEqual(response.status_code, 404)

    def test_delete_requires_authentication(self):
        self._create(timedelta(days=1), timedelta(days=1, hours=1))
        session = ClassroomLDSession.objects.get()
        self.client.logout()

        response = self.client.delete(url('classroom-ld-session-detail', session_id=session.pk))

        self.assertEqual(response.status_code, 401)
        self.assertTrue(ClassroomLDSession.objects.filter(pk=session.pk).exists())

    # --- model -------------------------------------------------------------

    def test_model_rejects_an_end_before_the_start(self):
        # Objects.create() never runs full_clean(), which is why the view checks
        # this itself; this pins the model-level guard for admin and shell use.
        from django.core.exceptions import ValidationError

        session = ClassroomLDSession(
            institution=self.institution,
            topic='Backwards',
            starts_at=self.now,
            ends_at=self.now - timedelta(hours=1),
        )

        with self.assertRaises(ValidationError):
            session.full_clean()

    def test_created_by_is_kept_when_the_author_is_deleted(self):
        self._create(timedelta(days=1), timedelta(days=1, hours=1))
        session = ClassroomLDSession.objects.get()

        self.user.delete()

        session.refresh_from_db()
        self.assertIsNone(session.created_by)