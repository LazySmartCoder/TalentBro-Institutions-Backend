import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import (
    CandidateProfile,
    ChatMessage,
    ChatSession,
    Institution,
    MockInterview,
    MockInterviewAnalysis,
    NOTIFICATION_SENDER_PLACEMENT_CELL,
    NOTIFICATION_SENDER_PLATFORM,
    Notification,
    NotificationReceipt,
    ROLE_INSTITUTION_STAFF,
    ROLE_STUDENT,
)
from .gemini_cost import record_cost_incurred, usage_cost_inr
from .views import (
    _nudge_message,
    _perf_components,
    _perf_question_module_score,
    _performance_components,
    _profile_ranks,
    _rank_map,
    _refresh_readiness_for_user,
    _serialize_components,
)


def _staff_account(name='tpo', email='tpo@test.com', password='pass12345'):
    user = User.objects.create_user(name, email, password)
    inst = Institution.objects.create(
        user=user,
        name='Test Institute',
        institution_type='College',
        email_domain='test.com',
        address='Test Address',
        city='Pune',
        state='Maharashtra',
        pin_code='411001',
        placement_department_name='Placement Office',
        placement_office_email='placements@test.com',
        approximate_student_strength=500,
    )
    return user, inst


def _student_account(inst, name='stu', email='stu@test.com', password='pass12345'):
    user = User.objects.create_user(name, email, password)
    CandidateProfile.objects.create(user=user, first_name='Test', last_name='Student', college=inst)
    return user


class NotificationModelTests(TestCase):
    def test_clean_requires_institution_for_placement_cell(self):
        n = Notification(sender=NOTIFICATION_SENDER_PLACEMENT_CELL, title='T', body='B')
        self.assertRaises(Exception, n.full_clean)

    def test_clean_rejects_institution_on_platform_broadcast(self):
        _, inst = _staff_account()
        n = Notification(
            sender=NOTIFICATION_SENDER_PLATFORM,
            institution=inst,
            title='T',
            body='B',
        )
        self.assertRaises(Exception, n.full_clean)


class NotificationApiTests(TestCase):
    def setUp(self):
        self.platform_user = User.objects.create_user(
            'platform', 'platform@test.com', 'pass12345', is_staff=True,
        )
        self.staff_user, self.inst = _staff_account()
        self.other_inst = Institution.objects.create(
            user=User.objects.create_user('tpo2', 'tpo2@test.com', 'pass12345'),
            name='Other Institute',
            institution_type='College',
            email_domain='other.com',
            address='A',
            city='Pune',
            state='Maharashtra',
            pin_code='411002',
            placement_department_name='TPO',
            placement_office_email='tpo2@test.com',
            approximate_student_strength=200,
        )
        self.student = _student_account(self.inst)
        self.other_student = _student_account(self.other_inst, 'stu2', 'stu2@test.com')

        self.staff_client = Client()
        self.staff_client.login(username='tpo', password='pass12345')
        self.platform_client = Client()
        self.platform_client.login(username='platform', password='pass12345')
        self.student_client = Client()
        self.student_client.login(username='stu', password='pass12345')

    def test_student_cannot_broadcast(self):
        res = self.student_client.post(
            '/api/notifications/',
            data=json.dumps({'title': 'Hi', 'body': 'Message'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 403)

    def test_staff_can_broadcast_placement_cell_message(self):
        res = self.staff_client.post(
            '/api/notifications/',
            data=json.dumps({'title': 'Drive soon', 'body': 'Infosys next week'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 201)
        payload = res.json()['notification']
        self.assertEqual(payload['sender'], 'Placement Cell')
        self.assertTrue(Notification.objects.filter(
            sender=NOTIFICATION_SENDER_PLACEMENT_CELL,
            institution=self.inst,
        ).exists())

    def test_platform_can_broadcast_platform_message(self):
        res = self.platform_client.post(
            '/api/notifications/',
            data=json.dumps({'title': 'Platform update', 'body': 'New feature live'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['notification']['sender'], 'TalentBro Platform')

    def test_student_sees_own_institution_and_platform_broadcasts_only(self):
        Notification.objects.create(
            sender=NOTIFICATION_SENDER_PLATFORM, title='Global', body='B',
        )
        Notification.objects.create(
            sender=NOTIFICATION_SENDER_PLACEMENT_CELL,
            institution=self.inst, title='Mine', body='B',
        )
        Notification.objects.create(
            sender=NOTIFICATION_SENDER_PLACEMENT_CELL,
            institution=self.other_inst, title='Not mine', body='B',
        )

        res = self.student_client.get('/api/notifications/')
        self.assertEqual(res.status_code, 200)
        titles = [n['title'] for n in res.json()['notifications']]
        self.assertIn('Global', titles)
        self.assertIn('Mine', titles)
        self.assertNotIn('Not mine', titles)
        self.assertGreaterEqual(res.json()['unread'], 2)

    def test_mark_read_updates_receipt(self):
        n = Notification.objects.create(
            sender=NOTIFICATION_SENDER_PLATFORM, title='T', body='B',
        )
        res = self.student_client.post(
            '/api/notifications/mark-read/',
            data=json.dumps({'notification_id': str(n.pk)}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        receipt = NotificationReceipt.objects.get(notification=n, user=self.student)
        self.assertTrue(receipt.read)
        body = self.student_client.get('/api/notifications/').json()
        target = next(x for x in body['notifications'] if x['id'] == str(n.pk))
        self.assertTrue(target['read'])

    def test_staff_cannot_delete_platform_broadcast(self):
        n = Notification.objects.create(
            sender=NOTIFICATION_SENDER_PLATFORM, title='T', body='B',
            created_by=self.platform_user,
        )
        res = self.staff_client.delete(f'/api/notifications/{n.pk}/')
        self.assertEqual(res.status_code, 403)

    def test_staff_deletes_own_institution_broadcast(self):
        n = Notification.objects.create(
            sender=NOTIFICATION_SENDER_PLACEMENT_CELL,
            institution=self.inst,
            created_by=self.staff_user,
            title='T',
            body='B',
        )
        res = self.staff_client.delete(f'/api/notifications/{n.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Notification.objects.filter(pk=n.pk).exists())

    def test_inactive_broadcasts_hidden_from_students(self):
        Notification.objects.create(
            sender=NOTIFICATION_SENDER_PLATFORM,
            title='Hidden', body='B', active=False,
        )
        titles = [
            n['title']
            for n in self.student_client.get('/api/notifications/').json()['notifications']
        ]
        self.assertNotIn('Hidden', titles)

    def test_student_gets_lazy_daily_nudges_on_first_open(self):
        res = self.student_client.get('/api/notifications/')
        self.assertEqual(res.status_code, 200)
        count = Notification.objects.filter(
            recipient=self.student,
            sender=NOTIFICATION_SENDER_PLATFORM,
            dedupe_key__startswith='nudge:',
        ).count()
        self.assertIn(count, (1, 2))
        body = res.json()
        titles = [n['title'] for n in body['notifications']]
        self.assertEqual(len(titles), count)
        self.assertTrue(all(n['title'] for n in body['notifications']))
        # Fresh nudges are unread.
        self.assertEqual(body['unread'], count)

    def test_nudges_are_idempotent_per_day(self):
        self.student_client.get('/api/notifications/')
        after_first = Notification.objects.filter(recipient=self.student).count()
        self.student_client.get('/api/notifications/')
        self.student_client.get('/api/notifications/')
        after_repeated = Notification.objects.filter(recipient=self.student).count()
        self.assertEqual(after_first, after_repeated)

    def test_nudge_topics_distinct_within_a_day(self):
        self.student_client.get('/api/notifications/')
        keys = list(Notification.objects.filter(
            recipient=self.student,
            sender=NOTIFICATION_SENDER_PLATFORM,
            dedupe_key__startswith='nudge:',
        ).values_list('dedupe_key', flat=True))
        topics = [k.rsplit(':', 1)[-1] for k in keys]
        self.assertEqual(len(topics), len(set(topics)))

    def test_placement_staff_not_nudged(self):
        self.staff_client.get('/api/notifications/')
        self.assertEqual(
            Notification.objects.filter(recipient=self.staff_user).count(), 0,
        )

    def test_score_nudge_message_from_readiness_components(self):
        profile = self.student.candidate_profile
        profile.readiness_components = {
            'pillars': {
                'mock_interview': {'score': 72, 'interviews': 1},
                'self_training': {'modules': {'english': 84, 'aplr': 55}},
            },
        }
        title, body, redirect, important = _nudge_message('score', profile)
        self.assertTrue(title.startswith('Your '))
        # Body always shares one of the student's own averages (72, 84 or 55).
        self.assertTrue(any(f'{score}/100' in body for score in (72, 84, 55)))
        self.assertIn(redirect, ('/mock-interview', '/english-training', '/self-training'))

    def test_score_nudge_skipped_when_no_averages(self):
        profile = self.student.candidate_profile
        profile.readiness_components = {'pillars': {}}
        profile.save(update_fields=['readiness_components'])
        self.assertIsNone(_nudge_message('score', profile))


def _add_chat_messages(user, count):
    """Give a user ``count`` student turns so their chat pillar is populated."""
    session = ChatSession.objects.create(user=user, title='practice')
    for _ in range(count):
        ChatMessage.objects.create(session=session, role='user', content='hi')
    return session


class ReadinessScoringTests(TestCase):
    def test_question_module_score_weights_solve_rate_and_stars(self):
        # 3 solved / 1 gave up (75%) + 5 stars -> 0.6*75 + 0.4*100 = 85
        self.assertEqual(_perf_question_module_score(3, 1, 5), 85)
        # nothing solved but attempts exist -> correctness half only
        self.assertEqual(_perf_question_module_score(0, 2, None), 0)
        # untouched module contributes nothing
        self.assertIsNone(_perf_question_module_score(0, 0, None))

    def test_rank_map_shares_ties_and_leaves_gaps(self):
        ranks = _rank_map({'a': 90, 'b': 90, 'c': 80, 'd': None})
        self.assertEqual(ranks, {'a': 1, 'b': 1, 'c': 3})

    def test_components_renormalise_over_available_pillars(self):
        chat_only = _perf_components(
            user_id=1,
            chat_stats={1: (50, 2)},
            mock_stats={},
            training_stats={},
        )
        self.assertEqual(chat_only['score'], 50.0)
        self.assertEqual(chat_only['coverage'], 18)
        self.assertNotIn('cgpa', chat_only['pillars'])

        # (36*90 + 18*50) / 54 = 76.666... -> 76.7
        chat_and_mock = _perf_components(
            user_id=1,
            chat_stats={1: (50, 2)},
            mock_stats={1: (90, 1)},
            training_stats={},
        )
        self.assertEqual(chat_and_mock['score'], 76.7)
        self.assertEqual(chat_and_mock['coverage'], 54)

    def test_components_none_when_no_signal(self):
        components = _perf_components(
            user_id=1,
            chat_stats={},
            mock_stats={},
            training_stats={},
        )
        self.assertIsNone(components['score'])
        self.assertIsNone(_serialize_components(components))

    def test_cgpa_alone_is_not_a_readiness_signal(self):
        _, inst = _staff_account()
        user = _student_account(inst, 'cgonly', 'cgonly@test.com')
        CandidateProfile.objects.filter(user=user).update(cgpa=9.8)

        components = _performance_components(user.candidate_profile)
        self.assertIsNone(components['score'])
        self.assertNotIn('cgpa', components['pillars'])

    def test_mock_pillar_uses_only_assessed_dimensions(self):
        _, inst = _staff_account()
        user = _student_account(inst)
        interview = MockInterview.objects.create(
            user=user, company_name='Acme', status='completed',
        )
        MockInterviewAnalysis.objects.create(
            interview=interview,
            user=user,
            communication_skills=80,
            communication_skills_desc='clear and structured',
            confidence=60,
            confidence_desc='steady but nervous',
        )

        components = _performance_components(user.candidate_profile)
        pillar = components['pillars']['mock_interview']
        self.assertEqual(pillar['score'], 70)
        self.assertEqual(pillar['interviews'], 1)


class ReadinessRankingTests(TestCase):
    def setUp(self):
        _, self.inst = _staff_account()
        self.s1 = _student_account(self.inst, 's1', 's1@test.com')
        self.s2 = _student_account(self.inst, 's2', 's2@test.com')
        self.s3 = _student_account(self.inst, 's3', 's3@test.com')

        CandidateProfile.objects.filter(user=self.s1).update(
            department='CSE',
        )
        CandidateProfile.objects.filter(user=self.s2).update(
            department='CSE',
        )
        CandidateProfile.objects.filter(user=self.s3).update(
            department='ECE',
        )

        _add_chat_messages(self.s1, 100)
        _add_chat_messages(self.s2, 50)
        _add_chat_messages(self.s3, 10)

    def test_ranks_scope_overall_and_department(self):
        profile = CandidateProfile.objects.get(user=self.s1)
        ranks = _profile_ranks(profile)

        # s1: chat 100, best overall and best in CSE. CGPA plays no part.
        self.assertEqual(ranks['overall'], 1)
        self.assertEqual(ranks['total'], 3)
        self.assertEqual(ranks['department'], 1)
        self.assertEqual(ranks['department_total'], 2)

        # s2 shares the CSE department but sits behind s1.
        s2_ranks = _profile_ranks(CandidateProfile.objects.get(user=self.s2))
        self.assertEqual(s2_ranks['department'], 2)
        self.assertEqual(s2_ranks['department_total'], 2)

        # s3 is the only ECE candidate, so their department rank is 1.
        s3_ranks = _profile_ranks(CandidateProfile.objects.get(user=self.s3))
        self.assertEqual(s3_ranks['department'], 1)
        self.assertEqual(s3_ranks['department_total'], 1)

    def test_candidates_without_signal_are_not_ranked(self):
        # A brand-new student with only a CGPA is not ranked, yet still counts
        # in the AIR denominator because the total is the college's full roll.
        _student_account(self.inst, 'blank', 'blank@test.com')
        CandidateProfile.objects.filter(user__username='blank').update(cgpa=8)
        profile = CandidateProfile.objects.get(user=self.s1)
        ranks = _profile_ranks(profile)
        self.assertEqual(ranks['total'], 4)
        blank_ranks = _profile_ranks(
            CandidateProfile.objects.get(user__username='blank')
        )
        self.assertIsNone(blank_ranks['overall'])
        self.assertIsNone(blank_ranks['score'])
        self.assertEqual(blank_ranks['total'], 4)

    def test_students_list_api_exposes_performance_and_ranks(self):
        _student_account(self.inst, 'blank', 'blank@test.com')
        client = Client()
        client.login(username='tpo', password='pass12345')
        body = client.get('/api/students/?sort=performance').json()

        self.assertEqual(body['count'], 4)
        self.assertEqual(body['students'][0]['id'], str(self.s1.candidate_profile.candidate_id))
        self.assertEqual(body['students'][0]['overall_rank'], 1)
        self.assertEqual(body['students'][0]['overall_total'], 4)
        self.assertEqual(body['students'][0]['performance_score'], body['students'][0]['performance']['score'])
        self.assertEqual(body['students'][0]['performance']['chat'], 100)
        # Sorted by score descending, the blank candidate lands last but still
        # shares the full-roll denominator.
        self.assertIsNone(body['students'][-1]['performance_score'])
        self.assertEqual(body['students'][-1]['overall_total'], 4)


class ProfilePerformanceApiTests(TestCase):
    def test_profile_api_exposes_performance_and_ranks(self):
        _, inst = _staff_account()
        user = _student_account(inst, 'api', 'api@test.com')
        CandidateProfile.objects.filter(user=user).update(department='CSE', cgpa=8)
        _add_chat_messages(user, 20)

        client = Client()
        client.login(username='api', password='pass12345')
        body = client.get('/api/auth/profile/').json()

        self.assertIn('performance', body)
        self.assertIsNotNone(body['performance']['score'])
        self.assertEqual(body['performance']['chat'], 20)
        self.assertEqual(body['ranks']['score'], body['performance']['score'])
        self.assertEqual(body['ranks']['overall'], 1)
        self.assertEqual(body['ranks']['total'], 1)


class ReadinessPersistenceTests(TestCase):
    def _row(self, profile):
        return CandidateProfile.objects.get(candidate_id=profile.candidate_id)

    def test_mutation_refresh_persists_air_and_department_rank(self):
        _, inst = _staff_account()
        s1 = _student_account(inst, 'p1', 'p1@test.com')
        s2 = _student_account(inst, 'p2', 'p2@test.com')
        CandidateProfile.objects.filter(user=s1).update(department='CSE')
        CandidateProfile.objects.filter(user=s2).update(department='CSE')
        _add_chat_messages(s1, 100)
        _add_chat_messages(s2, 50)

        _refresh_readiness_for_user(s1)
        row = self._row(s1.candidate_profile)
        self.assertIsNotNone(row.readiness_score)
        self.assertIsNotNone(row.readiness_updated_at)
        self.assertEqual(row.readiness_overall_rank, 1)
        self.assertEqual(row.readiness_overall_total, 2)
        self.assertEqual(row.readiness_department_rank, 1)
        self.assertEqual(row.readiness_department_total, 2)
        self.assertEqual(row.readiness_components.get('score'), row.readiness_score)

        _refresh_readiness_for_user(s2)
        self.assertEqual(self._row(s2.candidate_profile).readiness_department_rank, 2)

    def test_read_path_persists_ranks_off_stale_instance(self):
        # _profile_ranks must persist ranks on the DB row even though the passed
        # instance itself may hold stale values (fresh rows get bulk-updated).
        _, inst = _staff_account()
        s1 = _student_account(inst, 'q1', 'q1@test.com')
        _add_chat_messages(s1, 30)
        profile = CandidateProfile.objects.get(user=s1)
        ranks = _profile_ranks(profile)
        row = self._row(profile)
        self.assertEqual(row.readiness_overall_rank, ranks['overall'])
        self.assertEqual(row.readiness_score, ranks['score'])

    def test_blank_profile_persists_empty_rank_and_components(self):
        _, inst = _staff_account()
        blank = _student_account(inst)
        _refresh_readiness_for_user(blank)
        row = self._row(blank.candidate_profile)
        self.assertIsNone(row.readiness_score)
        self.assertIsNone(row.readiness_overall_rank)
        self.assertEqual(row.readiness_overall_total, 1)
        self.assertEqual(row.readiness_components, {})

    def test_full_roll_denominators_include_non_engaged_students(self):
        _, inst = _staff_account()
        engaged = _student_account(inst, 'e1', 'e1@test.com')
        second = _student_account(inst, 'e2', 'e2@test.com')
        sitting_out = _student_account(inst, 'sit', 'sit@test.com')
        CandidateProfile.objects.filter(user=engaged).update(department='CSE')
        CandidateProfile.objects.filter(user=second).update(department='CSE')
        CandidateProfile.objects.filter(user=sitting_out).update(
            department='CSE', cgpa=9,
        )
        _add_chat_messages(engaged, 100)
        _add_chat_messages(second, 50)

        _refresh_readiness_for_user(engaged)
        row = self._row(engaged.candidate_profile)
        self.assertEqual(row.readiness_overall_rank, 1)
        self.assertEqual(row.readiness_overall_total, 3)
        self.assertEqual(row.readiness_department_total, 3)

        _refresh_readiness_for_user(sitting_out)
        out_row = self._row(sitting_out.candidate_profile)
        self.assertIsNone(out_row.readiness_overall_rank)
        self.assertIsNone(out_row.readiness_score)
        self.assertEqual(out_row.readiness_overall_total, 3)
        self.assertEqual(out_row.readiness_department_total, 3)


class GeminiCostTests(TestCase):
    # 1000 input + 500 output tokens on gemini-2.5-flash-lite
    # (input $0.10/1M, output $0.40/1M) => 0.0003 USD => 0.0285 INR
    # with the 40% margin and 4-dp rounding => Decimal('0.0399').
    CAMEL_USAGE = {
        'promptTokenCount': 1000,
        'candidatesTokenCount': 500,
        'totalTokenCount': 1500,
    }
    SNAKE_USAGE = {
        'prompt_token_count': 1000,
        'candidates_token_count': 500,
        'total_token_count': 1500,
    }
    TOTAL_ONLY_USAGE = {
        'candidatesTokenCount': 500,
        'totalTokenCount': 1500,
    }

    def test_prices_camel_case_metadata(self):
        self.assertEqual(
            usage_cost_inr('gemini-2.5-flash-lite', self.CAMEL_USAGE),
            Decimal('0.0399'),
        )

    def test_prices_snake_case_metadata(self):
        self.assertEqual(
            usage_cost_inr('gemini-2.5-flash-lite', self.SNAKE_USAGE),
            Decimal('0.0399'),
        )

    def test_splits_total_when_prompt_missing(self):
        self.assertEqual(
            usage_cost_inr('gemini-2.5-flash-lite', self.TOTAL_ONLY_USAGE),
            Decimal('0.0399'),
        )

    def test_prices_model_version_suffix(self):
        self.assertEqual(
            usage_cost_inr('models/gemini-2.5-flash-lite-001', self.CAMEL_USAGE),
            Decimal('0.0399'),
        )

    def test_falls_back_to_default_prices_for_unknown_model(self):
        self.assertEqual(
            usage_cost_inr('some-other-model', self.CAMEL_USAGE),
            Decimal('0.0399'),
        )

    def test_returns_zero_without_metadata(self):
        self.assertEqual(usage_cost_inr('gemini-2.5-flash-lite', None),
                         Decimal('0.0000'))
        self.assertEqual(usage_cost_inr('gemini-2.5-flash-lite', {}),
                         Decimal('0.0000'))
        self.assertEqual(usage_cost_inr('gemini-2.5-flash-lite', 'nope'),
                         Decimal('0.0000'))

    def test_record_cost_incurred_accumulates_on_candidate(self):
        _, inst = _staff_account()
        student = _student_account(inst, 'tokens', 'tokens@test.com')
        payload = {'usageMetadata': self.CAMEL_USAGE}

        added = record_cost_incurred(student, 'gemini-2.5-flash-lite', payload)
        self.assertEqual(added, Decimal('0.0399'))
        profile = CandidateProfile.objects.get(user=student)
        self.assertEqual(profile.cost_incurred, Decimal('0.0399'))

        record_cost_incurred(student, 'gemini-2.5-flash-lite', payload)
        profile.refresh_from_db()
        self.assertEqual(profile.cost_incurred, Decimal('0.0798'))

    def test_record_cost_incurred_skips_staff_and_blank_payloads(self):
        staff, inst = _staff_account()
        student = _student_account(inst, 'nopay', 'nopay@test.com')
        payload = {'usageMetadata': self.CAMEL_USAGE}

        # Staff accounts have no CandidateProfile, so they are never charged.
        self.assertEqual(record_cost_incurred(staff, 'gemini-2.5-flash-lite', payload),
                         Decimal('0.0000'))
        self.assertFalse(hasattr(staff, 'candidate_profile'))

        # Non-dict / empty-metadata payloads charge nothing.
        self.assertEqual(record_cost_incurred(student, 'gemini-2.5-flash-lite', 'nope'),
                         Decimal('0.0000'))
        self.assertEqual(
            record_cost_incurred(student, 'gemini-2.5-flash-lite',
                                 {'usageMetadata': {}}),
            Decimal('0.0000'),
        )
        self.assertEqual(
            CandidateProfile.objects.get(user=student).cost_incurred,
            Decimal('0.0000'),
        )

    def test_record_cost_incurred_ignores_unauthenticated(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertEqual(record_cost_incurred(AnonymousUser(), 'gemini-2.5-flash-lite',
                                              {'usageMetadata': self.CAMEL_USAGE}),
                         Decimal('0.0000'))