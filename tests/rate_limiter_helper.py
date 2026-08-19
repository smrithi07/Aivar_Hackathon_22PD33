import time

# Gemini free tier: 15 requests/minute for this model.
GEMINI_RPM_LIMIT = 15


def pace(calls_per_case: int, safety_margin: float = 1.2):
    """
    Sleeps just long enough that running many evaluate_text() calls back-to-back
    stays under the Gemini free-tier rate limit, instead of relying on retry
    backoff to absorb 429s (which works, but silently costs 20-70s per hit).

    calls_per_case: how many Gemini judge calls one evaluate_text() call makes
                     (this is judge_top_k, default 3).
    safety_margin:   multiplier on the minimum delay, to leave headroom for
                     Phase 6/7's own retries or clock drift.
    """
    max_cases_per_minute = GEMINI_RPM_LIMIT / calls_per_case
    min_delay_seconds = 60.0 / max_cases_per_minute
    time.sleep(min_delay_seconds * safety_margin)