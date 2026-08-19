import time
from cohere import Client
from cohere.core.api_error import ApiError
from app.config import Config

EMBED_MODEL = "embed-v4.0"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Client(api_key=Config.COHERE_API_KEY)
    return _client


def embed_texts(texts: list, input_type: str = "search_document", max_retries: int = 4) -> list:
    """
    Embed a list of texts via Cohere. Returns a list of embedding vectors,
    in the same order as the input texts.

    input_type: "search_document" for vault content being stored/searched over,
                "search_query" for content being checked against the vault.
    """
    if not texts:
        return []

    client = _get_client()
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.embed(
                model=EMBED_MODEL,
                texts=texts,
                input_type=input_type,
                embedding_types=["float"],
            )
            return response.embeddings.float
        except ApiError as e:
            last_error = e
            wait = min(2 ** attempt, 20)
            print(f"  [cohere embed attempt {attempt}/{max_retries}] failed: {e}")
            if attempt < max_retries:
                time.sleep(wait)
    raise RuntimeError(f"Cohere embedding failed after {max_retries} attempts") from last_error