import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.llm_judge.gemini_judge import judge_text

CASES = {
    "paraphrased_leak": (
        "An employee named Cassian earns roughly one hundred fifteen thousand "
        "dollars a year in the Quantum Logistics team, with a bonus in the low "
        "five figures, and has been with the company since the spring of 2023."
    ),
    "unrelated": (
        "The weather today is sunny with a light breeze, perfect for a walk "
        "in the park."
    ),
    "borderline_partial": (
        "Compensation in the Quantum Logistics department tends to run "
        "competitive with industry standards for similar roles."
    ),
}

for label, text in CASES.items():
    print(f"=== {label} ===")
    verdicts = judge_text(text, top_k=2)
    for v in verdicts:
        print(f"  doc={v['doc_id']}  contains_facts={v['contains_protected_facts']}  "
              f"confidence={v['confidence']:.2f}  paraphrased={v['is_paraphrased']}  "
              f"matched={v['matched_facts']}")
        print(f"    reasoning: {v['reasoning']}")
    print()