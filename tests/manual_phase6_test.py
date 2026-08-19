import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app

app = create_app()
client = app.test_client()

print("=== /health ===")
resp = client.get("/health")
print(resp.status_code, resp.get_json())
print()

print("=== /vault ===")
resp = client.get("/vault")
print(resp.status_code)
data = resp.get_json()
print(f"count: {data.get('count')}")
for doc in data.get("documents", [])[:3]:
    print(" ", doc)
print()

print("=== /score — missing text field (expect 400) ===")
resp = client.post("/score", json={})
print(resp.status_code, resp.get_json())
print()

print("=== /score — valid leak text (expect 200, BLOCK) ===")
resp = client.post("/score", json={
    "text": "Cassian Vane's compensation includes a $115,000 salary and $12,500 bonus, "
            "effective from his April 15, 2023 start date in the Quantum Logistics division."
})
print(resp.status_code)
data = resp.get_json()
print(f"decision: {data['decision']}  risk: {data['overall_risk_score']}")
print(f"top match: {data['top_match']['doc_id']}")