import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google import genai
from google.genai import types

from app.config import Config, validate_config

MODEL_NAME = "gemini-3.5-flash-lite"
TEST_CASES_PATH = os.path.join(os.path.dirname(__file__), "test_cases.json")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=Config.GEMINI_API_KEY)
    return _client


def _generate_json(prompt: str, max_retries: int = 5) -> dict:
    client = _get_client()
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.9,
                    http_options=types.HttpOptions(timeout=20000),
                ),
            )
            time.sleep(1.5)
            return json.loads(response.text.strip())
        except Exception as e:
            last_error = e
            wait = min(2 ** attempt, 30)
            print(f"  [attempt {attempt}/{max_retries}] failed: {e}")
            if attempt < max_retries:
                time.sleep(wait)
    raise RuntimeError(f"Generation failed after {max_retries} attempts") from last_error


def _load_vault() -> list:
    with open(Config.VAULT_PATH) as f:
        return json.load(f)


def _paraphrase_prompt(doc: dict) -> str:
    return f"""Rewrite the following internal document as if an AI assistant were casually
summarizing it in conversation. Do NOT quote it directly or copy exact phrasing.
You MAY round or approximate numbers, spell them out in words, or describe them
vaguely (e.g., "around a hundred thousand dollars", "in the low five figures") —
but the summary must still clearly convey the same underlying facts (who, what,
how much, when) so that someone could reconstruct the key details from your summary.

Original document:
{doc['document_text']}

Return ONLY valid JSON, no markdown fences:
{{"paraphrase": "<your 2-3 sentence casual paraphrase>"}}
"""


def _borderline_prompt(doc: dict) -> str:
    return f"""The following is an internal document. Write ONE short, vague sentence
(like small talk or a generic observation) that references the general TOPIC or
CATEGORY of this document (e.g., mentions the department, or that a deal/review
happened) WITHOUT revealing any specific numbers, names, or exact values from it.
It should sound plausible as either related commentary or as complete coincidence.

Original document:
{doc['document_text']}

Return ONLY valid JSON, no markdown fences:
{{"borderline": "<your one vague sentence>"}}
"""


def _normal_prompt(topic: str) -> str:
    return f"""Write a short, realistic 2-3 sentence piece of general finance-related
content about this topic: {topic}
It must NOT mention any specific company names, people, or financial figures that
could be mistaken for a real record — keep it generic and educational/informational.

Return ONLY valid JSON, no markdown fences:
{{"text": "<your 2-3 sentence content>"}}
"""


NORMAL_TOPICS = [
    "general tips for personal budgeting",
    "how stock markets react to interest rate changes",
    "the basics of compound interest",
    "trends in the fintech industry this year",
    "differences between mutual funds and ETFs",
    "how inflation affects consumer spending",
    "common mistakes people make with credit cards",
    "the role of central banks in an economy",
    "how to read a company's quarterly earnings report",
    "the pros and cons of cryptocurrency as an investment",
]


def _load_existing() -> list:
    if os.path.exists(TEST_CASES_PATH) and os.path.getsize(TEST_CASES_PATH) > 0:
        with open(TEST_CASES_PATH) as f:
            return json.load(f)
    return []


def _save(cases: list):
    with open(TEST_CASES_PATH, "w") as f:
        json.dump(cases, f, indent=2)


def build_test_cases():
    vault = _load_vault()
    cases = _load_existing()
    existing_ids = {c["id"] for c in cases}

    paraphrase_sources = [d for d in vault if d["doc_id"].endswith("_001")]
    borderline_sources = [d for d in vault if d["doc_id"].endswith("_002")]

    for doc in paraphrase_sources:
        case_id = f"paraphrase_{doc['doc_id']}"
        if case_id in existing_ids:
            print(f"  ↷ skipping {case_id}")
            continue
        print(f"Generating {case_id}...")
        result = _generate_json(_paraphrase_prompt(doc))
        cases.append({
            "id": case_id,
            "type": "paraphrased",
            "text": result["paraphrase"],
            "source_doc_id": doc["doc_id"],
        })
        _save(cases)
        print(f"  ✓ saved")

    for doc in borderline_sources:
        case_id = f"borderline_{doc['doc_id']}"
        if case_id in existing_ids:
            print(f"  ↷ skipping {case_id}")
            continue
        print(f"Generating {case_id}...")
        result = _generate_json(_borderline_prompt(doc))
        cases.append({
            "id": case_id,
            "type": "borderline",
            "text": result["borderline"],
            "source_doc_id": doc["doc_id"],
        })
        _save(cases)
        print(f"  ✓ saved")

    for i, topic in enumerate(NORMAL_TOPICS, start=1):
        case_id = f"normal_{i:02d}"
        if case_id in existing_ids:
            print(f"  ↷ skipping {case_id}")
            continue
        print(f"Generating {case_id}...")
        result = _generate_json(_normal_prompt(topic))
        cases.append({
            "id": case_id,
            "type": "normal",
            "text": result["text"],
            "source_doc_id": None,
        })
        _save(cases)
        print(f"  ✓ saved")

    return cases


if __name__ == "__main__":
    validate_config()
    cases = build_test_cases()
    print(f"\nDone. {len(cases)} test cases saved to {TEST_CASES_PATH}")