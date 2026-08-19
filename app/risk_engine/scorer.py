import json

from app.config import Config
from app.embeddings.similarity import score_against_vault
from app.fact_matcher.extractor import match_text_against_vault
from app.llm_judge.gemini_judge import judge_text

# Signal weights — final, tuned for this hackathon submission.
# LLM judge weighted highest since it reasons about actual factual
# derivation, not just surface-level similarity.
WEIGHT_SIMILARITY = 0.30
WEIGHT_FACT_MATCH = 0.30
WEIGHT_LLM_JUDGE = 0.40

HIGH_SENSITIVITY_BONUS = 0.10


def _load_vault() -> list:
    with open(Config.VAULT_PATH) as f:
        return json.load(f)


def _index_by_doc_id(items: list, key: str = "doc_id") -> dict:
    return {item[key]: item for item in items}


def _has_high_sensitivity_match(doc: dict, matched_fields: list) -> bool:
    if not matched_fields:
        return False
    sensitivity = doc.get("field_sensitivity", {})
    return any(sensitivity.get(f) == "high" for f in matched_fields)


def evaluate_text(text: str, judge_top_k: int = 3) -> dict:
    """
    Runs all three detection signals against the vault, combines them into
    a per-document risk score, and returns the overall decision based on
    the highest-risk document.
    """
    vault = _load_vault()
    vault_by_id = _index_by_doc_id(vault)

    similarity_results = score_against_vault(text)
    fact_results = match_text_against_vault(text)
    judge_results = judge_text(text, top_k=judge_top_k, similarity_results=similarity_results)

    sim_by_id = _index_by_doc_id(similarity_results)
    fact_by_id = _index_by_doc_id(fact_results)
    judge_by_id = _index_by_doc_id(judge_results)

    doc_scores = []

    for doc_id, doc in vault_by_id.items():
        sim_score = sim_by_id.get(doc_id, {}).get("similarity", 0.0)
        fact_score = fact_by_id.get(doc_id, {}).get("fact_match_score", 0.0)
        fact_matched_fields = fact_by_id.get(doc_id, {}).get("matched_fields", [])

        judge_verdict = judge_by_id.get(doc_id)
        if judge_verdict is not None:
            llm_leak_score = (
                judge_verdict["confidence"] if judge_verdict["contains_protected_facts"] else 0.0
            )
            llm_matched_fields = judge_verdict["matched_facts"]
        else:
            # Doc wasn't in the LLM judge's shortlist (low similarity rank) —
            # treat as no LLM evidence rather than calling the API for every doc.
            llm_leak_score = 0.0
            llm_matched_fields = []

        combined = (
            WEIGHT_SIMILARITY * sim_score
            + WEIGHT_FACT_MATCH * fact_score
            + WEIGHT_LLM_JUDGE * llm_leak_score
        )

        all_matched_fields = sorted(set(fact_matched_fields) | set(llm_matched_fields))
        if _has_high_sensitivity_match(doc, all_matched_fields):
            combined = min(1.0, combined + HIGH_SENSITIVITY_BONUS)

        doc_scores.append({
            "doc_id": doc_id,
            "category": doc["category"],
            "entity_name": doc["entity_name"],
            "similarity_score": round(sim_score, 4),
            "fact_match_score": round(fact_score, 4),
            "llm_leak_score": round(llm_leak_score, 4),
            "matched_fields": all_matched_fields,
            "risk_score": round(combined, 4),
        })

    doc_scores.sort(key=lambda d: d["risk_score"], reverse=True)
    top = doc_scores[0]
    overall_risk_score = top["risk_score"]

    if overall_risk_score >= Config.RISK_THRESHOLD_BLOCK:
        decision = "BLOCK"
    elif overall_risk_score >= Config.RISK_THRESHOLD_REVIEW:
        decision = "REVIEW"
    else:
        decision = "ALLOW"

    return {
        "text": text,
        "decision": decision,
        "overall_risk_score": overall_risk_score,
        "top_match": top,
        "all_scores": doc_scores[:5],
    }