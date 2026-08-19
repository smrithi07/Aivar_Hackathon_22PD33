import json
import os
import threading
from datetime import datetime, timezone

from app.config import Config

_lock = threading.Lock()


def _ensure_log_dir():
    os.makedirs(os.path.dirname(Config.AUDIT_LOG_PATH), exist_ok=True)


def log_audit_event(result: dict, source: str = "api") -> None:
    """
    Appends one structured record per /score call to the audit log
    (JSONL — one JSON object per line). Thread-safe append, safe for
    Flask's dev server and gunicorn's default sync worker.
    """
    top = result["top_match"]

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "decision": result["decision"],
        "overall_risk_score": result["overall_risk_score"],
        "text": result["text"],
        "top_match": {
            "doc_id": top["doc_id"],
            "category": top["category"],
            "entity_name": top["entity_name"],
            "similarity_score": top["similarity_score"],
            "fact_match_score": top["fact_match_score"],
            "llm_leak_score": top["llm_leak_score"],
            "matched_fields": top["matched_fields"],
        },
    }

    _ensure_log_dir()
    line = json.dumps(record)

    with _lock:
        with open(Config.AUDIT_LOG_PATH, "a") as f:
            f.write(line + "\n")


def get_recent_events(limit: int = 20, decision: str = None) -> list:
    """
    Reads the audit log back for the /audit debug endpoint.
    Returns the most recent `limit` entries, newest first,
    optionally filtered by decision (ALLOW/REVIEW/BLOCK).
    """
    if not os.path.exists(Config.AUDIT_LOG_PATH):
        return []

    with open(Config.AUDIT_LOG_PATH) as f:
        lines = f.readlines()

    events = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if decision and record.get("decision") != decision.upper():
            continue
        events.append(record)
        if len(events) >= limit:
            break

    return events