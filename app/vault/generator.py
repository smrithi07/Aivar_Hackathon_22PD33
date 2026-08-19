import json
import os
import time

from google import genai
from google.genai import types
from app.config import Config
from app.vault.schema import get_categories, get_fields, get_sensitivity
import re

MODEL_NAME = "gemini-3.5-flash-lite"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=Config.GEMINI_API_KEY)
    return _client


def _build_prompt(category: str, used_names: list) -> str:
    fields = get_fields(category)
    field_lines = "\n".join(
        f'  - "{name}" ({meta["type"]})' for name, meta in fields.items()
    )

    avoid_clause = ""
    if used_names:
        names_str = ", ".join(f'"{n}"' for n in used_names)
        avoid_clause = f"""
IMPORTANT: Do NOT reuse any of these names, since they are already used in other
documents and every document must be about a DIFFERENT person/company/deal:
{names_str}
"""

    return f"""You are generating a SYNTHETIC, FAKE finance document for a security testing tool.
None of this data is real. Do not use real company or person names.

Category: {category}

Generate ONE realistic-sounding internal document for this category, containing
these fields (invent plausible fictional values for each):
{field_lines}
{avoid_clause}
Return ONLY valid JSON, no markdown fences, no commentary, in exactly this shape:
{{
  "document_text": "<a realistic paragraph of internal document prose that naturally mentions all the field values below>",
  "fields": {{
    <one key per field above, using EXACTLY these field names, with the value you invented>
  }},
  "entity_name": "<the fictional person/company/deal name this document is about>"
}}

Rules:
- "document_text" must be prose (2-4 sentences), like an internal memo or record excerpt.
- Every value in "fields" must also be reflected in "document_text" (in words or numerals).
- Use fictional names only (e.g., "Aria Contech", "Nolan Weiss") — never real companies or people.
- Currency fields should be plain numbers in "fields" (e.g., 94500), but can be written naturally
  in "document_text" (e.g., "$94,500").
- Pick a distinctive, varied fictional name — avoid generic/common placeholder-sounding names.
"""


def generate_document(category: str, used_names: list = None) -> dict:
    """
    Generate one synthetic vault document for the given category.
    used_names: entity names already used elsewhere in the vault, to avoid repeats.
    Returns a dict with document_text, fields, and entity_name.
    """
    if used_names is None:
        used_names = []

    client = _get_client()
    prompt = _build_prompt(category, used_names)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.9,
        ),
    )

    raw = response.text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini did not return valid JSON for category '{category}'.\nRaw output:\n{raw}"
        ) from e

    required_keys = {"document_text", "fields", "entity_name"}
    if not required_keys.issubset(parsed.keys()):
        raise ValueError(
            f"Missing expected keys in generated doc for '{category}'. Got: {list(parsed.keys())}"
        )

    expected_fields = set(get_fields(category).keys())
    got_fields = set(parsed["fields"].keys())
    if expected_fields != got_fields:
        raise ValueError(
            f"Field mismatch for '{category}'.\nExpected: {expected_fields}\nGot: {got_fields}"
        )
    parsed["fields"] = _coerce_field_types(category, parsed["fields"])

    return parsed


def generate_document_with_retry(category: str, used_names: list = None, max_retries: int = 5) -> dict:
    """Wraps generate_document with exponential backoff on transient API failures."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            result = generate_document(category, used_names)
            time.sleep(1.5)  # small gap between successful calls, avoid per-minute cap
            return result
        except Exception as e:
            last_error = e
            wait = min(2 ** attempt, 30)
            print(f"  [attempt {attempt}/{max_retries}] failed for '{category}': {e}")
            if attempt < max_retries:
                print(f"  retrying in {wait}s...")
                time.sleep(wait)
    raise RuntimeError(
        f"Failed to generate document for '{category}' after {max_retries} attempts"
    ) from last_error


def _load_existing_vault(path: str) -> list:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def build_vault_incremental(save_path: str, docs_per_category: int = 2) -> list:
    """
    Generates docs_per_category documents for every category, saving after
    each one and skipping doc_ids that already exist in save_path — so a
    failed/interrupted run can simply be re-run and it resumes.
    Tracks entity names used so far and feeds them to the prompt to avoid
    duplicate/repeated entity names across the vault.
    """
    vault = _load_existing_vault(save_path)
    existing_ids = {doc["doc_id"] for doc in vault}
    used_names = [doc["entity_name"] for doc in vault]
    categories = get_categories()

    for category in categories:
        for i in range(1, docs_per_category + 1):
            doc_id = f"{category}_{i:03d}"
            if doc_id in existing_ids:
                print(f"  ↷ skipping {doc_id} (already generated)")
                continue

            print(f"Generating {doc_id}...")
            raw_doc = generate_document_with_retry(category, used_names)

            field_sensitivity = {
                field_name: get_sensitivity(category, field_name)
                for field_name in raw_doc["fields"].keys()
            }

            record = {
                "doc_id": doc_id,
                "category": category,
                "entity_name": raw_doc["entity_name"],
                "document_text": raw_doc["document_text"],
                "fields": raw_doc["fields"],
                "field_sensitivity": field_sensitivity,
            }
            vault.append(record)
            used_names.append(raw_doc["entity_name"])

            with open(save_path, "w") as f:
                json.dump(vault, f, indent=2)

            print(f"  ✓ {doc_id} — {record['entity_name']} (saved)")

    return vault

def _coerce_field_types(category: str, fields: dict) -> dict:
    """Ensure field values match their declared schema type (esp. currency -> int)."""
    schema_fields = get_fields(category)
    coerced = {}
    for field_name, value in fields.items():
        field_type = schema_fields[field_name]["type"]
        if field_type == "currency":
            if isinstance(value, str):
                cleaned = re.sub(r"[^\d.]", "", value)
                value = int(float(cleaned)) if cleaned else value
            elif isinstance(value, float):
                value = int(value)
        coerced[field_name] = value
    return coerced