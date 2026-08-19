import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import Config
from app.vault.schema import get_fields


def _coerce_currency(value):
    """Convert '$4,850,000' or '4850000' or 4850000 -> int 4850000"""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]", "", value)
        if cleaned == "":
            raise ValueError(f"Could not parse currency value: {value!r}")
        return int(float(cleaned))
    raise ValueError(f"Unexpected type for currency field: {value!r}")


def normalize_vault(vault: list) -> list:
    for doc in vault:
        category = doc["category"]
        schema_fields = get_fields(category)
        for field_name, value in doc["fields"].items():
            field_type = schema_fields[field_name]["type"]
            if field_type == "currency":
                doc["fields"][field_name] = _coerce_currency(value)
    return vault


def main():
    with open(Config.VAULT_PATH) as f:
        vault = json.load(f)

    vault = normalize_vault(vault)

    with open(Config.VAULT_PATH, "w") as f:
        json.dump(vault, f, indent=2)

    print(f"Normalized {len(vault)} documents in {Config.VAULT_PATH}")


if __name__ == "__main__":
    main()