"""Read-only Coursera search scraper for the candidate /courses screen.

Coursera has no usable public JSON API any more: ``api.coursera.org/api/courses.v1``
answers 405 and the internal ``/api/search/v1/search`` route is edge-blocked
("API Route Does Not Exist"). What *is* available is the server-rendered search
page, which embeds its Apollo cache in a ``<script>`` tag as
``window.__APOLLO_STATE__``. Parsing that blob gives clean, structured results --
far more stable than parsing the rendered card markup with CSS selectors.

The one thing the search page does not carry is a human-written course
description. Rather than pay for a second request per course (12 extra requests,
~8s cold), ``description`` is assembled from the fields the page does expose, so
every part of it is still a real fact from Coursera.

Results are cached in-process for ``CACHE_TTL_SECONDS`` because the upstream page
is expensive (~2s) and rate-limits bursts of near-identical requests.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

# Replaces the empty `query={}` from the original Google Ads search URL. Anything
# the candidate might type into a future search box can be passed via `?q=`.
COURSERA_DEFAULT_QUERY = 'data science'

SEARCH_URL = 'https://www.coursera.org/search'
BASE_URL = 'https://www.coursera.org'
APOLLO_MARK = 'window.__APOLLO_STATE__'
REQUEST_TIMEOUT = 20
CACHE_TTL_SECONDS = 6 * 60 * 60
MAX_LIMIT = 24
MAX_QUERY_LENGTH = 120
MAX_LIST_ITEMS = 12
MAX_SKILLS = 10
MAX_FACET_VALUES = 8

_HEADERS = {
    # A plain browser UA: the search page is a public, server-rendered document.
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

LEVEL_LABELS = {
    'BEGINNER': 'Beginner',
    'INTERMEDIATE': 'Intermediate',
    'ADVANCED': 'Advanced',
    'MIXED': 'Mixed',
}

DURATION_LABELS = {
    'LESS_THAN_2_HOURS': 'Less than 2 hours',
    'ONE_TO_FOUR_WEEKS': '1-4 weeks',
    'ONE_TO_THREE_MONTHS': '1-3 months',
    'THREE_TO_SIX_MONTHS': '3-6 months',
    'SIX_TO_TWELVE_MONTHS': '6-12 months',
    'OVER_TWELVE_MONTHS': 'Over 12 months',
}

PRODUCT_TYPE_LABELS = {
    'COURSE': 'Course',
    'SPECIALIZATION': 'Specialization',
    'PROFESSIONAL_CERTIFICATE': 'Professional Certificate',
    'GUIDED_PROJECT': 'Guided Project',
}

BADGE_LABELS = {
    'Free Trial': 'Free trial',
    'Free': 'Free',
    'Coursera Plus': 'Coursera Plus',
    'New': 'New',
    'Enroll for Free': 'Enroll for free',
}


class CourseraScrapeError(Exception):
    """Raised when the search page cannot be fetched or parsed."""


def normalise_query(query: str | None) -> str:
    """Clamp a caller-supplied query, falling back to the default."""
    cleaned = ' '.join((query or '').split())[:MAX_QUERY_LENGTH].strip()
    return cleaned or COURSERA_DEFAULT_QUERY


def extract_apollo_state(html: str) -> dict[str, Any]:
    """Return the parsed ``window.__APOLLO_STATE__`` object from a page.

    The blob has to be sliced with a brace counter rather than up to the next
    ``;``: semicolons occur *inside* string values (e.g. module descriptions), so
    searching for the first ``;`` truncates the JSON and blows up the parse.
    """
    marker = html.find(APOLLO_MARK)
    if marker == -1:
        raise CourseraScrapeError(
            'Coursera did not include its Apollo state on the search page '
            '(the page layout may have changed).'
        )

    equals = html.find('=', marker)
    if equals == -1:
        raise CourseraScrapeError('Malformed Apollo state assignment on the Coursera page.')

    start = equals + 1
    while start < len(html) and html[start].isspace():
        start += 1

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(html)):
        char = html[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in '{[':
            depth += 1
        elif char in '}]':
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(html[start:index + 1])
                except ValueError as exc:
                    raise CourseraScrapeError(f'Could not parse the Coursera page: {exc}') from exc
                if not isinstance(parsed, dict):
                    raise CourseraScrapeError('Unexpected Apollo state shape on the Coursera page.')
                return parsed

    raise CourseraScrapeError('Unterminated Apollo state on the Coursera page.')


def _search_result(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return the PRODUCTS ``Search_Result`` payload, if present."""
    for entity in state.values():
        if not isinstance(entity, dict) or entity.get('__typename') != 'SearchResultQueries':
            continue
        for payload in entity.values():
            if not isinstance(payload, list):
                continue
            for result in payload:
                if not isinstance(result, dict) or result.get('__typename') != 'Search_Result':
                    continue
                # The same object also holds the SUGGESTIONS request; the one we
                # want is the block that actually carries product elements.
                if result.get('elements'):
                    return result
    return None


def _ordered_hits(state: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the product hits in SERP order, without duplicates."""
    hits = {
        key: value
        for key, value in state.items()
        if isinstance(value, dict) and value.get('__typename') == 'Search_ProductHit'
    }
    if not hits:
        return []

    ordered: list[dict[str, Any]] = []
    for element in result.get('elements') or []:
        ref = element.get('__ref') if isinstance(element, dict) else None
        hit = hits.get(ref) if ref else None
        if hit is not None and hit not in ordered:
            ordered.append(hit)

    # Anything the result block did not reference still belongs on the page.
    for hit in hits.values():
        if hit not in ordered:
            ordered.append(hit)
    return ordered


def _clean_list(value: Any, limit: int) -> list[str]:
    """Coerce a list-ish field into a de-duplicated list of clean strings."""
    if not isinstance(value, (list, tuple)):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _absolute_url(url: str) -> str:
    if not url:
        return ''
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return f'{BASE_URL}/{url.lstrip("/")}'


def _describe(course: dict[str, Any]) -> str:
    """Build a plain-English summary from the fields the search page provides.

    Coursera only publishes a written description on each course's own page, so
    this is assembled from real data (type, provider, level, rating, duration,
    skills) rather than invented copy.
    """
    title = course['title']
    parts: list[str] = []

    kind = course['type_label'].lower()
    provider = ', '.join(course['partners'])
    lead = f'{title} is a {kind}'
    if provider:
        lead += f' by {provider}'
    parts.append(lead.rstrip('.') + '.')

    facts: list[str] = []
    if course['level_label']:
        facts.append(course['level_label'])
    if course['rating']:
        rating = f"{course['rating']}/5"
        if course['rating_count']:
            rating += f" from {course['rating_count']:,} ratings"
        facts.append(rating)
    if course['duration_label']:
        facts.append(course['duration_label'])
    if facts:
        parts.append(' · '.join(facts) + '.')

    if course['skills']:
        skills = ', '.join(course['skills'][:5])
        more = len(course['skills']) - 5
        suffix = f', and {more} more' if more > 0 else ''
        parts.append(f"Skills you'll gain: {skills}{suffix}.")

    return ' '.join(parts)


def _resolve(state: dict[str, Any], node: Any) -> dict[str, Any]:
    """Follow an Apollo ``__ref`` pointer to its entity, if it resolves."""
    if not isinstance(node, dict):
        return {}
    ref = node.get('__ref')
    if not isinstance(ref, str):
        return node
    target = state.get(ref)
    return target if isinstance(target, dict) else {}


def _course_payload(hit: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    """Map one ``Search_ProductHit`` onto the API response shape."""
    title = str(hit.get('name') or '').strip()
    url = str(hit.get('url') or '').strip()
    if not title or not url:
        return None

    level = str(hit.get('productDifficultyLevel') or '').strip().upper()
    duration = str(hit.get('productDuration') or '').strip().upper()
    product_type = str(hit.get('productType') or '').strip().upper()

    raw_rating = hit.get('avgProductRating')
    rating = round(float(raw_rating), 1) if isinstance(raw_rating, (int, float)) else None
    raw_count = hit.get('numProductRatings')
    rating_count = int(raw_count) if isinstance(raw_count, (int, float)) else None

    badges: list[str] = []
    card = _resolve(state, hit.get('productCard'))
    for badge in _clean_list(card.get('badges'), MAX_LIST_ITEMS):
        badges.append(BADGE_LABELS.get(badge, badge))

    attributes = card.get('productTypeAttributes')
    attributes = _resolve(state, attributes) if isinstance(attributes, dict) else {}
    review_count = attributes.get('reviewCount')

    course: dict[str, Any] = {
        'id': str(hit.get('id') or '').strip(),
        'title': title,
        'description': '',
        'image': str(hit.get('imageUrl') or '').strip(),
        'course_url': _absolute_url(url),
        'tagline': str(hit.get('tagline') or '').strip(),
        'partners': _clean_list(hit.get('partners'), MAX_LIST_ITEMS),
        'partner_logos': _clean_list(hit.get('partnerLogos'), MAX_LIST_ITEMS),
        'rating': rating,
        'rating_count': rating_count,
        'review_count': (
            int(review_count) if isinstance(review_count, (int, float)) else None
        ),
        'level': level,
        'level_label': LEVEL_LABELS.get(level, ''),
        'duration': duration,
        'duration_label': DURATION_LABELS.get(duration, ''),
        'product_type': product_type,
        'type_label': PRODUCT_TYPE_LABELS.get(product_type, product_type.replace('_', ' ').title()),
        'skills': _clean_list(hit.get('skills'), MAX_SKILLS),
        'tools': _clean_list(hit.get('toolSoftwareSkillNames'), MAX_SKILLS),
        'languages': _clean_list(hit.get('fullyTranslatedLanguages'), MAX_LIST_ITEMS),
        'subtitle_languages': _clean_list(hit.get('subtitlesOnlyLanguages'), MAX_LIST_ITEMS),
        'is_free': bool(hit.get('isCourseFree')),
        'is_credit_eligible': bool(hit.get('isCreditEligible')),
        'is_new': bool(hit.get('isNewContent')),
        'in_coursera_plus': bool(hit.get('isPartOfCourseraPlus')),
        'badges': badges,
    }
    course['description'] = _describe(course)
    return course


def _facets(result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Trim the facet blocks that ride along on the same response.

    The search payload already contains per-facet value counts, so surfacing the
    top few costs no extra request. Useful context for the candidate ("most
    results here are from Coursera / Packt, mostly beginner level").
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for facet in result.get('facets') or []:
        if not isinstance(facet, dict):
            continue
        name = str(facet.get('name') or '').strip()
        values = facet.get('valuesAndCounts')
        if not name or not isinstance(values, list) or not values:
            continue

        entries: list[dict[str, Any]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            label = str(value.get('valueDisplay') or value.get('value') or '').strip()
            if not label:
                continue
            count = value.get('count')
            entries.append({
                'value': label,
                'count': int(count) if isinstance(count, (int, float)) else None,
            })
        entries.sort(key=lambda item: item['count'] or 0, reverse=True)
        if entries:
            out[name] = entries[:MAX_FACET_VALUES]
    return out


def fetch_courses(query: str) -> dict[str, Any]:
    """Fetch and parse the Coursera search results for ``query`` (no caching)."""
    try:
        response = requests.get(
            SEARCH_URL,
            params={'query': query},
            headers=_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CourseraScrapeError(f'Could not reach Coursera: {exc}') from exc

    # Coursera replies with a bare ``text/html`` content type and no charset, so
    # requests would fall back to ISO-8859-1 and turn names like "Professional(TM)"
    # into mojibake. The page itself is UTF-8, so decode it explicitly.
    response.encoding = 'utf-8'
    state = extract_apollo_state(response.text)
    result = _search_result(state)
    if result is None:
        raise CourseraScrapeError('No search results were present on the Coursera page.')

    courses = [
        payload
        for payload in (_course_payload(hit, state) for hit in _ordered_hits(state, result))
        if payload is not None
    ]
    if not courses:
        raise CourseraScrapeError('Coursera returned no usable course results for that search.')

    pagination = result.get('pagination')
    total_elements = pagination.get('totalElements') if isinstance(pagination, dict) else None

    return {
        'query': query,
        'count': len(courses),
        'total_results': (
            int(total_elements) if isinstance(total_elements, (int, float)) else None
        ),
        'total_pages': (
            int(result['totalPages'])
            if isinstance(result.get('totalPages'), (int, float))
            else None
        ),
        'source': 'coursera',
        'fetched_at': timezone.now().isoformat(),
        'courses': courses,
        'facets': _facets(result),
    }


def _clamp_limit(limit: Any) -> int:
    """Coerce a caller-supplied limit, ignoring anything non-numeric."""
    if limit is None or limit == '':
        return MAX_LIMIT
    try:
        return max(1, min(int(limit), MAX_LIMIT))
    except (TypeError, ValueError):
        return MAX_LIMIT


def get_courses(
    query: str | None = None, limit: Any = None
) -> tuple[dict[str, Any] | None, str | None]:
    """Return ``(payload, error)`` for a course search, using the in-process cache.

    Only one upstream request is made per query per TTL window. Failures are
    logged and surfaced to the caller as an error string so the API can answer
    with a real message instead of a bare 500.
    """
    resolved = normalise_query(query)
    capped = _clamp_limit(limit)

    cache: dict[str, Any] = getattr(get_courses, '_cache', {})
    entry = cache.get(resolved)
    if entry and (time.time() - entry['at']) < CACHE_TTL_SECONDS:
        payload = dict(entry['data'])
        payload['courses'] = payload['courses'][:capped]
        payload['count'] = len(payload['courses'])
        payload['cached'] = True
        return payload, None

    try:
        payload = fetch_courses(resolved)
    except CourseraScrapeError as exc:
        logger.warning('Coursera scrape failed for %r: %s', resolved, exc)
        return None, str(exc)

    cache[resolved] = {'at': time.time(), 'data': payload}
    get_courses._cache = cache

    payload = dict(payload)
    payload['courses'] = payload['courses'][:capped]
    payload['count'] = len(payload['courses'])
    payload['cached'] = False
    return payload, None
