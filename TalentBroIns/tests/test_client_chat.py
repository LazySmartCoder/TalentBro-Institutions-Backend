"""Tests for the placement-cell ("client") AI chat.

The placement chat is the one AI surface that reads OTHER people's data, so the
two things worth pinning down with tests are:

* **Isolation.** Every tool resolves against exactly one ``Institution`` and
  nothing else. A tool surface that quietly accepted free-form SQL (as the
  student chat does) could not make that promise, which is why the student tools
  are explicitly asserted to be absent here. The tests below drive each tool with
  another institute's ids and assert nothing leaks.
* **Persistence in its own store.** Threads land in ``ClientChatSession`` and are
  never visible to another officer, to the student chat, or to the student chat's
  ``ChatSession`` tables.

Gemini is never called: the agentic turn is patched, so these tests are about our
code (authorisation, scoping, storage), not about the model's behaviour.
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from TalentBroIns import views
from TalentBroIns.models import (
    APLRTraining,
    CandidateProfile,
    ChatMessage,
    ChatSession,
    ClientChatMessage,
    ClientChatSession,
    ClientProfile,
    Company,
    Drive,
    Institution,
    MockInterview,
)

USER_MODEL = get_user_model()
NAMESPACE = 'TalentBroIns'

REPLY = '12 of 30 students are placed, so the rate is 40%.'


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


def _student(first_name, last_name, institution, **overrides):
    user = USER_MODEL.objects.create_user(
        username=f'{first_name}.{last_name}'.lower(),
        email=f'{first_name}.{last_name}@student.test'.lower(),
        password='pw',
    )
    fields = {
        'user': user,
        'college': institution,
        # The profile's own name parts are what the assistant reads, so they have
        # to be set here; the username/email alone leave every row "Unnamed".
        'first_name': first_name,
        'last_name': last_name,
        'department': 'CSE',
        'program': 'B.Tech',
        'end_year': 2027,
        'cgpa': Decimal('8.00'),
        'placement_status': 'not_started',
    }
    fields.update(overrides)
    return CandidateProfile.objects.create(**fields)


class ClientChatAccessTests(TestCase):
    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.officer = _staff('cell@alpha.test', self.institution)

    def test_anonymous_is_rejected(self):
        self.assertEqual(
            self.client.get(url('client-chat-sessions')).status_code, 401)
        self.assertEqual(
            self.client.post(url('client-chat'), {'message': 'hi'},
                             content_type='application/json').status_code,
            401,
        )

    def test_a_student_cannot_reach_the_placement_chat(self):
        # The placement chat answers about a whole roster, so a student account
        # must be turned away at the door rather than filtered per query.
        student = _student('Ravi', 'Kumar', self.institution)
        self.client.force_login(student.user)

        self.assertEqual(
            self.client.get(url('client-chat-sessions')).status_code, 403)
        self.assertEqual(
            self.client.post(url('client-chat'), {'message': 'how many students?'},
                             content_type='application/json').status_code,
            403,
        )
        self.assertFalse(ClientChatSession.objects.exists())

    def test_staff_without_an_institution_is_rejected(self):
        # A role check alone is not enough: an unattached staff account must never
        # be served a query with no institute scope.
        orphan = USER_MODEL.objects.create_user(
            username='orphan', email='orphan@nowhere.test', password='pw')
        orphan.is_staff = True
        orphan.save()
        self.client.force_login(orphan)

        self.assertEqual(
            self.client.get(url('client-chat-sessions')).status_code, 403)

    def test_an_officer_cannot_open_another_officers_thread(self):
        # Threads are private to the officer who owns them, even inside the same
        # placement cell.
        other_officer = _staff('cell2@alpha.test', self.institution)
        session = ClientChatSession.objects.create(user=other_officer, title='Private')
        ClientChatMessage.objects.create(
            session=session, role='user', content='our CSE numbers please')

        self.client.force_login(self.officer)

        self.assertEqual(
            self.client.get(url('client-chat-session-detail',
                                session_id=str(session.pk))).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(url('client-chat-session-detail',
                                   session_id=str(session.pk))).status_code,
            404,
        )
        self.assertTrue(ClientChatSession.objects.filter(pk=session.pk).exists())
        self.assertEqual(
            self.client.get(url('client-chat-sessions')).json()['sessions'], [])


class ClientChatPersistenceTests(TestCase):
    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.officer = _staff('cell@alpha.test', self.institution)
        self.client.force_login(self.officer)

    def _post(self, message, session_id=None):
        body = {'message': message}
        if session_id:
            body['session_id'] = session_id
        with mock.patch.object(views, '_run_agentic_turn',
                               return_value=(REPLY, None, None)) as agentic:
            return self.client.post(url('client-chat'), body,
                                    content_type='application/json'), agentic

    def test_a_turn_is_stored_in_the_client_chat_tables_only(self):
        response, _agentic = self._post('How many students are placed?')

        self.assertEqual(response.status_code, 200)
        session = ClientChatSession.objects.get()
        self.assertEqual(session.user, self.officer)
        # 'how' and 'are' are stopwords, so the title keeps the meaningful words.
        self.assertEqual(session.title, 'Many students placed')
        self.assertEqual(
            [m.role for m in session.messages.all()], ['user', 'assistant'])
        self.assertEqual(session.messages.last().content, REPLY)
        # The whole point of the separate tables: a placement conversation must
        # never appear in the student chat store.
        self.assertFalse(ChatSession.objects.exists())
        self.assertFalse(ChatMessage.objects.exists())

    def test_a_replied_session_is_reused(self):
        first, _ = self._post('How many students are placed?')
        session_id = first.json()['session_id']

        second, _ = self._post('And by department?', session_id=session_id)

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['session_id'], session_id)
        self.assertEqual(ClientChatSession.objects.count(), 1)
        self.assertEqual(ClientChatSession.objects.get().messages.count(), 4)

    def test_the_turn_is_scoped_to_the_officers_own_institute(self):
        # The institute is closed over per request, so the tool runner handed to
        # Gemini can only ever resolve against this officer's institution.
        response, agentic = self._post('How many students are placed?')
        self.assertEqual(response.status_code, 200)

        runner = agentic.call_args.kwargs['tool_runner']
        listed = runner({'functionCall': {
            'name': 'list_institution_students', 'args': {}}}, None)
        self.assertEqual(listed['institution'], self.institution.name)

        declarations = agentic.call_args.kwargs['functions']
        self.assertEqual(
            [fn['name'] for fn in declarations],
            ['list_institution_students', 'get_student_placement_detail',
             'aggregate_institute_data', 'list_institute_drives', 'calculate'],
        )

    def test_the_student_tools_are_not_exposed(self):
        # The student chat's tools include free-form read-only SQL and a profile
        # write. Neither can be constrained to an institute, so the placement chat
        # must not ship them.
        names = {fn['name'] for fn in views.CLIENT_CHAT_FUNCTIONS}
        self.assertNotIn('query_database', names)
        self.assertNotIn('get_current_profile', names)
        self.assertNotIn('update_profile', names)

    def test_a_failed_turn_is_not_left_in_the_transcript(self):
        with mock.patch.object(views, '_run_agentic_turn',
                               return_value=(None, 502, 'Gemini is down')):
            response = self.client.post(
                url('client-chat'), {'message': 'hello'},
                content_type='application/json')

        self.assertEqual(response.status_code, 502)
        # The orphaned question would be replayed into the model on the next
        # attempt, so it is rolled back with the failed turn.
        self.assertEqual(ClientChatMessage.objects.count(), 0)
        # An opening turn that failed leaves nothing behind either: an empty
        # thread is noise in the sidebar.
        self.assertFalse(ClientChatSession.objects.exists())

    def test_a_failed_turn_keeps_an_existing_thread(self):
        first, _ = self._post('How many students are placed?')
        session_id = first.json()['session_id']

        with mock.patch.object(views, '_run_agentic_turn',
                               return_value=(None, 502, 'Gemini is down')):
            response = self.client.post(
                url('client-chat'), {'message': 'And by department?'},
                content_type='application/json')

        self.assertEqual(response.status_code, 502)
        # The earlier turns are still a real conversation, so the thread survives
        # with only the failed question rolled back.
        session = ClientChatSession.objects.get()
        self.assertEqual(str(session.pk), session_id)
        self.assertEqual(session.messages.count(), 2)

    def test_a_blank_message_is_rejected(self):
        response = self.client.post(
            url('client-chat'), {'message': '   '}, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClientChatSession.objects.exists())

    def test_listing_paginates_newest_first(self):
        for index in range(3):
            session = ClientChatSession.objects.create(
                user=self.officer, title=f'Chat {index}')
            ClientChatMessage.objects.create(
                session=session, role='user', content='hi')

        page = self.client.get(url('client-chat-sessions'), {'limit': 2}).json()

        self.assertEqual(page['limit'], 2)
        self.assertTrue(page['has_more'])
        self.assertEqual(len(page['sessions']), 2)
        self.assertEqual([s['message_count'] for s in page['sessions']], [1, 1])

    def test_the_detail_endpoint_pages_the_transcript_backwards(self):
        session = ClientChatSession.objects.create(user=self.officer, title='Thread')
        for index in range(5):
            ClientChatMessage.objects.create(
                session=session, role='user', content=f'message {index}')

        newest = self.client.get(
            url('client-chat-session-detail', session_id=str(session.pk)),
            {'limit': 2}).json()['session']

        self.assertEqual([m['content'] for m in newest['messages']],
                         ['message 3', 'message 4'])
        self.assertTrue(newest['older_available'])

        older = self.client.get(
            url('client-chat-session-detail', session_id=str(session.pk)),
            {'limit': 2, 'before': newest['messages'][0]['id']}).json()['session']
        self.assertEqual([m['content'] for m in older['messages']],
                         ['message 1', 'message 2'])
        self.assertTrue(older['older_available'])


class ClientChatToolIsolationTests(TestCase):
    """Every tool is driven with the other institute's ids and must not leak."""

    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.other = _institution('Beta Institute', 'beta.test')
        # A Company row belongs to the officer who recorded it, so the drive
        # fixtures need a staff account on each side.
        self.alpha_staff = _staff('cell@alpha.test', self.institution)
        self.beta_staff = _staff('cell@beta.test', self.other)

        self.placed = _student(
            'Asha', 'Rao', self.institution, department='CSE',
            placement_status='placed', readiness_score=90, cgpa=Decimal('9.10'),
            mock_interview_score=88, self_training_score=82)
        self.ready = _student(
            'Bala', 'Raj', self.institution, department='ECE',
            placement_status='applying', readiness_score=55, cgpa=Decimal('7.40'))
        self.ineligible = _student(
            'Chan', 'Wu', self.institution, department='CSE',
            placement_status='not_started', readiness_score=12)

        self.outsider = _student(
            'Dara', 'Secret', self.other, department='CSE',
            placement_status='placed', readiness_score=95)

        APLRTraining.objects.create(
            user=self.placed.user, category='quantitative', status='solved',
            points_awarded=10)
        MockInterview.objects.create(
            user=self.placed.user, company_name='Alpha Corp', status='completed')

    def _call(self, name, args):
        return views._client_chat_execute_tool(
            {'functionCall': {'name': name, 'args': args}}, self.institution)

    def test_listing_students_returns_only_this_institute(self):
        result = self._call('list_institution_students', {'limit': 50})

        self.assertTrue(result['ok'])
        self.assertEqual(result['total_in_institution'], 3)
        names = {row['name'] for row in result['students']}
        self.assertEqual(names, {'Asha Rao', 'Bala Raj', 'Chan Wu'})
        self.assertNotIn('Dara Secret', names)

    def test_listing_students_filters(self):
        result = self._call('list_institution_students', {
            'department': 'CSE', 'not_placed_only': True, 'limit': 50})
        self.assertEqual({row['name'] for row in result['students']}, {'Chan Wu'})

        eligible = self._call('list_institution_students', {
            'eligible_only': True, 'limit': 50})
        self.assertEqual({row['name'] for row in eligible['students']},
                         {'Asha Rao', 'Bala Raj'})

        ready = self._call('list_institution_students', {
            'min_readiness_score': 60, 'limit': 50})
        self.assertEqual({row['name'] for row in ready['students']}, {'Asha Rao'})

    def test_student_detail_refuses_another_institutes_student(self):
        # A perfectly valid id, just not this institute's.
        result = self._call('get_student_placement_detail',
                            {'student_id': str(self.outsider.candidate_id)})

        self.assertFalse(result['ok'])
        self.assertNotIn('Dara', str(result))
        self.assertNotIn('student', result)

    def test_student_detail_returns_our_own_student(self):
        result = self._call('get_student_placement_detail',
                            {'student_id': str(self.placed.candidate_id)})

        self.assertTrue(result['ok'])
        self.assertEqual(result['student']['name'], 'Asha Rao')
        self.assertEqual(result['student']['readiness_score'], 90)
        self.assertEqual(result['mock_interviews']['total'], 1)
        self.assertEqual(result['self_training'][0]['module'],
                         'Aptitude & Logical Reasoning (APLR)')

    def test_student_detail_reports_an_ambiguous_name(self):
        _student('Asha', 'Menon', self.institution, department='CSE')

        result = self._call('get_student_placement_detail', {'name': 'Asha'})

        self.assertFalse(result['ok'])
        self.assertEqual(len(result['candidates']), 2)

    def test_aggregates_count_only_this_institute(self):
        result = self._call('aggregate_institute_data', {'group_by': 'department'})

        self.assertTrue(result['ok'])
        self.assertEqual(result['total_students_matching'], 3)
        groups = {row['group']: row for row in result['groups']}
        self.assertEqual(set(groups), {'CSE', 'ECE'})
        self.assertEqual(groups['CSE']['students'], 2)
        self.assertEqual(groups['CSE']['placed'], 1)
        self.assertEqual(groups['CSE']['with_mock_score'], 1)
        self.assertEqual(groups['ECE']['students'], 1)

    def test_aggregates_support_the_other_groupings(self):
        eligibility = self._call('aggregate_institute_data',
                                 {'group_by': 'eligibility'})
        by_group = {row['group']: row['students'] for row in eligibility['groups']}
        self.assertEqual(by_group, {'eligible': 2, 'ineligible': 1})

        bands = self._call('aggregate_institute_data', {'group_by': 'readiness_band'})
        self.assertEqual(
            {row['group']: row['students'] for row in bands['groups']},
            {'topper_80_plus': 1, 'ready_40_59': 1, 'not_ready': 1})

    def test_aggregates_reject_an_unknown_grouping(self):
        result = self._call('aggregate_institute_data', {'group_by': 'salary'})

        self.assertFalse(result['ok'])
        self.assertIn('group_by must be one of', result['error'])

    def test_drives_are_scoped_to_the_institution(self):
        company = Company.objects.create(
            company_name='Alpha Corp', tier='dream',
            institution=self.institution,
            client=ClientProfile.objects.get(user=self.alpha_staff))
        Drive.objects.create(
            institution=self.institution, company=company, title='Alpha Drive',
            total_vacancies=10, status='ongoing')
        other_company = Company.objects.create(
            company_name='Beta Corp', tier='core',
            institution=self.other,
            client=ClientProfile.objects.get(user=self.beta_staff))
        Drive.objects.create(
            institution=self.other, company=other_company, title='Beta Drive',
            total_vacancies=99, status='ongoing')

        result = self._call('list_institute_drives', {'limit': 50})

        self.assertTrue(result['ok'])
        self.assertEqual(result['total_drives'], 1)
        self.assertEqual([d['title'] for d in result['drives']], ['Alpha Drive'])
        self.assertNotIn('Beta Drive', str(result))

    def test_the_reference_context_mentions_only_this_institute(self):
        company = Company.objects.create(
            company_name='Alpha Corp', tier='dream',
            institution=self.institution,
            client=ClientProfile.objects.get(user=self.alpha_staff))
        Drive.objects.create(
            institution=self.institution, company=company, title='Alpha Drive',
            total_vacancies=10, status='ongoing')
        Drive.objects.create(
            institution=self.other, company=Company.objects.create(
                company_name='Beta Corp', tier='core',
                institution=self.other,
                client=ClientProfile.objects.get(user=self.beta_staff)),
            title='Beta Drive', total_vacancies=99, status='ongoing')

        context = views._client_chat_reference_context(self.institution)

        self.assertIn('Alpha Institute', context)
        self.assertNotIn('Beta Institute', context)
        self.assertNotIn('Dara', context)
        self.assertIn('Asha Rao', context)
        # The snapshot summarises drives by status and total openings, so the
        # other institute's 99 vacancies must not show up in ours.
        self.assertIn('Active / Ongoing 1', context)
        self.assertIn('10 opening(s) in total', context)
        self.assertNotIn('99', context)


class ClientChatCalculatorTests(TestCase):
    """The calculator is what makes "do the maths for me" reliable."""

    def _calculate(self, expression):
        return views._client_chat_calculate({'expression': expression})

    def test_it_computes_placement_rates(self):
        # Literal numbers only: the sandbox refuses bare names, which is why the
        # tool description tells the model to substitute fetched figures.
        result = self._calculate('(12 / 30) * 100')

        self.assertTrue(result['ok'])
        self.assertEqual(self._calculate('(2 / 5) * 100')['result'], 40.0)
        self.assertEqual(self._calculate('round((2 / 5) * 100, 1)')['result'], 40.0)
        self.assertEqual(self._calculate('sum([1, 2, 3, 4])')['result'], 10)
        self.assertEqual(self._calculate('max(3, 9)')['result'], 9)

    def test_it_reports_errors_instead_of_raising(self):
        self.assertFalse(self._calculate('1 / 0')['ok'])
        self.assertFalse(self._calculate('(1 +')['ok'])
        self.assertFalse(self._calculate('')['ok'])
        self.assertFalse(self._calculate('(placed / total) * 100')['ok'])

    def test_it_refuses_anything_that_is_not_arithmetic(self):
        # The allow-list is the sandbox: names, attributes and calls outside the
        # allowed functions must all fail rather than reach Python.
        for expression in (
            '__import__("os").system("echo pwned")',
            'open("/etc/passwd").read()',
            'os.getcwd()',
            'password',
            '[x for x in range(3)]',
            '2 ** 100000',
        ):
            with self.subTest(expression=expression):
                self.assertFalse(self._calculate(expression)['ok'])