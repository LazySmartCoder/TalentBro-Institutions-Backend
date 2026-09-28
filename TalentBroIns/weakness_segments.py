"""Weakness segmentation that drives the candidate ``/courses`` screen.

The ``/tutorials`` screen already groups the 34 mock-interview dimensions into a
handful of human buckets (``ANALYSIS_TOPICS`` in ``Frontend/src/routes/
tutorials.tsx``) and asks YouTube for a video per bucket. This module is the
Coursera-side twin of that idea and deliberately reuses the *same* nine bucket
labels, so a candidate who sees "Communication & Soft Skills" on one screen
recognises it on the other.

Two things are different on purpose:

* The buckets are fed from four sources, not just mock interviews. Self-training
  (English, GD, aptitude) is where most of a candidate's evidence actually lives.
* Each bucket carries a Coursera search phrase instead of a YouTube phrase, which
  the existing ``coursera_scraper`` turns into a course grid.

Scoring rules, chosen to stay honest rather than flattering:

* A dimension only counts when it has evidence behind it. ``MockInterviewAnalysis``
  seeds every one of its 34 percentage fields with ``0``, so an unscored dimension
  would otherwise masquerade as a catastrophic weakness.
* Mock interviews use the *worst* recent showing per dimension (min across the last
  few analyses), matching the tutorials screen so both screens agree.
* English and GD sessions only count once completed, and a session whose relevant
  columns are all zero is treated as unscored and skipped.
* Segments with no evidence at all are omitted, so a brand-new candidate gets the
  neutral default search rather than nine confident-looking zeroes.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    APLR_STATUS_ACTIVE,
    APLR_STATUS_GAVE_UP,
    APLR_STATUS_SOLVED,
    GD_CRITERIA,
    GD_CRITERIA_FIELDS,
    GD_STATUS_COMPLETED,
    MOCK_INTERVIEW_ANALYSIS_DIMENSIONS,
    MOCK_INTERVIEW_STATUS_COMPLETED,
    APLRTraining,
    EnglishTrainingSession,
    GdTraining,
    MockInterview,
)

logger = logging.getLogger(__name__)

# How many recent rows to read per source. Interviews are noisier than a scored
# English session, so they get a slightly wider window.
MOCK_INTERVIEW_LIMIT = 3
TRAINING_SESSION_LIMIT = 3
APLR_SESSION_LIMIT = 40

WEAKNESS_SEGMENTS: tuple[dict[str, str], ...] = (
    {
        'key': 'communication_soft_skills',
        'label': 'Communication & Soft Skills',
        'query': 'communication skills for the workplace',
        'blurb': 'Spoken clarity, vocabulary and listening.',
    },
    {
        'key': 'domain_knowledge',
        'label': 'Domain Knowledge & Awareness',
        'query': 'industry knowledge for business',
        'blurb': 'Knowing your field well enough to answer anything asked.',
    },
    {
        'key': 'analytical_thinking',
        'label': 'Analytical Thinking & Problem Solving',
        'query': 'critical thinking and problem solving',
        'blurb': 'Reasoning through unfamiliar problems and aptitude questions.',
    },
    {
        'key': 'structured_answers',
        'label': 'Structured Interview Answers',
        'query': 'business writing and presentation',
        'blurb': 'Organising a thought so it lands in the time you get.',
    },
    {
        'key': 'confidence_presence',
        'label': 'Confidence & Body Language',
        'query': 'public speaking and presentation skills',
        'blurb': 'Coming across steady, present and sure of yourself.',
    },
    {
        'key': 'leadership',
        'label': 'Leadership & Initiative',
        'query': 'leadership and management essentials',
        'blurb': 'Taking charge and owning outcomes in a team.',
    },
    {
        'key': 'teamwork',
        'label': 'Teamwork & Interpersonal Skills',
        'query': 'teamwork and emotional intelligence',
        'blurb': 'Working with others, handling conflict, reading the room.',
    },
    {
        'key': 'motivation_fit',
        'label': 'Interview Motivation & Role Fit',
        'query': 'career planning and professional development',
        'blurb': 'Knowing why you want the role, and what you want from it.',
    },
    {
        'key': 'general_awareness',
        'label': 'General Awareness & Current Affairs',
        'query': 'general knowledge and current affairs',
        'blurb': 'Wider awareness of the world you are stepping into.',
    },
)

SEGMENTS_BY_KEY: dict[str, dict[str, str]] = {s['key']: s for s in WEAKNESS_SEGMENTS}

# Mock-interview dimension slugs per bucket. Mirrors the tutorials screen's
# ``ANALYSIS_TOPICS`` keys, minus two of its bugs: ``ownership`` is not a real
# dimension, and ``clarity_of_thought`` was double-listed under two buckets.
_INTERVIEW_DIMENSIONS: dict[str, tuple[str, ...]] = {
    'communication_soft_skills': (
        'communication_skills',
        'verbal_fluency',
        'vocabulary',
        'listening',
        'conciseness',
    ),
    'domain_knowledge': ('subject_knowledge', 'knowledge_awareness'),
    'analytical_thinking': (
        'analytical_problem_solving',
        'logical_reasoning',
        'creativity',
        'clarity_of_thought',
    ),
    'structured_answers': ('ability_structure_answer', 'ability_defend_opinion'),
    'confidence_presence': ('confidence', 'personality_presence', 'energy', 'attitude'),
    'leadership': ('leadership_initiative', 'responsibility'),
    'teamwork': (
        'teamwork_interpersonal_skills',
        'empathy',
        'conflict_management',
        'respect_for_others',
    ),
    'motivation_fit': ('motivation_fit', 'ambition', 'self_awareness', 'learning_orientation'),
    'general_awareness': ('general_awareness', 'curiosity'),
}

# English training scores per bucket.
_ENGLISH_SCORES: dict[str, tuple[str, ...]] = {
    'communication_soft_skills': (
        'grammar',
        'vocabulary',
        'spelling',
        'conciseness',
        'professional_tone',
        'writing_score',
        'clarity',
    ),
    'structured_answers': ('structure', 'task_focus'),
}

# Group-discussion criteria per bucket.
_GD_CRITERIA: dict[str, tuple[str, ...]] = {
    'domain_knowledge': ('content_quality',),
    'analytical_thinking': ('reasoning',),
    'communication_soft_skills': ('communication', 'active_listening'),
    'confidence_presence': ('confidence',),
    'teamwork': ('teamwork',),
    'leadership': ('initiative', 'build_challenge'),
}

# Aptitude categories per bucket.
_APLR_CATEGORIES: dict[str, tuple[str, ...]] = {
    'analytical_thinking': (
        'quantitative',
        'logical_reasoning',
        'data_interpretation',
        'puzzle',
    ),
    'communication_soft_skills': ('verbal',),
    'general_awareness': ('miscellaneous',),
}

# Human labels, taken from the model constants so they can never drift out of
# sync with the fields they describe.
_INTERVIEW_LABELS: dict[str, str] = {
    field: label for field, label, _definition in MOCK_INTERVIEW_ANALYSIS_DIMENSIONS
}
_ENGLISH_LABELS: dict[str, str] = {
    'clarity': 'Clarity',
    'structure': 'Structure',
    'grammar': 'Grammar',
    'vocabulary': 'Vocabulary',
    'spelling': 'Spelling & Punctuation',
    'conciseness': 'Conciseness',
    'task_focus': 'Task Focus & Format',
    'professional_tone': 'Professional Tone',
    'writing_score': 'Overall Writing',
}
_GD_LABELS: dict[str, str] = dict(GD_CRITERIA)

# Guard against a mapping typo silently dropping evidence. This only warns: a
# crash at import time would take the whole candidate app down over a cosmetic
# label, and the test suite pins the tables so typos cannot land unnoticed.
def _validate_mappings() -> None:
    english_fields = set(_ENGLISH_LABELS)
    gd_fields = set(GD_CRITERIA_FIELDS)
    for dimensions in _INTERVIEW_DIMENSIONS.values():
        unknown = [d for d in dimensions if d not in _INTERVIEW_LABELS]
        if unknown:
            logger.warning('unknown mock-interview dimensions mapped: %s', unknown)
    for fields in _ENGLISH_SCORES.values():
        unknown = [f for f in fields if f not in english_fields]
        if unknown:
            logger.warning('unknown english training scores mapped: %s', unknown)
    for fields in _GD_CRITERIA.values():
        unknown = [f for f in fields if f not in gd_fields]
        if unknown:
            logger.warning('unknown GD criteria mapped: %s', unknown)
    mapped = {f for fields in _GD_CRITERIA.values() for f in fields}
    uncovered = sorted(gd_fields - mapped)
    if uncovered:
        logger.warning('GD criteria not mapped to any weakness segment: %s', uncovered)


_validate_mappings()


def _label_for(slug: str, labels: dict[str, str]) -> str:
    return labels.get(slug) or slug.replace('_', ' ').title()


def _clamp(value: Any) -> int | None:
    """Coerce a stored score to a 0-100 int, or None when it is not a real score."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0 or value > 100:
        return None
    return int(value)


def _scored(value: Any) -> int | None:
    """Like :func:`_clamp`, but treats 0 as "never scored".

    The self-training tables have no per-field presence flag, and every score
    column is a ``PositiveSmallIntegerField(default=0)``. English and GD rows are
    written with only a subset of their columns filled in, so counting the
    untouched zeros would drag a segment's average down on evidence that does not
    exist. Mock interviews do not need this rule because they carry a written
    description per dimension, which is used as the presence test instead.
    """
    score = _clamp(value)
    if score is None or score == 0:
        return None
    return score


class _Bucket:
    """Accumulates evidence for one weakness segment."""

    __slots__ = ('key', 'scores', 'evidence', 'sources')

    def __init__(self, key: str) -> None:
        self.key = key
        self.scores: list[int] = []
        self.evidence: list[str] = []
        self.sources: set[str] = set()

    def add(self, score: int, source: str, evidence: str | None = None) -> None:
        self.scores.append(score)
        self.sources.add(source)
        if evidence and len(self.evidence) < 3:
            self.evidence.append(evidence)

    def as_dict(self) -> dict[str, Any]:
        meta = SEGMENTS_BY_KEY[self.key]
        return {
            'key': self.key,
            'label': meta['label'],
            'query': meta['query'],
            'blurb': meta['blurb'],
            'score': round(sum(self.scores) / len(self.scores)),
            'sample_size': len(self.scores),
            'sources': sorted(self.sources),
            'evidence': self.evidence[:3],
        }


def _interview_buckets(buckets: dict[str, _Bucket], user: Any) -> None:
    """Fold the worst recent score per mock-interview dimension into buckets.

    Only dimensions that carry an AI-written description are counted: the model
    seeds all 34 percentage columns with ``0``, so a dimension nobody scored would
    otherwise be read as a 0% weakness.
    """
    interviews = list(
        MockInterview.objects.filter(user=user, status=MOCK_INTERVIEW_STATUS_COMPLETED)
        .exclude(analysis=None)
        .select_related('analysis')
        .order_by('-updated_at')[:MOCK_INTERVIEW_LIMIT]
    )
    if not interviews:
        return

    # slug -> (worst score, label, company)
    worst: dict[str, tuple[int, str, str]] = {}
    for interview in interviews:
        analysis = interview.analysis
        for field, label, _definition in MOCK_INTERVIEW_ANALYSIS_DIMENSIONS:
            score = _clamp(getattr(analysis, field, None))
            description = (getattr(analysis, f'{field}_desc', '') or '').strip()
            if score is None or not description:
                continue
            current = worst.get(field)
            if current is None or score < current[0]:
                worst[field] = (score, label, interview.company_name or 'your mock interview')

    for segment_key, dimensions in _INTERVIEW_DIMENSIONS.items():
        bucket = buckets[segment_key]
        for field in dimensions:
            found = worst.get(field)
            if found is None:
                continue
            score, label, company = found
            bucket.add(
                score,
                'mock_interview',
                f'{label}: you scored {score}% ({company}).',
            )


def _english_buckets(buckets: dict[str, _Bucket], user: Any) -> None:
    sessions = list(
        EnglishTrainingSession.objects.filter(user=user, status='completed')
        .order_by('-created_at')[:TRAINING_SESSION_LIMIT]
    )
    for session in sessions:
        if not any(_scored(getattr(session, f, None)) for f in _ENGLISH_LABELS):
            continue
        for segment_key, fields in _ENGLISH_SCORES.items():
            bucket = buckets[segment_key]
            for field in fields:
                score = _scored(getattr(session, field, None))
                if score is None:
                    continue
                bucket.add(
                    score,
                    'english_training',
                    f'{_label_for(field, _ENGLISH_LABELS)}: you scored {score}%.',
                )


def _gd_buckets(buckets: dict[str, _Bucket], user: Any) -> None:
    sessions = list(
        GdTraining.objects.filter(user=user, status=GD_STATUS_COMPLETED).order_by('-created_at')[
            :TRAINING_SESSION_LIMIT
        ]
    )
    for session in sessions:
        # A completed session that scored nothing at all was never actually
        # evaluated, so it is skipped rather than counted as a wall of zeroes.
        if not any(_scored(getattr(session, f, None)) for f in GD_CRITERIA_FIELDS):
            continue
        for segment_key, criteria in _GD_CRITERIA.items():
            bucket = buckets[segment_key]
            for field in criteria:
                score = _scored(getattr(session, field, None))
                if score is None:
                    continue
                bucket.add(
                    score,
                    'gd_training',
                    f'{_label_for(field, _GD_LABELS)}: you scored {score}% in a group discussion.',
                )


def _aplr_buckets(buckets: dict[str, _Bucket], user: Any) -> None:
    """Score aptitude practice per category: how often it is solved unaided."""
    sessions = list(
        APLRTraining.objects.filter(user=user)
        .exclude(status=APLR_STATUS_ACTIVE)
        .order_by('-created_at')[:APLR_SESSION_LIMIT]
    )
    by_category: dict[str, list[APLRTraining]] = {}
    for session in sessions:
        by_category.setdefault(session.category, []).append(session)

    for segment_key, categories in _APLR_CATEGORIES.items():
        bucket = buckets[segment_key]
        for category in categories:
            rows = by_category.get(category)
            if not rows:
                continue
            solved = [r for r in rows if r.status == APLR_STATUS_SOLVED]
            gave_up = [r for r in rows if r.status == APLR_STATUS_GAVE_UP]
            resolved = len(solved) + len(gave_up)
            if not resolved:
                continue
            readable = category.replace('_', ' ')
            score = 100 * len(solved) / resolved
            # Needing hints, or several attempts, marks the topic as shaky even
            # when it was eventually solved.
            hints = sum(r.hints_used for r in rows) / len(rows)
            attempts = sum(r.attempts for r in rows) / len(rows)
            score -= min(15, hints * 5)
            if attempts > 2:
                score -= min(10, (attempts - 2) * 5)
            score = max(0, min(100, round(score)))
            if not gave_up:
                evidence = f'Solved all {resolved} {readable} question(s) unaided.'
            else:
                evidence = f'Gave up on {len(gave_up)} of {resolved} {readable} question(s).'
            bucket.add(score, 'aplr', evidence)


def collect_weakness_segments(user: Any) -> list[dict[str, Any]]:
    """Return the candidate's weakness segments, weakest score first.

    Segments without any evidence are omitted. An empty list means "no tracked
    weakness yet" and the caller should fall back to a neutral default search.
    """
    buckets = {segment['key']: _Bucket(segment['key']) for segment in WEAKNESS_SEGMENTS}

    _interview_buckets(buckets, user)
    _english_buckets(buckets, user)
    _gd_buckets(buckets, user)
    _aplr_buckets(buckets, user)

    segments = [bucket.as_dict() for bucket in buckets.values() if bucket.scores]
    # Weakest first, so the front end can lead with the most urgent gap.
    segments.sort(key=lambda s: (s['score'], s['label']))
    return segments
