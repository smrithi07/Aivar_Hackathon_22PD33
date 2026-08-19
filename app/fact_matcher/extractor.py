import json
import re
from datetime import datetime

from rapidfuzz import fuzz

from app.config import Config
from app.vault.schema import get_fields

_MONEY_MULTIPLIERS = {
    "thousand": 1_000,
    "k": 1_000,
    "million": 1_000_000,
    "mn": 1_000_000,
    "billion": 1_000_000_000,
    "bn": 1_000_000_000,
}

_NUMBER_RE = re.compile(
    r'\$?\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s?(thousand|million|billion|k|mn|bn)?',
    re.IGNORECASE
)

_PERCENT_RE = re.compile(r'(\d+(?:\.\d+)?)\s?%')

_SENSITIVITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def _load_vault() -> list:
    with open(Config.VAULT_PATH) as f:
        return json.load(f)


def extract_numbers(text: str) -> list:
    """Extract numeric quantities from text, resolving 'million'/'thousand'/'k' suffixes."""
    results = []
    for match in _NUMBER_RE.finditer(text):
        raw_num, suffix = match.groups()
        if raw_num is None:
            continue
        try:
            value = float(raw_num.replace(",", ""))
        except ValueError:
            continue
        if suffix:
            multiplier = _MONEY_MULTIPLIERS.get(suffix.lower())
            if multiplier:
                value *= multiplier
        results.append(value)
    return results


def extract_percentages(text: str) -> list:
    return [float(m.group(1)) for m in _PERCENT_RE.finditer(text)]


def _numbers_match(a: float, b: float, tolerance: float = 0.02) -> bool:
    """True if a and b are within `tolerance` relative difference (default 2%)."""
    if b == 0:
        return a == 0
    return abs(a - b) / abs(b) <= tolerance


def _parse_percentage_value(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r'[^\d.]', '', value)
        if cleaned:
            return float(cleaned)
    return None


def _date_variants(date_str: str) -> list:
    """Generate alternate textual representations of an ISO ('YYYY-MM-DD') date string."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return [date_str]
    day = str(dt.day)
    month_full = dt.strftime("%B")
    month_abbr = dt.strftime("%b")
    year = str(dt.year)
    return [
        date_str,
        f"{month_full} {day}, {year}",
        f"{month_abbr} {day}, {year}",
        f"{dt.month:02d}/{dt.day:02d}/{year}",
        f"{day} {month_full} {year}",
    ]


def _field_matches(field_type: str, field_value, text: str, numbers: list, percentages: list) -> bool:
    if field_type in ("currency", "number"):
        try:
            target = float(field_value) if not isinstance(field_value, str) else _parse_percentage_value(field_value)
        except (TypeError, ValueError):
            return False
        if target is None:
            return False
        return any(_numbers_match(n, target) for n in numbers)

    if field_type == "percentage":
        target = _parse_percentage_value(field_value)
        if target is None:
            return False
        return any(abs(p - target) < 0.5 for p in percentages)

    if field_type == "date":
        variants = _date_variants(str(field_value))
        return any(v.lower() in text.lower() for v in variants)

    if field_type == "text":
        score = fuzz.partial_ratio(str(field_value).lower(), text.lower())
        return score >= 85

    return False


def match_document(doc: dict, text: str) -> dict:
    """
    Checks how many fields of a single vault document appear (numerically or
    textually) in the given text. Returns matched fields and a sensitivity-
    weighted match score between 0.0 and 1.0.
    """
    numbers = extract_numbers(text)
    percentages = extract_percentages(text)
    schema_fields = get_fields(doc["category"])

    matched_fields = []
    total_weight = 0
    matched_weight = 0

    for field_name, field_value in doc["fields"].items():
        field_type = schema_fields[field_name]["type"]
        sensitivity = doc["field_sensitivity"][field_name]
        weight = _SENSITIVITY_WEIGHT[sensitivity]
        total_weight += weight

        if _field_matches(field_type, field_value, text, numbers, percentages):
            matched_fields.append(field_name)
            matched_weight += weight

    score = matched_weight / total_weight if total_weight > 0 else 0.0

    return {
        "doc_id": doc["doc_id"],
        "category": doc["category"],
        "matched_fields": matched_fields,
        "match_count": len(matched_fields),
        "total_fields": len(doc["fields"]),
        "fact_match_score": score,
    }


def match_text_against_vault(text: str) -> list:
    """
    Runs match_document against every vault document. Returns results
    sorted by fact_match_score descending (best match first).
    """
    vault = _load_vault()
    results = [match_document(doc, text) for doc in vault]
    results.sort(key=lambda r: r["fact_match_score"], reverse=True)
    return results