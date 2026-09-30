"""Tests for the paged self-training history endpoints.

These exist because the paged response shape and its whole-record summary/rollup
are built by shared helpers, and a mistake in those helpers surfaces only at
runtime as a 500 on a page the student actually uses. `manage.py check` cannot
see any of it.
"""

import datetime
from unittest import mock
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from TalentBroIns.models import (
    APLRTraining,
    BasicMathTraining,
    CandidateProfile,
    CommunicationTraining,
    DSATraining,
    EnglishTrainingSession,
    GdTraining,
    Institution,
    NOTIFICATION_SENDER_PLACEMENT_CELL,
    NOTIFICATION_SENDER_PLATFORM,
    Notification,
    NotificationReceipt,
    SituationalProblemSolvingTraining,
    TechnicalTraining,
)

USER_MODEL = get_user_model()

# TalentBroIns/urls.py sets app_name, so every pattern is namespaced.
NAMESPACE = 'TalentBroIns'

COMMUNICATION_LIST = 'communication-training-list'
ENGLISH_LIST = 'english-training-list'
APLR_LIST = 'aplr-list'
BASIC_MATH_LIST = 'basic-math-list'
DSA_LIST = 'dsa-list'
SITUATIONAL_LIST = 'situational-list'
TECHNICAL_LIST = 'technical-list'
GD_HISTORY = 'gd-history'

ALL_LIST_URL_NAMES = [
    COMMUNICATION_LIST, ENGLISH_LIST, APLR_LIST, BASIC_MATH_LIST,
    DSA_LIST, SITUATIONAL_LIST, TECHNICAL_LIST, GD_HISTORY,
]


def url(name):
    return reverse(f'{NAMESPACE}:{name}')


def _ago(days):
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)


class PagedHistoryShapeTests(TestCase):
    """Every history endpoint must page, and must never fall over."""

    def setUp(self):
        self.user = USER_MODEL.objects.create_user(
            username='student', email='student@example.com', password='pw'
        )
        self.client.force_login(self.user)

    def _seed_communication(self, count):
        """Communication sessions with a full, non-empty analysis.

        The text fields matter: they hold prose, and an earlier version of the
        summary averaged every analysis field, which raised ValueError and turned
        this endpoint into a 500 for any student with a real session.
        """
        sessions = []
        for i in range(count):
            sessions.append(
                CommunicationTraining.objects.create(
                    user=self.user,
                    title=f'Session {i}',
                    status='completed',
                    finalized_at=_ago(i),
                    transcript=[{'role': 'user', 'content': 'hello'}],
                    clarity=60 + (i % 20),
                    communication_score=55 + (i % 25),
                    recurring_mistakes='You said "alot" instead of "a lot".',
                    strengths='Clear opening and a steady pace.',
                    areas_for_improvement='Slow down at the end of answers.',
                    ai_recommendations='Practise the STAR structure.',
                    practice_priorities='Keep answers under two minutes.',
                )
            )
        return sessions

    def test_communication_history_returns_page_with_summary(self):
        self._seed_communication(3)

        response = self.client.get(url(COMMUNICATION_LIST))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body['sessions']), 3)
        self.assertEqual(body['total'], 3)
        self.assertFalse(body['has_more'])
        self.assertEqual(body['offset'], 0)
        self.assertEqual(body['limit'], 50)

        summary = body['summary']
        self.assertEqual(summary['analyzed_count'], 3)
        # Newest-first, so the first analysed row is the latest session and the
        # last is the very first one.
        self.assertEqual(summary['latest'], body['sessions'][0]['communication_score'])
        self.assertEqual(summary['first'], body['sessions'][-1]['communication_score'])
        self.assertIsNotNone(summary['last_practiced_at'])

        # Numeric dimensions are averaged; the overall score has its own field and
        # the prose fields must never appear in the averages map.
        self.assertIn('clarity', summary['averages'])
        self.assertNotIn('communication_score', summary['averages'])
        for text_field in (
            'recurring_mistakes', 'strengths', 'ai_recommendations', 'practice_priorities',
        ):
            self.assertNotIn(text_field, summary['averages'])

    def test_communication_history_summary_ignores_unanalysed_sessions(self):
        self._seed_communication(2)
        CommunicationTraining.objects.create(
            user=self.user, title='Abandoned', status='active',
        )

        summary = self.client.get(url(COMMUNICATION_LIST)).json()['summary']

        self.assertEqual(summary['analyzed_count'], 2)
        self.assertEqual(summary['overall'], summary['latest'])

    def test_communication_history_pagination_walks_the_whole_record(self):
        self._seed_communication(120)

        first = self.client.get(url(COMMUNICATION_LIST), {'limit': 50, 'offset': 0}).json()
        self.assertEqual(len(first['sessions']), 50)
        self.assertTrue(first['has_more'])
        self.assertEqual(first['total'], 120)

        last = self.client.get(url(COMMUNICATION_LIST), {'limit': 50, 'offset': 100}).json()
        self.assertEqual(len(last['sessions']), 20)
        self.assertFalse(last['has_more'])

        # Pages must not overlap or drop rows.
        seen = []
        for offset in (0, 50, 100):
            page = self.client.get(url(COMMUNICATION_LIST), {'limit': 50, 'offset': offset}).json()
            seen.extend(s['id'] for s in page['sessions'])
        self.assertEqual(len(seen), 120)
        self.assertEqual(len(set(seen)), 120)

    def test_history_limit_is_clamped_to_the_maximum(self):
        self._seed_communication(2)

        body = self.client.get(url(COMMUNICATION_LIST), {'limit': 100000}).json()

        self.assertEqual(body['limit'], 200)

    def test_history_rejects_a_negative_offset(self):
        self._seed_communication(2)

        body = self.client.get(url(COMMUNICATION_LIST), {'offset': -10}).json()

        self.assertEqual(body['offset'], 0)
        self.assertEqual(len(body['sessions']), 2)

    def test_history_ignores_garbage_paging_params(self):
        self._seed_communication(2)

        response = self.client.get(
            url(COMMUNICATION_LIST), {'limit': 'lots', 'offset': 'later'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['offset'], 0)

    def test_english_history_returns_page_with_summary(self):
        for i in range(3):
            EnglishTrainingSession.objects.create(
                user=self.user,
                title=f'Writing {i}',
                status='completed',
                finalized_at=_ago(i),
                transcript=[{'role': 'user', 'content': 'Dear team'}],
                clarity=70 + i,
                writing_score=60 + i,
                mistakes=[{'category': 'grammar'}],
                recurring_mistakes='Run-on sentence.',
                strengths='Clear structure.',
            )

        body = self.client.get(url(ENGLISH_LIST)).json()

        self.assertEqual(body['total'], 3)
        self.assertEqual(body['summary']['analyzed_count'], 3)
        self.assertEqual(body['summary']['total_mistakes'], 3)
        self.assertIn('clarity', body['summary']['averages'])
        self.assertNotIn('writing_score', body['summary']['averages'])
        self.assertNotIn('recurring_mistakes', body['summary']['averages'])

    def test_practice_modules_return_a_rollup_over_the_whole_record(self):
        for i in range(60):
            APLRTraining.objects.create(
                user=self.user, question=f'Q{i}', category='quant',
                status='solved' if i % 2 else 'gave_up',
                points_awarded=10, star_rating=3, created_at=_ago(i),
            )

        first = self.client.get(url(APLR_LIST), {'limit': 50}).json()

        self.assertEqual(len(first['sessions']), 50)
        self.assertTrue(first['has_more'])
        # The rollup covers every session, not just this page, so the stat chips
        # and category insights do not change as the reader scrolls.
        self.assertEqual(len(first['rollup']), 60)
        self.assertEqual(sum(row['points_awarded'] for row in first['rollup']), 600)

    def test_practice_rollup_is_present_on_every_page(self):
        for i in range(120):
            BasicMathTraining.objects.create(
                user=self.user, question=f'Q{i}', category='algebra',
                status='solved', points_awarded=5, star_rating=4, created_at=_ago(i),
            )

        second = self.client.get(url(BASIC_MATH_LIST), {'limit': 50, 'offset': 50}).json()

        self.assertEqual(len(second['sessions']), 50)
        self.assertEqual(len(second['rollup']), 120)

    def test_gd_history_rollup_backs_the_report_progress_line(self):
        for i in range(5):
            GdTraining.objects.create(
                user=self.user, topic=f'Topic {i}', overall_score=50 + i, created_at=_ago(i),
            )

        body = self.client.get(url(GD_HISTORY)).json()

        self.assertEqual(body['total'], 5)
        self.assertEqual(
            [row['overall_score'] for row in body['rollup']], [54, 53, 52, 51, 50]
        )

    def test_remaining_practice_endpoints_page(self):
        for model, name in (
            (DSATraining, DSA_LIST),
            (SituationalProblemSolvingTraining, SITUATIONAL_LIST),
            (TechnicalTraining, TECHNICAL_LIST),
        ):
            for i in range(3):
                model.objects.create(
                    user=self.user, question=f'Q{i}', category='c',
                    status='solved', points_awarded=1, star_rating=1, created_at=_ago(i),
                )

            body = self.client.get(url(name)).json()

            self.assertEqual(len(body['sessions']), 3, name)
            self.assertEqual(body['total'], 3, name)
            self.assertEqual(len(body['rollup']), 3, name)

    def test_history_endpoints_require_authentication(self):
        self.client.logout()

        for name in ALL_LIST_URL_NAMES:
            self.assertEqual(self.client.get(url(name)).status_code, 401, name)


class PagedNotificationsTests(TestCase):
    """The notifications inbox pages exactly like a history screen, and the two
    feed filters run on the server so a 50-row window never hides rows that live
    on a later page."""

    def setUp(self):
        self.user = USER_MODEL.objects.create_user(username='reader', password='pw')
        self.client.force_login(self.user)
        # The daily nudges are lazily topped up per-GET and would shift `total`,
        # so no-op them to keep every assertion deterministic.
        self._fill_patch = mock.patch('TalentBroIns.views._fill_due_nudges')

    def tearDown(self):
        self._fill_patch.stop()

    def _feed(self, **params):
        qs = urlencode(params)
        with self._fill_patch:
            return self.client.get(url('notifications-list') + (f'?{qs}' if qs else ''))

    def _broadcast(self, sender, title, *, pinned=False, at=None):
        row = Notification.objects.create(
            sender=sender, title=title, body=f'{title} body', pinned=pinned,
        )
        if at is not None:
            Notification.objects.filter(pk=row.pk).update(created_at=at)
        return row

    def test_feed_returns_a_paged_window_with_a_global_unread_count(self):
        base = datetime.datetime.now(datetime.timezone.utc)
        for i in range(120):
            self._broadcast(NOTIFICATION_SENDER_PLATFORM, f'Notice {i}',
                            at=base - datetime.timedelta(days=i))

        first = self._feed(limit=50, offset=0).json()
        self.assertEqual(len(first['notifications']), 50)
        self.assertEqual(first['total'], 120)
        self.assertTrue(first['has_more'])
        self.assertEqual(first['limit'], 50)
        self.assertEqual(first['offset'], 0)
        self.assertEqual(first['unread'], 120)

        last = self._feed(limit=50, offset=100).json()
        self.assertEqual(len(last['notifications']), 20)
        self.assertFalse(last['has_more'])

        seen = []
        for offset in (0, 50, 100):
            page = self._feed(limit=50, offset=offset).json()
            seen.extend(n['id'] for n in page['notifications'])
        self.assertEqual(len(seen), 120)
        self.assertEqual(len(set(seen)), 120)

    def test_pinned_broadcasts_sort_to_the_front_of_the_feed(self):
        base = datetime.datetime.now(datetime.timezone.utc)
        self._broadcast(NOTIFICATION_SENDER_PLATFORM, 'Newest', at=base)
        self._broadcast(NOTIFICATION_SENDER_PLATFORM, 'Pinned', pinned=True,
                        at=base - datetime.timedelta(days=2))
        self._broadcast(NOTIFICATION_SENDER_PLATFORM, 'Oldest',
                        at=base - datetime.timedelta(days=5))

        titles = [n['title'] for n in self._feed().json()['notifications']]

        self.assertEqual(titles, ['Pinned', 'Newest', 'Oldest'])

    def test_sender_and_unread_filters_apply_before_paging(self):
        staff = USER_MODEL.objects.create_user(username='cell-staff', password='pw')
        institution = Institution.objects.create(
            user=staff,
            name='Test College',
            institution_type='College',
            email_domain='testcollege.edu',
            address='1 College Road',
            city='City',
            state='State',
            pin_code='560001',
            placement_department_name='Placement Cell',
            placement_office_email='placement@testcollege.edu',
            approximate_student_strength=1000,
        )
        CandidateProfile.objects.create(user=self.user, college=institution)
        base = datetime.datetime.now(datetime.timezone.utc)
        for i in range(3):
            Notification.objects.create(
                sender=NOTIFICATION_SENDER_PLACEMENT_CELL,
                institution=institution,
                title=f'Cell {i}',
                body=f'Cell {i} body',
                pinned=False,
                created_at=base - datetime.timedelta(days=i),
            )
        for i in range(2):
            row = self._broadcast(NOTIFICATION_SENDER_PLATFORM, f'Platform {i}',
                                  at=base - datetime.timedelta(days=i))
            if i % 2:
                NotificationReceipt.objects.create(notification=row, user=self.user, read=True)

        cell = self._feed(sender='Placement Cell').json()
        self.assertEqual(cell['total'], 3)
        self.assertTrue(all(n['sender'] == 'Placement Cell' for n in cell['notifications']))
        # The badge count never shrinks to match the open filter.
        self.assertEqual(cell['unread'], 4)

        only_unread = self._feed(unread='true').json()
        self.assertEqual(only_unread['total'], 4)
        self.assertTrue(all(not n['read'] for n in only_unread['notifications']))

    def test_feed_clamps_limit_and_rejects_negative_offset(self):
        self._broadcast(NOTIFICATION_SENDER_PLATFORM, 'Hello')

        body = self._feed(limit=100000).json()
        self.assertEqual(body['limit'], 200)

        body = self._feed(offset=-10).json()
        self.assertEqual(body['offset'], 0)

    def test_feed_requires_authentication(self):
        self.client.logout()

        self.assertEqual(self.client.get(url('notifications-list')).status_code, 401)
