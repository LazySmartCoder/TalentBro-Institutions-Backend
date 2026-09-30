"""Tests for the company edit endpoint (PATCH /api/companies/<id>/update/).

These exist because `company_update` writes a hand-listed set of fields behind
an institution-scoping check. A typo in a field name, a bad import of the tier
choices, or a missing institution filter all pass `manage.py check` and then
either 500 on the first save or, worse, quietly edit another college's partner.
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from TalentBroIns.models import ClientProfile, Company, Drive, Institution

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


class CompanyUpdateTests(TestCase):
    def setUp(self):
        self.institution = _institution('Alpha Institute', 'alpha.test')
        self.other = _institution('Beta Institute', 'beta.test')
        self.user = _staff('cell@alpha.test', self.institution)
        self.client.force_login(self.user)

        self.company = Company.objects.create(
            company_id='ALPHA-1',
            company_name='Alpha Corp',
            industry='IT Services',
            company_description='Original blurb',
            work_location='Bengaluru',
            tier='core',
            salary_min=3,
            salary_max=6,
            minimum_cgpa='6.00',
            maximum_backlogs=2,
            graduation_year=2027,
            eligible_courses=['B.Tech'],
            eligible_branches=['CSE'],
            institution=self.institution,
            client=ClientProfile.objects.get(user=self.user),
        )

    def patch(self, payload, company=None):
        return self.client.patch(
            url('company-update', company_id=(company or self.company).pk),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_updates_every_editable_field(self):
        res = self.patch({
            'company_name': 'Alpha Corp Ltd',
            'industry': 'Product Engineering',
            'company_description': 'Revised blurb',
            'work_location': 'Hyderabad',
            'tier': 'dream',
            'salary_min': 4.5,
            'salary_max': 9,
            'minimum_cgpa': 7.25,
            'maximum_backlogs': 0,
            'graduation_year': 2028,
            'eligible_courses': ['B.Tech', 'MCA'],
            'eligible_branches': ['CSE', 'IT'],
        })
        self.assertEqual(res.status_code, 200, res.content)

        company = Company.objects.get(pk=self.company.pk)
        self.assertEqual(company.company_name, 'Alpha Corp Ltd')
        self.assertEqual(company.industry, 'Product Engineering')
        self.assertEqual(company.company_description, 'Revised blurb')
        self.assertEqual(company.work_location, 'Hyderabad')
        self.assertEqual(company.tier, 'dream')
        self.assertEqual(float(company.salary_min), 4.5)
        self.assertEqual(float(company.salary_max), 9)
        self.assertEqual(float(company.minimum_cgpa), 7.25)
        self.assertEqual(company.maximum_backlogs, 0)
        self.assertEqual(company.graduation_year, 2028)
        self.assertEqual(company.eligible_courses, ['B.Tech', 'MCA'])
        self.assertEqual(company.eligible_branches, ['CSE', 'IT'])

    def test_accepts_comma_separated_lists(self):
        self.patch({'eligible_branches': 'CSE, IT , ECE'})
        self.company.refresh_from_db()
        self.assertEqual(self.company.eligible_branches, ['CSE', 'IT', 'ECE'])

    def test_only_writes_the_keys_present_in_the_body(self):
        self.patch({'industry': 'Fintech'})
        self.company.refresh_from_db()
        self.assertEqual(self.company.industry, 'Fintech')
        self.assertEqual(self.company.work_location, 'Bengaluru')
        self.assertEqual(self.company.salary_max, 6)

    def test_blank_numeric_clears_the_field(self):
        self.patch({'salary_max': None, 'minimum_cgpa': ''})
        self.company.refresh_from_db()
        self.assertIsNone(self.company.salary_max)
        self.assertIsNone(self.company.minimum_cgpa)

    def test_rejects_blank_company_name(self):
        res = self.patch({'company_name': '   '})
        self.assertEqual(res.status_code, 400)
        self.company.refresh_from_db()
        self.assertEqual(self.company.company_name, 'Alpha Corp')

    def test_rejects_unknown_tier(self):
        res = self.patch({'tier': 'legendary'})
        self.assertEqual(res.status_code, 400)
        self.company.refresh_from_db()
        self.assertEqual(self.company.tier, 'core')

    def test_identity_fields_are_not_editable(self):
        res = self.patch({'company_id': 'HACKED', 'tier': 'mass'})
        self.assertEqual(res.status_code, 200, res.content)
        self.company.refresh_from_db()
        self.assertEqual(self.company.company_id, 'ALPHA-1')
        self.assertEqual(self.company.tier, 'mass')

    def test_ai_profile_survives_an_edit(self):
        self.company.company_ai_info = [
            {'name': 'Alpha Corp', 'short_desc': 's', 'known_for': 'k', 'big_desc': 'b'},
        ]
        self.company.save()
        self.patch({'industry': 'Fintech'})
        self.company.refresh_from_db()
        self.assertEqual(len(self.company.ai_info_blocks), 1)

    def test_drive_totals_are_reported_back(self):
        Drive.objects.create(
            company=self.company,
            institution=self.institution,
            title='Alpha SDE',
            total_vacancies=25,
        )
        body = self.patch({'industry': 'Fintech'}).json()
        self.assertEqual(body['company']['openings'], 25)
        self.assertEqual(body['company']['drive_count'], 1)

    def test_cannot_edit_another_institutions_company(self):
        foreign_staff = _staff('cell@beta.test', self.other)
        foreign = Company.objects.create(
            company_name='Beta Corp',
            institution=self.other,
            client=ClientProfile.objects.get(user=foreign_staff),
        )
        res = self.patch({'company_name': 'Stolen'}, company=foreign)
        self.assertEqual(res.status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.company_name, 'Beta Corp')

    def test_students_have_no_institution_and_are_rejected(self):
        student = USER_MODEL.objects.create_user(
            username='stu@test', email='stu@test', password='pw',
        )
        self.client.force_login(student)
        res = self.patch({'industry': 'Fintech'})
        self.assertEqual(res.status_code, 403)

    def test_anonymous_is_unauthorized(self):
        self.client.logout()
        res = self.patch({'industry': 'Fintech'})
        self.assertEqual(res.status_code, 401)

    def test_get_is_not_allowed(self):
        res = self.client.get(url('company-update', company_id=self.company.pk))
        self.assertEqual(res.status_code, 405)
