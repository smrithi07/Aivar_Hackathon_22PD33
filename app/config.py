import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    COHERE_API_KEY = os.environ.get("COHERE_API_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

    RISK_THRESHOLD_REVIEW = float(os.environ.get("RISK_THRESHOLD_REVIEW", 0.4))
    RISK_THRESHOLD_BLOCK = float(os.environ.get("RISK_THRESHOLD_BLOCK", 0.7))

    VAULT_PATH = os.path.join(
        os.path.dirname(__file__), "vault", "data", "vault.json"
    )


def validate_config():
    """Fail fast if required keys are missing."""
    missing = []
    if not Config.COHERE_API_KEY:
        missing.append("COHERE_API_KEY")
    if not Config.GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )