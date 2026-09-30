"""Renders a candidate's resume to a PDF.

Two sources feed one document: the TalentBro candidate profile (the fields the
student fills in or talks to the onboarding bot about — skills, certifications,
projects, internships, CGPA) and the LinkedIn profile scraped by Apify (about,
schools, companies, and whatever else the active actor returns). Neither source
is complete on its own, so the two are merged with the platform profile winning
on the fields the student curates by hand.

The LinkedIn side is deliberately forgiving about key names: the actors disagree
with each other and drift between versions, so every field is read through a list
of aliases and a section that is missing is simply left off the page rather than
printed as an empty heading.
"""

from collections import namedtuple
from io import BytesIO
import unicodedata

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# One line of an experience/education/project entry. `meta` is the short right
# hand fragment (dates, CGPA), `subtitle` the second line, `bullets` the body.
Entry = namedtuple('Entry', 'title meta subtitle bullets')
Section = namedtuple('Section', 'heading entries')

ACCENT = colors.HexColor('#1f2937')
MUTED = colors.HexColor('#4b5563')
RULE = colors.HexColor('#d1d5db')

PAGE_MARGIN = 14 * mm

# Usable width inside the margins, which is what the entry title/date columns
# have to share.
CONTENT_WIDTH = A4[0] - 2 * PAGE_MARGIN

# Anything shorter than this is treated as a placeholder rather than real content.
# The logged-out LinkedIn actor in particular returns degree "-" for most entries.
_MIN_MEANINGFUL_LENGTH = 2

# The PDF is drawn in the built-in Helvetica, which is WinAnsi-only, so any
# character outside it renders as a blank or a black box. Scraped LinkedIn text
# is full of curly quotes, ellipses and the occasional emoji, so it is folded
# down to plain ASCII before it reaches the page.
_TYPOGRAPHIC = {
    '‘': "'", '’': "'", '‚': "'", '‛': "'",
    '“': '"', '”': '"', '„': '"',
    '–': '-', '—': '-', '−': '-',
    '…': '...', '·': '-', '•': '*', '●': '*',
    ' ': ' ', ' ': ' ', ' ': ' ', '': '',
    '→': '->', '←': '<-', '≤': '<=', '≥': '>=',
    '✓': 'Yes', '✔': 'Yes', '❤': '', '⭐': '',
}


def _fold(text):
    """Best-effort conversion of arbitrary Unicode to printable ASCII."""
    if not text:
        return ''
    out = []
    for char in str(text):
        if char in _TYPOGRAPHIC:
            out.append(_TYPOGRAPHIC[char])
            continue
        # Drop accents (é -> e) but keep the base letter.
        decomposed = unicodedata.normalize('NFKD', char)
        out.append(''.join(c for c in decomposed if not unicodedata.combining(c)))
    folded = ''.join(out)
    # Anything still outside ASCII (CJK, emoji, symbols) is dropped rather than
    # printed as a missing-glyph box.
    return ''.join(c if 32 <= ord(c) < 127 else ' ' for c in folded).strip()


def _esc(value):
    """Escape a value for reportlab's mini-HTML paragraph markup."""
    if value is None:
        return ''
    text = _fold(value)
    for needle, replacement in (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;')):
        text = text.replace(needle, replacement)
    return text


def _clean(value):
    """A trimmed string, or '' when the value is unusable filler.

    Actors and the onboarding bot both write "-" or "N/A" to mean "no value", and
    those must not reach the page.
    """
    if value is None:
        return ''
    text = _fold(value)
    if len(text) < _MIN_MEANINGFUL_LENGTH or text in {'-', '--', 'N/A', 'n/a', 'NA'}:
        return ''
    return text


def _first(source, *keys):
    """The first non-empty scalar value among ``keys`` of a dict, or ''.

    LinkedIn entries are dicts whose field names shift between actors; the
    platform's own projects/internships are dicts written by the onboarding bot
    with looser names still. Reading them through an alias list keeps that
    variety out of the layout code. Only for scalar fields — see ``_list`` for
    the list-valued ones.
    """
    if not isinstance(source, dict):
        return ''
    for key in keys:
        value = source.get(key)
        if isinstance(value, (dict, list, tuple, set)):
            continue
        text = _clean(value)
        if text:
            return text
    return ''


def _list(source, *keys):
    """The first list-valued entry among ``keys`` of a dict, as a list.

    ``_first`` would stringify a list field into its repr, which then printed the
    raw scraped dict onto the page, so list fields are read through here instead.
    """
    if not isinstance(source, dict):
        return []
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return [item for item in value if item not in (None, '', [], {})]
        if isinstance(value, dict):
            return [value]
        text = _clean(value)
        if text:
            return [text]
    return []


def _as_items(value):
    """A list of entries from a field that may be a list, a string or empty."""
    if isinstance(value, list):
        return [item for item in value if item not in (None, '', [], {})]
    text = _clean(value)
    return [text] if text else []


def _bullets(source, *keys):
    """Bullet lines from the first matching key, split on newlines or semicolons."""
    if isinstance(source, str):
        parts = [source]
    elif isinstance(source, dict):
        raw = _first(source, *keys)
        parts = [raw] if raw else []
    elif isinstance(source, (list, tuple)):
        parts = [str(item) for item in source]
    else:
        parts = []

    bullets = []
    for part in parts:
        for line in str(part).replace(';', '\n').splitlines():
            line = line.strip().lstrip('-•*').strip()
            if line:
                bullets.append(line)
    return bullets


# --- LinkedIn mapping -------------------------------------------------------

_LI_EXPERIENCE = (
    ('title', 'position', 'positionTitle', 'title', 'jobTitle', 'role', 'occupation'),
    ('companyName', 'company', 'organization', 'companyName', 'organisation', 'employer'),
)

_LI_EDUCATION = (
    ('schoolName', 'school', 'university', 'institution', 'schoolName'),
    ('degree', 'degreeName', 'fieldOfStudy', 'studyField', 'discipline', 'faculty'),
)

_LI_CERT = ('name', 'title', 'certification', 'credential')

_LI_PROJECT = ('name', 'title', 'project')

_LI_GENERIC = (
    ('name', 'title', 'label'),
    ('issuedBy', 'organization', 'company', 'issuer', 'school', 'publisher'),
)


def _linkedin_experiences(item):
    entries = []
    for raw in _list(item, 'experience', 'experiences', 'positionGroups'):
        if isinstance(raw, str):
            entries.append(Entry(title=raw, meta='', subtitle='', bullets=[]))
            continue
        title = _first(raw, *_LI_EXPERIENCE[0])
        company = _first(raw, *_LI_EXPERIENCE[1])
        # The logged-out actor returns only the company, so fall back to it for the
        # headline rather than printing a bullet with no title.
        headline = title or company
        if not headline:
            continue
        meta = _clean(raw.get('dateRange')) or ' '.join(
            part for part in (
                _first(raw, 'startDate')[:4], _first(raw, 'endDate')[:4],
            ) if part
        )
        # Only name the company separately when there is a distinct role above it.
        subtitle = company if (title and company and company != title) else ''
        entries.append(Entry(
            title=headline,
            meta=meta,
            subtitle=subtitle,
            bullets=_bullets(raw, 'description', 'descriptionText', 'summary'),
        ))
    return entries


def _linkedin_educations(item):
    entries = []
    for raw in _list(item, 'education', 'educations', 'educationsList'):
        if isinstance(raw, str):
            entries.append(Entry(title=raw, meta='', subtitle='', bullets=[]))
            continue
        school = _first(raw, *_LI_EDUCATION[0])
        degree = _first(raw, *_LI_EDUCATION[1])
        if not school and not degree:
            continue
        meta = _clean(raw.get('dateRange')) or ' '.join(
            part for part in (
                _first(raw, 'startDate')[:4], _first(raw, 'endDate')[:4],
            ) if part
        )
        entries.append(Entry(
            title=degree or school,
            meta=meta,
            # Don't repeat the school underneath itself when the actor gave no
            # degree, which is the common case for the logged-out scraper.
            subtitle=school if (degree and school != degree) else '',
            bullets=_bullets(raw, 'description', 'fieldOfStudy'),
        ))
    return entries


def _linkedin_simple_section(item, aliases, title_keys, meta_keys, limit=None):
    """A section of uniformly shaped LinkedIn entries (certs, projects, awards)."""
    entries = []
    for raw in _list(item, *aliases):
        if isinstance(raw, str):
            entries.append(Entry(title=raw, meta='', subtitle='', bullets=[]))
            continue
        title = _first(raw, *title_keys)
        if not title:
            continue
        entries.append(Entry(
            title=title,
            meta='',
            subtitle=_first(raw, *meta_keys),
            bullets=_bullets(raw, 'description', 'summary'),
        ))
        if limit is not None and len(entries) >= limit:
            break
    return entries


def _linkedin_languages(item):
    entries = []
    for raw in _list(item, 'languages', 'languageList'):
        if isinstance(raw, str):
            entries.append(Entry(title=raw, meta='', subtitle='', bullets=[]))
            continue
        name = _first(raw, 'language', 'name')
        if not name:
            continue
        entries.append(Entry(
            title=name,
            meta=_first(raw, 'proficiency', 'level'),
            subtitle='',
            bullets=[],
        ))
    return entries


# --- Platform profile mapping -----------------------------------------------

_PLATFORM_INTERNSHIP = (
    ('company', 'org', 'organisation', 'title', 'name'),
    ('role', 'position', 'designation', 'title', 'name'),
)

_PLATFORM_PROJECT = (
    ('title', 'name', 'project'),
    ('tech', 'stack', 'technologies', 'tools'),
)

_PLATFORM_CERT = ('name', 'title', 'certification', 'issuer', 'organization')


def _platform_entries(values, title_keys, subtitle_keys, description_keys):
    entries = []
    for raw in _as_items(values):
        if isinstance(raw, str):
            entries.append(Entry(title=raw, meta='', subtitle='', bullets=[]))
            continue
        title = _first(raw, *title_keys)
        if not title:
            continue
        subtitle = _first(raw, *subtitle_keys)
        entries.append(Entry(
            title=title,
            meta=_first(raw, 'duration', 'period', 'dateRange', 'year'),
            subtitle=subtitle if subtitle != title else '',
            bullets=_bullets(raw, *description_keys),
        ))
    return entries


def _word_entries(values):
    """Plain strings (skills, activities) rendered as a comma-joined line."""
    words = []
    for raw in _as_items(values):
        text = _clean(raw) if isinstance(raw, str) else _first(raw, 'name', 'title')
        if text:
            words.append(text)
    return [Entry(title=', '.join(words), meta='', subtitle='', bullets=[])] if words else []


def _merge(*groups):
    """Concatenate entry groups, dropping duplicates that a shared value produced.

    A candidate whose LinkedIn college is also their TalentBro college should see
    it once, so identical (title, meta, subtitle) triples collapse.
    """
    seen = set()
    out = []
    for group in groups:
        for entry in group:
            key = (entry.title, entry.meta, entry.subtitle)
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
    return out


# --- Document ---------------------------------------------------------------

def _styles():
    body = ParagraphStyle(
        'Body', fontName='Helvetica', fontSize=9, leading=12, textColor=colors.black,
    )
    return {
        'name': ParagraphStyle(
            'Name', parent=body, fontName='Helvetica-Bold', fontSize=18, leading=21,
            textColor=ACCENT, spaceAfter=1,
        ),
        'headline': ParagraphStyle(
            'Headline', parent=body, fontSize=10, leading=13, textColor=MUTED,
            spaceAfter=3,
        ),
        'contact': ParagraphStyle(
            'Contact', parent=body, fontSize=8.5, leading=11, textColor=MUTED,
        ),
        'heading': ParagraphStyle(
            'Heading', parent=body, fontName='Helvetica-Bold', fontSize=10.5,
            leading=13, textColor=ACCENT,
        ),
        'entry_title': ParagraphStyle(
            'EntryTitle', parent=body, fontName='Helvetica-Bold', fontSize=9.5, leading=12,
        ),
        'entry_meta': ParagraphStyle(
            'EntryMeta', parent=body, fontSize=8.5, leading=12, textColor=MUTED,
            alignment=TA_RIGHT,
        ),
        'entry_subtitle': ParagraphStyle(
            'EntrySubtitle', parent=body, fontSize=9, leading=12, textColor=MUTED,
        ),
        'bullet': ParagraphStyle(
            'Bullet', parent=body, leftIndent=9, bulletIndent=1, spaceAfter=1,
        ),
        'summary': ParagraphStyle(
            'Summary', parent=body, fontSize=9, leading=12, spaceAfter=2,
        ),
    }


def _section_flowables(section, styles, content_width):
    out = [
        Paragraph(_esc(section.heading.upper()), styles['heading']),
        HRFlowable(
            width='100%', thickness=0.6, color=RULE,
            spaceBefore=1, spaceAfter=4,
        ),
    ]
    # The date/CGPA column is fixed and the title takes the rest, so a long job
    # title wraps instead of pushing its own date off the page.
    meta_width = 42 * mm
    for entry in section.entries:
        block = []
        if entry.meta:
            row = Table(
                [[
                    Paragraph(_esc(entry.title), styles['entry_title']),
                    Paragraph(_esc(entry.meta), styles['entry_meta']),
                ]],
                colWidths=[content_width - meta_width, meta_width],
            )
            row.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            block.append(row)
        else:
            block.append(Paragraph(_esc(entry.title), styles['entry_title']))
        if entry.subtitle:
            block.append(Paragraph(_esc(entry.subtitle), styles['entry_subtitle']))
        for bullet in entry.bullets:
            # The bullet glyph is drawn in the same WinAnsi font as the text, so it
            # stays a plain ASCII dash rather than a Unicode bullet.
            block.append(Paragraph(_esc(bullet), styles['bullet'], bulletText='-'))
        # Keep an entry whole rather than letting a page break land mid-way through
        # one, but allow the break if the entry is taller than a page on its own.
        out.append(KeepTogether(block))
    out.append(Spacer(1, 5))
    return out


def render_resume_pdf(candidate, linkedin=None):
    """Build the resume PDF and return its bytes.

    ``candidate`` is a dict of the platform profile (as produced by
    ``_candidate_profile_data``), ``linkedin`` the raw Apify dataset item or None
    when the scrape was unavailable. A missing or empty section is omitted, so a
    thin profile yields a short page rather than a page of blank headings.
    """
    candidate = candidate or {}
    linkedin = linkedin if isinstance(linkedin, dict) else {}
    styles = _styles()
    doc = SimpleDocTemplate(
        BytesIO(),
        pagesize=A4,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=PAGE_MARGIN,
        title='Resume',
        author=_clean(candidate.get('full_name')) or 'Candidate',
    )

    # --- header ---
    name = (
        _clean(candidate.get('full_name'))
        or _clean(linkedin.get('fullName'))
        or 'Your Name'
    )
    headline = (
        _clean(candidate.get('bio'))
        or _clean(linkedin.get('headline'))
        or _clean(linkedin.get('subtitle'))
    )

    contact_bits = [
        _clean(candidate.get('personal_email')) or _clean(candidate.get('email')),
        _clean(candidate.get('phone')),
        _clean(linkedin.get('location')),
        _clean(candidate.get('linkedin_url')),
        _clean(candidate.get('github_url')),
        _clean(candidate.get('portfolio_url')),
    ]
    contact = '  |  '.join(bit for bit in contact_bits if bit)

    story = [Paragraph(_esc(name), styles['name'])]
    if headline:
        story.append(Paragraph(_esc(headline), styles['headline']))
    if contact:
        story.append(Paragraph(_esc(contact), styles['contact']))
    story.append(Spacer(1, 7))

    # --- summary ---
    about = _clean(linkedin.get('about'))
    if about:
        story.append(Paragraph('SUMMARY', styles['heading']))
        story.append(HRFlowable(
            width='100%', thickness=0.6, color=RULE, spaceBefore=1, spaceAfter=3,
        ))
        story.append(Paragraph(_esc(about), styles['summary']))
        story.append(Spacer(1, 5))

    # --- platform education, when the student filled it in ---
    college = _clean(candidate.get('college'))
    department = _clean(candidate.get('department'))
    program = _clean(candidate.get('program'))
    years = ' - '.join(
        str(year) for year in (candidate.get('start_year'), candidate.get('end_year')) if year
    )
    cgpa = candidate.get('cgpa')
    platform_education = []
    if college or department or program:
        title = program or department or college
        # Keep the school/department underneath, but never repeat the title there.
        subtitle = ' | '.join(
            part for part in (college, department, program) if part and part != title
        )
        meta = ' | '.join(part for part in (
            years,
            f'CGPA {cgpa}' if cgpa not in (None, '') else '',
        ) if part)
        platform_education.append(Entry(
            title=title, meta=meta, subtitle=subtitle, bullets=[],
        ))

    # LinkedIn's `articles` key is the logged-out actor's name for published posts,
    # of which a profile can have dozens. A resume lists the strongest few.
    publications = _linkedin_simple_section(
        linkedin, ('publications', 'publicationList', 'articles'),
        ('title', 'name', 'headline', 'publication'), _LI_GENERIC[1], limit=4,
    )

    sections = [
        Section('Education', _merge(
            platform_education,
            _linkedin_educations(linkedin),
        )),
        Section('Experience', _merge(
            _platform_entries(
                candidate.get('internships'),
                _PLATFORM_INTERNSHIP[0], _PLATFORM_INTERNSHIP[1],
                ('description', 'summary', 'work'),
            ),
            _linkedin_experiences(linkedin),
        )),
        Section('Projects', _merge(
            _platform_entries(
                candidate.get('projects'),
                _PLATFORM_PROJECT[0], _PLATFORM_PROJECT[1],
                ('description', 'link', 'url'),
            ),
            _linkedin_simple_section(
                linkedin, ('projects', 'projectsList'), _LI_PROJECT, _LI_GENERIC[1],
            ),
        )),
        Section('Skills', _merge(
            _word_entries(candidate.get('skills')),
            _word_entries(_list(linkedin, 'skills', 'skillsList')),
        )),
        Section('Certifications', _merge(
            _platform_entries(
                candidate.get('certifications'),
                _PLATFORM_CERT, _PLATFORM_CERT, ('description', 'link', 'url'),
            ),
            _linkedin_simple_section(
                linkedin, ('certifications', 'certificationsList'), _LI_CERT, _LI_GENERIC[1],
            ),
        )),
        Section('Extracurricular Activities', _merge(
            _word_entries(candidate.get('extracurricular_activities')),
        )),
        Section('Languages', _merge(_linkedin_languages(linkedin))),
        Section('Publications', _merge(publications)),
        Section('Honors & Awards', _merge(
            _linkedin_simple_section(
                linkedin, ('honors', 'honorsList', 'awards'),
                _LI_GENERIC[0], _LI_GENERIC[1], limit=6,
            ),
        )),
        Section('Volunteering', _merge(
            _linkedin_simple_section(
                linkedin, ('volunteerExperience', 'volunteerExperiences', 'volunteering'),
                ('title', 'role', 'organization'), _LI_GENERIC[1], limit=6,
            ),
        )),
        Section('Courses', _merge(
            _linkedin_simple_section(
                linkedin, ('courses', 'coursesList'), ('name', 'title'), _LI_GENERIC[1],
                limit=6,
            ),
        )),
    ]

    for section in sections:
        if section.entries:
            story.extend(_section_flowables(section, styles, CONTENT_WIDTH))

    doc.build(story)
    return doc.filename.getvalue()
