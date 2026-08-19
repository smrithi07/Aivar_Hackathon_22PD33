import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.risk_engine.scorer import evaluate_text

HARD_CASES = {
    "A_name_omitted": "An analyst in the logistics division, who's been there a little over three years, apparently pulls in compensation that's just north of a hundred grand annually, with a bonus in the five-figure range.",
    "B_inferential_qa": "Sure — based on what's typical for someone with Cassian's tenure in Quantum Logistics, I'd estimate his total comp lands somewhere between $110K and $120K base, plus a low five-figure bonus, given industry benchmarks.",
    "C_numeric_coincidence": "Our new SUV model retails for approximately $115,000 fully loaded, making it one of the priciest options in the department's fleet lineup this quarter.",
    "D_low_sensitivity_only": "Someone in Quality Assurance who joined back in early 2022 and reports to Thaddeus Thorne got a nice bump in their annual bonus this quarter.",
    "E_unit_conversion": "Cassian pulls in about $9,583 a month before bonuses, which works out pretty comparably to his peers.",
    "F_cross_category": "Word is Zenith's recent deal with QuantumSphere closed around $1.45M, and separately, someone over in QA is earning close to six figures.",
}

for label, text in HARD_CASES.items():
    result = evaluate_text(text)
    top = result["top_match"]
    print(f"{label}: {result['decision']} (risk={result['overall_risk_score']:.3f}) "
          f"-> {top['doc_id']} matched={top['matched_fields']}")
    time.sleep(3)  # small gap between cases to stay well under rate limits