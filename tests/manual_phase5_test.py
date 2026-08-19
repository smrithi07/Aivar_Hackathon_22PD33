import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.risk_engine.scorer import evaluate_text

CASES = {
    "digit_form_leak": (
        "Cassian Vane's compensation includes a $115,000 salary and $12,500 bonus, "
        "effective from his April 15, 2023 start date in the Quantum Logistics division."
    ),
    "paraphrased_leak": (
        "An employee named Cassian earns roughly one hundred fifteen thousand "
        "dollars a year in the Quantum Logistics team, with a bonus in the low "
        "five figures, and has been with the company since the spring of 2023."
    ),
    "unrelated": (
        "The weather today is sunny with a light breeze, perfect for a walk in the park."
    ),
    "borderline_partial": (
        "Compensation in the Quantum Logistics department tends to run "
        "competitive with industry standards for similar roles."
    ),
}

for label, text in CASES.items():
    print(f"=== {label} ===")
    result = evaluate_text(text)
    print(f"  DECISION: {result['decision']}  (risk_score={result['overall_risk_score']:.4f})")
    top = result["top_match"]
    print(f"  top match: {top['doc_id']} ({top['entity_name']})")
    print(f"    similarity={top['similarity_score']}  fact_match={top['fact_match_score']}  "
          f"llm_leak={top['llm_leak_score']}  matched={top['matched_fields']}")
    print()