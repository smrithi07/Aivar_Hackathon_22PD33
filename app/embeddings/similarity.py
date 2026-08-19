import json
import os
import numpy as np

from app.config import Config
from app.embeddings.cohere_client import embed_texts

EMBEDDINGS_CACHE_PATH = os.path.join(
    os.path.dirname(Config.VAULT_PATH), "vault_embeddings.json"
)


def _load_vault():
    with open(Config.VAULT_PATH) as f:
        return json.load(f)


def _load_cache():
    if os.path.exists(EMBEDDINGS_CACHE_PATH):
        with open(EMBEDDINGS_CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict):
    with open(EMBEDDINGS_CACHE_PATH, "w") as f:
        json.dump(cache, f)


def build_vault_embeddings(force: bool = False) -> dict:
    """
    Embeds every vault document's document_text via Cohere and caches the
    result keyed by doc_id, so re-running this doesn't re-call the API
    unless the vault has new/unembedded documents.
    Returns dict: {doc_id: embedding_vector}
    """
    vault = _load_vault()
    cache = {} if force else _load_cache()

    missing = [doc for doc in vault if doc["doc_id"] not in cache]

    if missing:
        print(f"Embedding {len(missing)} vault document(s) not yet cached...")
        texts = [doc["document_text"] for doc in missing]
        vectors = embed_texts(texts, input_type="search_document")
        for doc, vec in zip(missing, vectors):
            cache[doc["doc_id"]] = vec
        _save_cache(cache)
        print("Done — cache updated.")
    else:
        print("All vault documents already embedded (using cache).")

    return cache


def cosine_similarity(vec_a: list, vec_b: list) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def score_against_vault(text: str) -> list:
    """
    Embeds the given text as a search_query and returns a list of
    {doc_id, category, entity_name, similarity} sorted by similarity descending
    (most similar vault document first).
    """
    vault = _load_vault()
    vault_embeddings = build_vault_embeddings()

    query_vec = embed_texts([text], input_type="search_query")[0]

    results = []
    for doc in vault:
        doc_vec = vault_embeddings.get(doc["doc_id"])
        if doc_vec is None:
            continue
        sim = cosine_similarity(query_vec, doc_vec)
        results.append({
            "doc_id": doc["doc_id"],
            "category": doc["category"],
            "entity_name": doc["entity_name"],
            "similarity": sim,
        })

    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results