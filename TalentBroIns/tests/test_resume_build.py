"""Tests for the resume build endpoint.

These exist because the endpoint scrapes a third-party profile, merges it with the
signed-in candidate's own row and writes nothing back — so every branch is only
visible at runtime, and `manage.py check` cannot see any of it. The Apify call is
patched out so the suite never spends a scrape or needs a token.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from TalentBroIns.models import CandidateProfile
from TalentBroIns.views import _resume_pdf_path

USER_MODEL = get_user_model()

# TalentBroIns/urls.py sets app_name, so every pattern is namespaced.
NAMESPACE = 'TalentBroIns'

RESUME_BUILD = 'resume-build'
RESUME_DOWNLOAD = 'resume-download'

# A trimmed stand-in for the actor's dataset item, keeping the key names that
# actor actually uses (singular `experience` / `education`).
FAKE_SCRAPE = {
    'success': True,
    'fullName': 'Bill Gates',
    'headline': 'Co-chair at the Gates Foundation',
    'about': 'Working on early childhood education.',
    'location': 'Seattle, Washington, United States',
    'profilePictureUrl': 'https://media.licdn.com/example.jpg',
    'experience': [{'company': 'Microsoft', 'companyUrl': 'https://example.com'}],
    'education': [{'school': 'Harvard University', 'degree': '-',
                   'dateRange': '1973 - 1975', 'startDate': 1973, 'endDate': 1975}],
    'linkedinUrl': 'https://www.linkedin.com/in/williamhgates',
}

PDF_MAGIC = b'%PDF-'


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='talentbro-resume-test-'))
class ResumeBuildTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        # The temp MEDIA_ROOT above is process-wide, so it is cleared here rather
        # than left behind in the temp directory.
        shutil.rmtree(str(settings.MEDIA_ROOT), ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        # Resume files live on disk, and SQLite hands a rolled-back primary key
        # straight back to the next test, so the previous test's PDF would still
        # be sitting under this test's user id. Clear the store per test.
        shutil.rmtree(str(Path(settings.MEDIA_ROOT) / 'resumes'), ignore_errors=True)

        self.user = USER_MODEL.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='pw',
        )
        self.profile = CandidateProfile.objects.create(
            user=self.user,
            first_name='Bill',
            last_name='Gates',
            department='Computer Science',
            skills=['Python'],
            linkedin_url='https://www.linkedin.com/in/williamhgates',
        )
        self.client.force_login(self.user)

    def _post(self, payload):
        return self.client.post(
            reverse(f'{NAMESPACE}:{RESUME_BUILD}'),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def _with_scrape(self, item=None, error=None):
        return mock.patch(
            'TalentBroIns.views.scrape_linkedin_profile',
            return_value=(FAKE_SCRAPE if item is None else item, error),
        )

    def test_unauthenticated_is_rejected(self):
        res = Client().post(
            reverse(f'{NAMESPACE}:{RESUME_BUILD}'),
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 401)

    def test_invalid_json_is_rejected(self):
        res = self.client.post(
            reverse(f'{NAMESPACE}:{RESUME_BUILD}'),
            data='not json',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    def test_missing_url_is_rejected(self):
        self.profile.linkedin_url = ''
        self.profile.save(update_fields=['linkedin_url'])
        res = self._post({})
        self.assertEqual(res.status_code, 400)
        self.assertIn('LinkedIn profile link', res.json()['detail'])

    def test_non_linkedin_url_is_rejected(self):
        res = self._post({'linkedin_url': 'https://example.com/not-linkedin'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('does not look like a LinkedIn', res.json()['detail'])

    def test_scrape_failure_is_reported_and_logged(self):
        with self._with_scrape(item=None, error='Apify request failed: boom'):
            with self.assertLogs('TalentBroIns.views', level='WARNING') as captured:
                res = self._post({})
        self.assertEqual(res.status_code, 400)
        self.assertIn('boom', res.json()['detail'])
        self.assertIn('boom', '\n'.join(captured.output))

    def test_falls_back_to_the_saved_linkedin_url(self):
        with self._with_scrape() as scrape:
            res = self._post({})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            scrape.call_args.args, ('https://www.linkedin.com/in/williamhgates',),
        )

    def test_body_url_overrides_the_saved_one(self):
        with self._with_scrape() as scrape:
            res = self._post({'linkedin_url': 'https://linkedin.com/in/other-person'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            scrape.call_args.args, ('https://linkedin.com/in/other-person',),
        )

    def test_reports_the_sections_it_found(self):
        with self._with_scrape():
            res = self._post({})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['ok'])
        self.assertTrue(body['logged'])
        # The actor spells these in the singular, which is what the alias list has
        # to match for a resume to have an experience and an education section.
        self.assertIn('experiences', body['sections'])
        self.assertIn('educations', body['sections'])
        self.assertIn('summary', body['sections'])
        self.assertIn('about', body['sections'])

    def test_logs_the_linkedin_and_platform_profiles(self):
        with self._with_scrape():
            with self.assertLogs('TalentBroIns.views', level='INFO') as captured:
                self._post({})
        output = '\n'.join(captured.output)
        self.assertIn('Bill Gates', output)
        self.assertIn('Harvard University', output)
        self.assertIn('Co-chair at the Gates Foundation', output)
        # The candidate's own platform profile is logged alongside the scrape.
        self.assertIn('Computer Science', output)
        self.assertIn('Python', output)

    def test_writes_nothing_back_to_the_profile(self):
        before = CandidateProfile.objects.get(pk=self.profile.pk)
        snapshot = {
            'skills': before.skills,
            'bio': before.bio,
            'avatar': before.avatar,
            'certifications': before.certifications,
        }
        with self._with_scrape():
            self._post({})
        after = CandidateProfile.objects.get(pk=self.profile.pk)
        self.assertEqual(after.skills, snapshot['skills'])
        self.assertEqual(after.bio, snapshot['bio'])
        self.assertEqual(after.avatar, snapshot['avatar'])
        self.assertEqual(after.certifications, snapshot['certifications'])

    def test_returns_a_download_path(self):
        with self._with_scrape():
            res = self._post({})
        self.assertEqual(res.json()['pdf_url'], reverse(f'{NAMESPACE}:{RESUME_DOWNLOAD}'))

    def test_writes_a_pdf_the_candidate_can_download(self):
        with self._with_scrape():
            self._post({})
        res = self.client.get(reverse(f'{NAMESPACE}:{RESUME_DOWNLOAD}'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        body = b''.join(res.streaming_content)
        self.assertTrue(body.startswith(PDF_MAGIC), 'download did not return a PDF')

    def test_download_is_offered_under_the_candidate_name(self):
        with self._with_scrape():
            self._post({})
        res = self.client.get(reverse(f'{NAMESPACE}:{RESUME_DOWNLOAD}'))
        self.assertIn('bill-gates-resume.pdf', res['Content-Disposition'])

    def test_one_candidate_cannot_read_another_candidates_resume(self):
        with self._with_scrape():
            self._post({})

        other = USER_MODEL.objects.create_user(
            username='other@example.com', email='other@example.com', password='pw',
        )
        CandidateProfile.objects.create(user=other, first_name='Other', last_name='Person')
        other_client = Client()
        other_client.force_login(other)
        res = other_client.get(reverse(f'{NAMESPACE}:{RESUME_DOWNLOAD}'))
        # A per-user path means the second candidate simply has no file of their
        # own yet, rather than being handed the first candidate's resume.
        self.assertEqual(res.status_code, 404)

    def test_rebuilding_overwrites_the_previous_pdf(self):
        with self._with_scrape():
            self._post({})
        first = _resume_pdf_path(self.user).read_bytes()

        updated = {'success': True, 'fullName': 'Bill Gates',
                   'headline': 'Founder of Breakthrough Energy'}
        with self._with_scrape(item=updated):
            self._post({})
        second = _resume_pdf_path(self.user).read_bytes()

        self.assertNotEqual(first, second, 'the stale PDF was served again')
        res = self.client.get(reverse(f'{NAMESPACE}:{RESUME_DOWNLOAD}'))
        self.assertEqual(b''.join(res.streaming_content), second)

    def test_download_requires_authentication(self):
        with self._with_scrape():
            self._post({})
        res = Client().get(reverse(f'{NAMESPACE}:{RESUME_DOWNLOAD}'))
        self.assertEqual(res.status_code, 401)

    def test_download_before_any_build_is_a_404(self):
        res = self.client.get(reverse(f'{NAMESPACE}:{RESUME_DOWNLOAD}'))
        self.assertEqual(res.status_code, 404)

    def test_a_thin_profile_still_produces_a_valid_pdf(self):
        """A scrape that returned no sections must not fail the build."""
        with mock.patch(
            'TalentBroIns.views.scrape_linkedin_profile', return_value=({}, None),
        ):
            res = self._post({})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['sections'], [])
        body = b''.join(
            self.client.get(reverse(f'{NAMESPACE}:{RESUME_DOWNLOAD}')).streaming_content
        )
        self.assertTrue(body.startswith(PDF_MAGIC))

    def test_a_missing_linkedin_url_is_still_rejected(self):
        # Building from nothing is not the same as building from an empty scrape:
        # without a URL there is nothing to scrape.
        self.profile.linkedin_url = ''
        self.profile.save(update_fields=['linkedin_url'])
        res = self._post({})
        self.assertEqual(res.status_code, 400)
