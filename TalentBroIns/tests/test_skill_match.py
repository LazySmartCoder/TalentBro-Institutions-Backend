"""Tests for the candidate-side match figure on each drive card.

The percentage answers "how much of this drive's ask is already satisfied by my
profile", so the four things worth pinning down are:

* what counts as a match. Recruiters and students spell the same skill
  differently ("React JS" / "ReactJS", "Node.js" / "Node"), and matching has to
  survive that without turning "java" into a hit for "javascript".
* the weighting. Required skills are the bar, so clearing all of them must still
  read as a strong match even with none of the preferred ones.
* the fallback. Most drives never fill in a skill list at all, so a drive with no
  skills has to fall back to the branch/course/CGPA bar its company declares -
  and must say which of the two it measured, so the card can label it honestly.
* the empty cases. No skills on the drive and no bar on the company, or none on
  the profile, must not be reported as 0% - that reads as a rejection rather than
  as missing data.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from TalentBroIns.models import (
    CandidateProfile,
    ClientProfile,
    Company,
    Drive,
    Institution,
)

USER_MODEL = get_user_model()
NAMESPACE = 'TalentBroIns'


def url(name, **kwargs):
    return reverse(f'{NAMESPACE}:{name}', kwargs=kwargs)


def _college(name='Alpha Institute'):
    owner = USER_MODEL.objects.create_user(
        email=f'owner@{name.split()[0].lower()}.test',
        username=f'owner-{name.split()[0].lower()}',
        password='pw',
    )
    college = Institution.objects.create(
        user=owner,
        name=name,
        institution_type='College',
        email_domain=f'{name.split()[0].lower()}.test',
        address='1 College Road',
        city='Bengaluru',
        state='Karnataka',
        pin_code='560001',
        placement_department_name='Placement Cell',
        placement_office_email=f'placement@{name.split()[0].lower()}.test',
        approximate_student_strength=1000,
    )
    # A Company is always recorded by a member of the placement cell, so the
    # college needs an officer before any company can be attached to it.
    officer = USER_MODEL.objects.create_user(
        email=f'cell@{name.split()[0].lower()}.test',
        username=f'cell-{name.split()[0].lower()}',
        password='pw',
    )
    ClientProfile.objects.create(user=officer, institution=college)
    return college


def _student(college, skills=(), slug='a', *, department='Computer Science',
             program='B.Tech', cgpa=None):
    user = USER_MODEL.objects.create_user(
        username=f'stu-{slug}-{college.pk}@test', email=f'stu-{slug}-{college.pk}@test',
        password='pw',
    )
    CandidateProfile.objects.create(
        user=user, college=college, first_name='Asha', last_name='Rao',
        department=department, program=program, cgpa=cgpa, skills=list(skills),
    )
    return user


def _officer(college):
    """The placement-cell account that recorded this college's companies."""
    return ClientProfile.objects.get(institution=college).user


def _company(college, name='Acme', **overrides):
    fields = {
        'institution': college,
        'client': ClientProfile.objects.filter(institution=college).first(),
        'company_name': f'{name}-{college.pk}',
    }
    fields.update(overrides)
    return Company.objects.create(**fields)


def _drive(company, *, required=(), preferred=(), branches=(), courses=(),
           minimum_cgpa=None):
    return Drive.objects.create(
        institution=company.institution, company=company,
        title='SDE hire', role='SDE',
        required_skills=list(required), preferred_skills=list(preferred),
        eligible_branches=list(branches), eligible_courses=list(courses),
        minimum_cgpa=minimum_cgpa,
    )


class SkillMatchTests(TestCase):
    def setUp(self):
        self.college = _college()
        self.company = _company(self.college)
        self.user = _student(self.college, skills=['Python', 'SQL', 'React JS'])
        self.client.force_login(self.user)

    def _detail(self):
        response = self.client.get(
            url('candidate-company-drive-detail', company_id=self.company.pk)
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def _match_for(self, drive):
        row = next(d for d in self._detail()['drives'] if d['drive_id'] == drive.pk)
        return (
            row['profile_match'], row['matched_skills'],
            row['required_skill_count'], row['match_basis'],
        )

    def test_full_required_match_reads_as_strong(self):
        drive = _drive(
            self.company,
            required=['Python', 'SQL'],
            preferred=['Kubernetes', 'GraphQL'],
        )
        # Every required skill covered, none of the preferred: 3:1 weighting puts
        # this at 75%, which should not read as a weak match.
        percent, matched, required_total, basis = self._match_for(drive)
        self.assertEqual(percent, 75)
        self.assertEqual(sorted(matched), ['Python', 'SQL'])
        self.assertEqual(required_total, 2)
        self.assertEqual(basis, 'skills')

    def test_partial_match_is_proportional(self):
        drive = _drive(self.company, required=['Python', 'SQL', 'Java', 'Docker'])
        # 2 of 4 required, no preferred listed so the required group carries the
        # whole score.
        percent, matched, required_total, basis = self._match_for(drive)
        self.assertEqual(percent, 50)
        self.assertEqual(sorted(matched), ['Python', 'SQL'])
        self.assertEqual(required_total, 4)
        self.assertEqual(basis, 'skills')

    def test_no_required_skills_scores_on_preferred_alone(self):
        drive = _drive(self.company, preferred=['Python', 'SQL', 'Java'])
        # 2 of 3 preferred, and with no required group the preferred share is the
        # whole score rather than being diluted by an empty required list.
        percent, _matched, required_total, basis = self._match_for(drive)
        self.assertEqual(percent, 67)
        self.assertEqual(required_total, 0)
        self.assertEqual(basis, 'skills')

    def test_spelling_variants_still_count_as_a_match(self):
        drive = _drive(self.company, required=['ReactJS', 'Node.js'])
        # The profile lists "React JS"; punctuation and spacing are normalised
        # away before comparing.
        percent, matched, _total, basis = self._match_for(drive)
        self.assertEqual(matched, ['ReactJS'])
        self.assertEqual(percent, 50)
        self.assertEqual(basis, 'skills')

    def test_unrelated_skill_does_not_match_a_different_one(self):
        drive = _drive(self.company, required=['JavaScript'])
        # "Python"/"SQL"/"React JS" are on the profile; none of them may be
        # counted towards a JavaScript requirement.
        percent, matched, _total, basis = self._match_for(drive)
        self.assertEqual(matched, [])
        self.assertEqual(percent, 0)
        self.assertEqual(basis, 'skills')

    def test_drive_with_no_skills_falls_back_to_the_company_bar(self):
        """A recruiter who never filled in a skill list still gets a real figure.

        The seeded L&T drive is exactly this case: no skills, but a standing
        branch/course/CGPA bar on the company.
        """
        self.company.eligible_branches = ['Computer Science']
        self.company.eligible_courses = ['B.Tech']
        self.company.minimum_cgpa = Decimal('7.00')
        self.company.save()
        drive = _drive(self.company)
        # Branch and course match, and the profile has no CGPA recorded, so the
        # CGPA bar is a miss: 2 of 3.
        percent, matched, required_total, basis = self._match_for(drive)
        self.assertEqual(basis, 'eligibility')
        self.assertEqual(percent, 67)
        self.assertEqual(matched, [])
        self.assertEqual(required_total, 0)

    def test_drive_declaration_overrides_the_company_bar(self):
        self.company.eligible_branches = ['Civil']
        self.company.minimum_cgpa = Decimal('8.00')
        self.company.save()
        # The drive names the branches this recruiter actually wants, which
        # replace the company's standing list rather than adding to it.
        drive = _drive(self.company, branches=['Computer Science'])
        profile = CandidateProfile.objects.get(user=self.user)
        profile.cgpa = Decimal('8.20')
        profile.save(update_fields=['cgpa'])
        percent, _matched, _total, basis = self._match_for(drive)
        self.assertEqual(basis, 'eligibility')
        # Branch and CGPA both clear. Had the company's Civil list been used
        # instead of the drive's, this would have been 50%.
        self.assertEqual(percent, 100)

    def test_a_drive_level_cgpa_bar_overrides_the_company_one(self):
        self.company.minimum_cgpa = Decimal('9.00')
        self.company.save()
        # The drive lowers the bar to 7.00, and the same profile that failed the
        # company's 9.00 now clears this drive.
        drive = _drive(self.company, minimum_cgpa=Decimal('7.00'))
        profile = CandidateProfile.objects.get(user=self.user)
        profile.cgpa = Decimal('8.20')
        profile.save(update_fields=['cgpa'])
        percent, _matched, _total, basis = self._match_for(drive)
        self.assertEqual(basis, 'eligibility')
        self.assertEqual(percent, 100)

    def test_declared_skills_beat_the_eligibility_bar(self):
        """Skills are the sharper signal, so they win when a drive lists both."""
        self.company.eligible_branches = ['Civil']
        self.company.save()
        drive = _drive(self.company, required=['Python'])
        percent, _matched, _total, basis = self._match_for(drive)
        self.assertEqual(basis, 'skills')
        self.assertEqual(percent, 100)

    def test_an_undeclared_criterion_is_skipped_not_counted_as_a_pass(self):
        self.company.minimum_cgpa = Decimal('7.00')
        self.company.save()
        drive = _drive(self.company)
        # No branches and no courses recorded anywhere, so only the CGPA bar is
        # measured. A drive that did not name branches is not a drive that
        # accepts every branch.
        percent, _matched, _total, basis = self._match_for(drive)
        self.assertEqual(basis, 'eligibility')
        self.assertEqual(percent, 0)

    def test_drive_with_no_skills_and_no_bar_reports_no_match_at_all(self):
        drive = _drive(self.company)
        # Null rather than 0, and no basis either: there is nothing on the drive or
        # the company to compare against. This is the seeded ZOmato drive.
        percent, _matched, _total, basis = self._match_for(drive)
        self.assertIsNone(percent)
        self.assertIsNone(basis)

    def test_empty_profile_skills_score_zero_without_claiming_null(self):
        # Same college, so the company is visible - only the profile differs.
        bare = _student(self.college, skills=[], slug='bare')
        drive = _drive(self.company, required=['Python'])
        self.client.force_login(bare)
        percent, matched, _total, basis = self._match_for(drive)
        # The drive does ask for skills, so this is a real 0 - the student's
        # profile is empty, which is different from the drive listing nothing.
        self.assertEqual(percent, 0)
        self.assertEqual(matched, [])

    def test_one_hit_out_of_many_never_rounds_down_to_zero(self):
        drive = _drive(self.company, required=[f'Skill {i}' for i in range(200)] + ['Python'])
        percent, _matched, _total, basis = self._match_for(drive)
        # 1 of 201 rounds to 0, which would render as "no match at all" despite
        # a genuine hit, so it is floored at 1.
        self.assertEqual(percent, 1)

    def test_match_is_scoped_to_the_viewing_student(self):
        drive = _drive(self.company, required=['Python'])
        other = _student(_college('Gamma Institute'), skills=['Python'])
        self.client.force_login(other)
        response = self.client.get(
            url('candidate-company-drive-detail', company_id=self.company.pk)
        )
        # Another college's student cannot even see this company, let alone its
        # match figure.
        self.assertEqual(response.status_code, 404)


class SkillMatchListingTests(TestCase):
    def setUp(self):
        self.college = _college()
        self.company = _company(self.college)
        self.user = _student(self.college, skills=['Python'])
        self.client.force_login(self.user)

    def test_listing_endpoint_carries_the_same_figure(self):
        _drive(self.company, required=['Python', 'Go'])
        response = self.client.get(url('candidate-company-drives'))
        self.assertEqual(response.status_code, 200, response.content)
        drives = response.json()['drives']
        self.assertEqual(len(drives), 1)
        self.assertEqual(drives[0]['profile_match'], 50)
        self.assertEqual(drives[0]['matched_skills'], ['Python'])

    def test_staff_listing_does_not_leak_the_student_figure(self):
        _drive(self.company, required=['Python'])
        # profile_match describes one student's standing, so the placement-cell
        # listing - which covers the whole batch - must not carry it.
        self.client.force_login(_officer(self.college))
        response = self.client.get(url('drives-list'))
        self.assertEqual(response.status_code, 200, response.content)
        for row in response.json()['drives']:
            self.assertNotIn('profile_match', row)
            self.assertNotIn('matched_skills', row)


class SkillMatchAnonymousTests(TestCase):
    def test_anonymous_is_rejected(self):
        college = _college()
        company = _company(college)
        self.client.logout()
        self.assertEqual(
            self.client.get(url('candidate-company-drive-detail', company_id=company.pk)).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(url('candidate-company-drives')).status_code, 401,
        )