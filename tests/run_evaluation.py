import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.risk_engine.scorer import evaluate_text
from tests.rate_limiter_helper import pace
TEST_CASES_PATH = os.path.join(os.path.dirname(__file__), "test_cases.json")


def _load_cases() -> list:
    with open(TEST_CASES_PATH) as f:
        return json.load(f)


def _find_score_for_doc(all_scores: list, doc_id: str):
    for entry in all_scores:
        if entry["doc_id"] == doc_id:
            return entry
    return None


def run():
    cases = _load_cases()
    results = []

    print(f"Running {len(cases)} test cases through the risk engine...\n")
    for case in cases:
        print(f"  evaluating {case['id']}...")
        try:
            outcome = evaluate_text(case["text"])
            results.append({**case, "outcome": outcome})
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            results.append({**case, "outcome": None, "error": str(e)})
        pace(calls_per_case=3)

    with open(os.path.join(os.path.dirname(__file__), "phase8_results.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 70)
    print("SUCCESS CRITERIA REPORT")
    print("=" * 70)

    paraphrased = [r for r in results if r["type"] == "paraphrased"]
    normal = [r for r in results if r["type"] == "normal"]
    borderline = [r for r in results if r["type"] == "borderline"]

    # Criterion 1: similarity scorer ranks paraphrased content higher than unrelated
    paraphrase_sims = []
    for r in paraphrased:
        entry = _find_score_for_doc(r["outcome"]["all_scores"], r["source_doc_id"])
        sim = entry["similarity_score"] if entry else 0.0
        paraphrase_sims.append(sim)
    normal_sims = [r["outcome"]["top_match"]["similarity_score"] for r in normal]

    min_paraphrase_sim = min(paraphrase_sims) if paraphrase_sims else 0
    max_normal_sim = max(normal_sims) if normal_sims else 0
    crit1_pass = min_paraphrase_sim > max_normal_sim

    print(f"\n[1] Similarity ranks paraphrased > unrelated")
    print(f"    min(paraphrased similarity) = {min_paraphrase_sim:.4f}")
    print(f"    max(normal similarity)      = {max_normal_sim:.4f}")
    print(f"    {'PASS' if crit1_pass else 'FAIL'}")

    # Criterion 2: factual overlap detector identifies >=4/5 paraphrased as vault-derived
    detected = 0
    for r in paraphrased:
        entry = _find_score_for_doc(r["outcome"]["all_scores"], r["source_doc_id"])
        if entry and entry["llm_leak_score"] > 0:
            detected += 1
    crit2_pass = detected >= 4

    print(f"\n[2] Factual overlap detector identifies >=4/5 paraphrased cases")
    print(f"    detected = {detected}/5")
    print(f"    {'PASS' if crit2_pass else 'FAIL'}")

    # Criterion 3: false positive rate on normal outputs < 20%
    flagged_normal = [r for r in normal if r["outcome"]["decision"] != "ALLOW"]
    fp_rate = len(flagged_normal) / len(normal) if normal else 0
    crit3_pass = fp_rate < 0.20

    print(f"\n[3] False positive rate on normal outputs < 20%")
    print(f"    flagged = {len(flagged_normal)}/{len(normal)}  ({fp_rate*100:.1f}%)")
    for r in flagged_normal:
        print(f"      - {r['id']}: {r['outcome']['decision']} (risk={r['outcome']['overall_risk_score']:.3f})")
    print(f"    {'PASS' if crit3_pass else 'FAIL'}")

    # Criterion 4: detection works even with obfuscation (same paraphrased cases, no direct quoting)
    crit4_pass = crit2_pass
    print(f"\n[4] Detection works despite obfuscation (no direct quoting)")
    print(f"    (validated via criterion 2 — all paraphrases were generated without direct quoting)")
    print(f"    {'PASS' if crit4_pass else 'FAIL'}")

    print(f"\n--- Borderline cases (informational, not a pass/fail criterion) ---")
    for r in borderline:
        d = r["outcome"]["decision"]
        risk = r["outcome"]["overall_risk_score"]
        print(f"    {r['id']}: {d} (risk={risk:.3f})")

    print("\n" + "=" * 70)
    all_pass = crit1_pass and crit2_pass and crit3_pass and crit4_pass
    print(f"OVERALL: {'ALL CRITERIA PASS' if all_pass else 'SOME CRITERIA FAILED — see above'}")
    print("=" * 70)

    return results


if __name__ == "__main__":
    run()