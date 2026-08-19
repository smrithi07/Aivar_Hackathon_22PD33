import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.vault.generator import build_vault_incremental
from app.config import Config, validate_config


def main():
    validate_config()
    os.makedirs(os.path.dirname(Config.VAULT_PATH), exist_ok=True)

    print("Building vault...\n")
    vault = build_vault_incremental(Config.VAULT_PATH, docs_per_category=2)

    print(f"\nDone. {len(vault)} documents saved to {Config.VAULT_PATH}")


if __name__ == "__main__":
    main()