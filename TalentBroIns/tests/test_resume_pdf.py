"""Tests for the resume PDF renderer.

The renderer merges two sources whose field names are neither stable nor agreed
on: the LinkedIn actors rename keys between versions, and the platform's own
projects/internships are free-form dicts written by the onboarding bot. Every
mapping is therefore driven by alias lists, and the failure mode when one of them
is wrong is silent — a section quietly vanishes, or worse, a raw scraped dict
gets printed on the page. These tests pin the mappings down.
"""

from io import BytesIO
from unittest import skipUnless

from django.test import SimpleTestCase

from TalentBroIns.resume_pdf import (
    _bullets,
    _clean,
    _first,
    _fold,
    _list,
    _linkedin_educations,
    _linkedin_experiences,
    _word_entries,
    render_resume_pdf,
)

PDF_MAGIC = b'%PDF-'

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - pypdf is a test-only dependency
    PdfReader = None


def _pdf_text(pdf):
    """Extract the drawn text from a PDF, for asserting on its content."""
    reader = PdfReader(BytesIO(pdf))
    return '\n'.join(page.extract_text() for page in reader.pages)


class CleanTests(SimpleTestCase):
    def test_placeholder_values_are_dropped(self):
        for value in ('-', '--', 'N/A', 'n/a', 'NA', '', '  ', None):
            self.assertEqual(_clean(value), '', value)

    def test_real_values_survive(self):
        self.assertEqual(_clean('  Python  '), 'Python')
        self.assertEqual(_clean('Go'), 'Go')

    def test_non_string_scalars_are_accepted(self):
        self.assertEqual(_clean(9.4), '9.4')


class FoldTests(SimpleTestCase):
    def test_typographic_characters_become_ascii(self):
        # The built-in PDF fonts are WinAnsi-only, so anything outside it renders
        # as a blank or a black box.
        self.assertEqual(_fold('it’s fine'), "it's fine")
        self.assertEqual(_fold('wait…'), 'wait...')
        self.assertEqual(_fold('a – b — c'), 'a - b - c')
        self.assertEqual(_fold('“quoted”'), '"quoted"')

    def test_accents_are_folded_but_letters_kept(self):
        self.assertEqual(_fold('José García'), 'Jose Garcia')

    def test_characters_outside_latin_are_dropped(self):
        self.assertEqual(_fold('Python 日本語'), 'Python')

    def test_fold_leaves_plain_ascii_untouched(self):
        self.assertEqual(_fold('Senior Software Engineer'), 'Senior Software Engineer')


class ScalarLookupTests(SimpleTestCase):
    def test_first_skips_a_missing_key(self):
        self.assertEqual(_first({'b': 'second'}, 'a', 'b'), 'second')

    def test_first_never_stringifies_a_list(self):
        # This returned the repr of the list once, which printed a raw scraped
        # dict straight onto the page.
        self.assertEqual(_first({'experience': [{'company': 'Microsoft'}]}, 'experience'), '')

    def test_first_never_stringifies_a_dict(self):
        self.assertEqual(_first({'company': {'name': 'X'}}, 'company'), '')

    def test_list_returns_the_list(self):
        self.assertEqual(
            _list({'experience': [{'company': 'Microsoft'}]}, 'experience'),
            [{'company': 'Microsoft'}],
        )

    def test_list_wraps_a_single_dict(self):
        self.assertEqual(_list({'x': {'a': 1}}, 'x'), [{'a': 1}])

    def test_list_wraps_a_bare_string(self):
        self.assertEqual(_list({'x': 'solo'}, 'x'), ['solo'])

    def test_list_drops_empty_entries(self):
        self.assertEqual(_list({'x': [{'a': 1}, None, '', {}]}, 'x'), [{'a': 1}])

    def test_list_on_a_non_dict_is_empty(self):
        self.assertEqual(_list('nope', 'x'), [])


class BulletTests(SimpleTestCase):
    def test_splits_on_newlines(self):
        self.assertEqual(_bullets('one\ntwo'), ['one', 'two'])

    def test_splits_on_semicolons(self):
        self.assertEqual(_bullets('one; two'), ['one', 'two'])

    def test_strips_existing_bullet_markers(self):
        self.assertEqual(_bullets('- one\n* two'), ['one', 'two'])

    def test_accepts_a_list(self):
        self.assertEqual(_bullets(['one', 'two']), ['one', 'two'])

    def test_missing_description_yields_nothing(self):
        self.assertEqual(_bullets({'company': 'Microsoft'}, 'description'), [])


class LinkedInMappingTests(SimpleTestCase):
    def test_experience_without_a_title_falls_back_to_the_company(self):
        # The logged-out actor returns only the company, so this is the common case.
        entries = _linkedin_experiences({'experience': [{'company': 'Microsoft'}]})
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].title, 'Microsoft')
        # With no distinct role there is nothing to say under the heading.
        self.assertEqual(entries[0].subtitle, '')

    def test_experience_names_the_company_under_a_real_role(self):
        entries = _linkedin_experiences({
            'experience': [{'title': 'Programmer', 'company': 'Microsoft',
                            'startDate': '1974-06', 'endDate': '1974-09'}],
        })
        self.assertEqual(entries[0].title, 'Programmer')
        self.assertEqual(entries[0].subtitle, 'Microsoft')
        self.assertEqual(entries[0].meta, '1974 1974')

    def test_experience_reads_the_plural_key_too(self):
        entries = _linkedin_experiences({'experiences': [{'company': 'Acme'}]})
        self.assertEqual(len(entries), 1)

    def test_education_does_not_repeat_the_school_as_a_subtitle(self):
        # The actor returns degree "-" for most entries, so there is often no
        # degree to show and the school must not be printed twice.
        entries = _linkedin_educations({
            'education': [{'school': 'Harvard University', 'degree': '-',
                           'dateRange': '1973 - 1975'}],
        })
        self.assertEqual(entries[0].title, 'Harvard University')
        self.assertEqual(entries[0].subtitle, '')
        self.assertEqual(entries[0].meta, '1973 - 1975')

    def test_education_puts_the_degree_on_top_when_present(self):
        entries = _linkedin_educations({
            'education': [{'school': 'MIT', 'degree': 'B.S. Computer Science',
                           'startDate': 2018, 'endDate': 2022}],
        })
        self.assertEqual(entries[0].title, 'B.S. Computer Science')
        self.assertEqual(entries[0].subtitle, 'MIT')
        self.assertEqual(entries[0].meta, '2018 2022')

    def test_an_entry_with_nothing_usable_is_dropped(self):
        self.assertEqual(_linkedin_experiences({'experience': [{}]}), [])
        self.assertEqual(_linkedin_educations({'education': [{'degree': '-'}]}), [])

    def test_a_bare_string_entry_is_kept_as_a_title(self):
        entries = _linkedin_experiences({'experience': ['Some Company']})
        self.assertEqual(entries[0].title, 'Some Company')

    def test_word_entries_joins_into_one_line(self):
        self.assertEqual(
            _word_entries(['Python', 'DSA'])[0].title, 'Python, DSA',
        )

    def test_word_entries_handles_dicts_too(self):
        self.assertEqual(_word_entries([{'name': 'Python'}])[0].title, 'Python')

    def test_word_entries_of_nothing_is_empty(self):
        self.assertEqual(_word_entries([]), [])


class RenderTests(SimpleTestCase):
    CANDIDATE = {
        'full_name': 'Bill Gates',
        'phone': '+91 98765 43210',
        'college': 'Harvard University',
        'department': 'Computer Science',
        'cgpa': 9.4,
        'skills': ['Python', 'DSA'],
    }

    LINKEDIN = {
        'fullName': 'Bill Gates',
        'about': 'Chair of the Gates Foundation.',
        'location': 'Seattle, United States',
        'experience': [{'company': 'Microsoft'}],
        'education': [{'school': 'Harvard University', 'degree': '-'}],
    }

    def test_produces_a_pdf(self):
        pdf = render_resume_pdf(self.CANDIDATE, self.LINKEDIN)
        self.assertTrue(pdf.startswith(PDF_MAGIC))
        self.assertGreater(len(pdf), 1000)

    def test_renders_with_no_linkedin_data(self):
        self.assertTrue(render_resume_pdf(self.CANDIDATE, None).startswith(PDF_MAGIC))

    def test_renders_an_almost_empty_profile(self):
        # A candidate who has just signed up still gets a file to download, rather
        # than an error they cannot act on.
        self.assertTrue(render_resume_pdf({}, {}).startswith(PDF_MAGIC))
        self.assertTrue(render_resume_pdf(None, None).startswith(PDF_MAGIC))

    def test_unrepresentable_text_cannot_break_the_fonts(self):
        # The built-in fonts are WinAnsi-only, so these are the inputs that once
        # rendered as black boxes or raised mid-draw. Written as escapes so the
        # test does not depend on how the source file itself is decoded.
        pdf = render_resume_pdf(
            {'full_name': ' R\xe9sum\xe9 \u2728'},
            {'about': 'Jos\xe9 Garc\xeda \u2014 \u2026 \u201cquoted\u201d '
                      '\u65e5\u672c\u8a9e \U0001f680'},
        )
        self.assertTrue(pdf.startswith(PDF_MAGIC))

    def test_a_very_long_profile_does_not_lose_its_header(self):
        pdf = render_resume_pdf(
            {'full_name': 'Bill Gates', 'skills': ['skill-%d' % i for i in range(120)]},
            {'about': 'about ' * 400, 'experience': [{'company': 'C%d' % i} for i in range(40)]},
        )
        self.assertTrue(pdf.startswith(PDF_MAGIC))


@skipUnless(PdfReader, 'pypdf is not installed')
class RenderedTextTests(SimpleTestCase):
    """Assertions on what actually reached the page.

    These need text extraction, which needs pypdf. Everything above checks the
    mapping without it, so a missing test dependency skips only this class.
    """

    CANDIDATE = {
        'full_name': 'Bill Gates',
        'phone': '+91 98765 43210',
        'college': 'Harvard University',
        'department': 'Computer Science',
        'cgpa': 9.4,
        'skills': ['Python', 'DSA'],
        'projects': [{'title': 'TalentBro', 'tech': 'Django',
                      'description': 'Placement platform.'}],
    }

    LINKEDIN = {
        'fullName': 'Bill Gates',
        'about': 'Chair of the Gates Foundation.',
        'location': 'Seattle, United States',
        'experience': [{'company': 'Microsoft'}],
        'education': [{'school': 'Harvard University', 'degree': '-'}],
    }

    def test_never_leaks_a_raw_scraped_dict(self):
        """The regression this renderer exists to prevent."""
        text = _pdf_text(render_resume_pdf(self.CANDIDATE, self.LINKEDIN))
        self.assertNotIn('companyUrl', text)
        self.assertNotIn('dateRange', text)
        self.assertNotIn('startDate', text)
        self.assertNotIn("'school'", text)

    def test_includes_content_from_both_sources(self):
        text = _pdf_text(render_resume_pdf(self.CANDIDATE, self.LINKEDIN))
        # From the platform profile.
        self.assertIn('Bill Gates', text)
        self.assertIn('Python, DSA', text)
        self.assertIn('TalentBro', text)
        # From the LinkedIn scrape.
        self.assertIn('Chair of the Gates Foundation.', text)
        self.assertIn('Microsoft', text)
        self.assertIn('Seattle', text)

    def test_empty_sections_are_omitted_rather_than_blank_headings(self):
        text = _pdf_text(render_resume_pdf({'full_name': 'Solo'}, {}))
        for heading in ('CERTIFICATIONS', 'LANGUAGES', 'PUBLICATIONS', 'HONORS'):
            self.assertNotIn(heading, text)
