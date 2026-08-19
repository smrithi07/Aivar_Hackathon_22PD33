import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app

app = create_app()
client = app.test_client()

print("=== /score x2 (populate audit log) ===")
client.post("/score", json={
    "text": "Cassian Vane's compensation includes a $115,000 salary and $12,500 bonus."
})
client.post("/score", json={
    "text": "The weather today is sunny with a light breeze."
})
print("done\n")

print("=== /audit (default) ===")
resp = client.get("/audit")
print(resp.status_code)
data = resp.get_json()
print(f"count: {data['count']}")
for e in data["events"]:
    print(f"  {e['timestamp']}  {e['decision']}  risk={e['overall_risk_score']}  doc={e['top_match']['doc_id']}")
print()

print("=== /audit?decision=BLOCK ===")
resp = client.get("/audit?decision=BLOCK")
data = resp.get_json()
print(f"count: {data['count']}  (should only include BLOCK entries)")