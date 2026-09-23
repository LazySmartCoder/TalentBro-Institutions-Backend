"""Token-cost tracking for Gemini usage, per candidate.

Every Gemini ``generateContent`` call made on behalf of a candidate returns
``usageMetadata`` with ``promptTokenCount`` (input) and
``candidatesTokenCount`` (output). This module prices those tokens per model
(list prices in USD per 1,000,000 tokens from Google), converts the result to
Indian Rupees and adds a 40% service margin, then accumulates the total onto
the candidate's ``CandidateProfile.cost_incurred`` field so the number keeps
rising as the student uses the AI features.

Example: a call that costs ₹1.00 of raw Gemini usage is stored as ₹1.40.
"""

from decimal import ROUND_HALF_UP, Decimal

# Per-model list price in USD per 1,000,000 tokens: (input, output).
# Both "output" figures already include thinking tokens, matching Google's
# published "Output price (including thinking tokens)" rates.
GEMINI_MODEL_PRICES_USD = {
    'gemini-2.5-flash-lite': (Decimal('0.10'), Decimal('0.40')),
    'gemini-3.1-flash-lite': (Decimal('0.25'), Decimal('1.50')),
    # Speech-to-text uses the full 2.5 Flash model; included so those calls
    # are priced correctly instead of silently under-charging.
    'gemini-2.5-flash': (Decimal('0.30'), Decimal('2.50')),
}

# Fallback used for any model not listed above (cheapest known tier).
_DEFAULT_PRICES_USD = (Decimal('0.10'), Decimal('0.40'))

# Fixed USD -> INR conversion. List prices are published in USD, but the cost
# is stored and reported in INR only. ~₹95/USD as of Sep 2026.
USD_TO_INR = Decimal('95.00')

# Service margin added on top of the raw Gemini bill, kept as a factor.
# 40% margin -> cost is multiplied by 1.4 (₹1.00 raw becomes ₹1.40).
COST_MARKUP_FACTOR = Decimal('1.40')

_COST_PRECISION = Decimal('0.0001')


def _normalize_model_name(model):
    """Normalize a Gemini model id for price lookup.

    Accepts the plain id (``gemini-2.5-flash-lite``), the ``models/...``
    variants and any version-suffixed id (``-001``), so the base model family
    is what drives the price.
    """
    name = str(model or '').strip().lower()
    name = name.split(':')[-1].split('/')[-1]
    return name


def _model_prices_usd(model):
    """Return the (input_per_1m, output_per_1m) USD prices for ``model``."""
    name = _normalize_model_name(model)
    # Exact match first, then longest prefix match to tolerate suffixes.
    if name in GEMINI_MODEL_PRICES_USD:
        return GEMINI_MODEL_PRICES_USD[name]
    best = None
    for key, prices in GEMINI_MODEL_PRICES_USD.items():
        if name.startswith(key) and (best is None or len(key) > len(best[0])):
            best = (key, prices)
    if best is not None:
        return best[1]
    return _DEFAULT_PRICES_USD


def usage_cost_inr(model, usage):
    """Price one Gemini call in INR including the 40% margin.

    ``usage`` is the parsed ``usageMetadata`` dict from a Gemini response
    (``promptTokenCount`` + ``candidatesTokenCount``). Both the REST API's
    camelCase field names and the Python SDK's snake_case names are accepted.
    Returns a Decimal >= 0. A missing/empty metadata block or missing counts
    returns 0.
    """
    if not isinstance(usage, dict):
        return Decimal('0.0000')

    def _count(*keys):
        for key in keys:
            value = usage.get(key)
            if isinstance(value, bool):
                continue
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                continue
        return 0

    prompt_tokens = _count('promptTokenCount', 'prompt_token_count',
                           'inputTokenCount', 'input_token_count')
    output_tokens = _count('candidatesTokenCount', 'candidates_token_count',
                           'outputTokenCount', 'output_token_count',
                           'generatedTokenCount', 'generated_token_count')
    total_tokens = _count('totalTokenCount', 'total_token_count')
    if total_tokens and not prompt_tokens and output_tokens:
        # Some responses only report a total; split it off the output.
        prompt_tokens = max(0, total_tokens - output_tokens)
    if not prompt_tokens and not output_tokens:
        return Decimal('0.0000')

    input_price, output_price = _model_prices_usd(model)
    usd_cost = (
        (Decimal(prompt_tokens) * input_price)
        + (Decimal(output_tokens) * output_price)
    ) / Decimal(1000000)

    inr_raw = usd_cost * USD_TO_INR
    inr_with_markup = inr_raw * COST_MARKUP_FACTOR
    return inr_with_markup.quantize(_COST_PRECISION, rounding=ROUND_HALF_UP)


def record_cost_incurred(user, model, payload):
    """Accumulate the cost of one Gemini call onto the candidate's profile.

    ``user`` is the authenticated Django user the call was made for; only
    accounts that own a ``CandidateProfile`` are charged (candidates ==
    students in this project). ``payload`` is the raw JSON response from the
    Gemini API so ``usageMetadata`` can be read.

    Returns the Decimal cost (in INR, margin included) that was added, or 0
    when the user/profile is absent or the response carried no token usage.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return Decimal('0.0000')
    profile = getattr(user, 'candidate_profile', None)
    if profile is None:
        return Decimal('0.0000')
    if not isinstance(payload, dict):
        return Decimal('0.0000')

    cost = usage_cost_inr(model, payload.get('usageMetadata'))
    if cost <= 0:
        return Decimal('0.0000')

    current = profile.cost_incurred or Decimal('0.0000')
    profile.cost_incurred = (current + cost).quantize(
        _COST_PRECISION, rounding=ROUND_HALF_UP,
    )
    profile.save(update_fields=['cost_incurred', 'updated_at'])
    return cost