import logging

from flask import Blueprint, jsonify, render_template, request
from app.audit.logger import log_audit_event, get_recent_events
from app.risk_engine.scorer import evaluate_text
from app.config import Config
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("semantic-dlp-gateway")

api_bp = Blueprint("api", __name__)


@api_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "semantic-dlp-gateway"}), 200


@api_bp.route("/vault", methods=["GET"])
def list_vault():
    """
    Debug/demo endpoint: lists vault documents by metadata only
    (doc_id, category, entity_name) — does NOT expose field values,
    since that would defeat the point of a protected vault.
    """
    try:
        with open(Config.VAULT_PATH) as f:
            vault = json.load(f)
    except FileNotFoundError:
        return jsonify({"error": "Vault not found. Run scripts/build_vault.py first."}), 500
    except Exception as e:
        logger.exception("Failed to load vault")
        return jsonify({"error": f"Internal error loading vault: {str(e)}"}), 500

    summary = [
        {
            "doc_id": doc["doc_id"],
            "category": doc["category"],
            "entity_name": doc["entity_name"],
        }
        for doc in vault
    ]
    return jsonify({"count": len(summary), "documents": summary}), 200


@api_bp.route("/score", methods=["POST"])
def score():
    """
    Core detection endpoint. Accepts JSON: {"text": "<candidate agent output>"}
    Returns the risk engine's decision, score, and per-document breakdown.
    """
    body = request.get_json(silent=True)

    if body is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    text = body.get("text")
    if not text or not isinstance(text, str) or not text.strip():
        return jsonify({"error": "'text' field is required and must be a non-empty string"}), 400

    try:
        result = evaluate_text(text)
    except Exception as e:
        logger.exception("evaluate_text failed")
        return jsonify({"error": f"Internal error during evaluation: {str(e)}"}), 500

    logger.info(
        f"SCORE decision={result['decision']} risk={result['overall_risk_score']} "
        f"top_doc={result['top_match']['doc_id']}"
    )
    log_audit_event(result)

    return jsonify(result), 200

@api_bp.route("/audit", methods=["GET"])
def audit():
    """
    Debug/demo endpoint: returns the most recent audit log entries.
    Query params: ?limit=20&decision=BLOCK
    """
    limit = request.args.get("limit", default=20, type=int)
    decision = request.args.get("decision", default=None, type=str)

    try:
        events = get_recent_events(limit=limit, decision=decision)
    except Exception as e:
        logger.exception("Failed to read audit log")
        return jsonify({"error": f"Internal error reading audit log: {str(e)}"}), 500

    return jsonify({"count": len(events), "events": events}), 200