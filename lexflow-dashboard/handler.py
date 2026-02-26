"""
lexflow-dashboard Lambda handler.

Routes:
  GET  /dashboard              → aggregated metrics
  GET  /case/{intake_id}       → full case detail
  POST /case/{intake_id}/status → update case status (accept/decline)
"""

import json
import logging
import os
from collections import defaultdict

import db

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE_NAME"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

VALID_STATUSES = {"active", "declined", "needs_review", "new", "claimed", "closed"}


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def handle_dashboard(event, context):
    """GET /dashboard — aggregated metrics."""
    logger.info("Dashboard request received")

    try:
        items = db.scan_all(table_name=DYNAMODB_TABLE, region=AWS_REGION)
    except Exception as e:
        logger.error("DynamoDB scan failed | error=%s", str(e))
        return _response(500, {"error": "Failed to retrieve intake data."})

    total = len(items)
    by_case_type = defaultdict(int)
    by_urgency = defaultdict(int)
    by_status = defaultdict(int)
    viability_scores = []

    for item in items:
        by_case_type[item.get("case_type", "Unknown")] += 1
        by_urgency[item.get("urgency", "unknown")] += 1
        by_status[item.get("status", "unknown")] += 1
        score = item.get("viability_score")
        if score and int(score) > 0:
            viability_scores.append(int(score))

    avg_viability = round(sum(viability_scores) / len(viability_scores), 1) if viability_scores else 0.0
    new_count = by_status.get("new", 0)
    critical_count = by_urgency.get("critical", 0)

    sorted_items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)
    last_10 = [
        {
            "intake_id": item.get("intake_id"),
            "timestamp": item.get("timestamp"),
            "client_name": item.get("client_name"),
            "case_type": item.get("case_type"),
            "viability_score": int(item.get("viability_score", 0)),
            "urgency": item.get("urgency"),
            "status": item.get("status"),
            "statute_of_limitations_flag": item.get("statute_of_limitations_flag", False),
        }
        for item in sorted_items[:10]
    ]

    payload = {
        "total_intakes": total,
        "avg_viability": avg_viability,
        "new_unreviewed": new_count,
        "critical_urgency": critical_count,
        "by_case_type": dict(by_case_type),
        "by_urgency": dict(by_urgency),
        "by_status": dict(by_status),
        "last_10_intakes": last_10,
    }

    logger.info("Dashboard complete | total=%d | avg_viability=%s", total, avg_viability)
    return _response(200, payload)


def handle_case_detail(intake_id: str):
    """GET /case/{intake_id} — full case details."""
    logger.info("Case detail request | intake_id=%s", intake_id)

    try:
        item = db.get_item(
            table_name=DYNAMODB_TABLE,
            intake_id=intake_id,
            region=AWS_REGION
        )
    except Exception as e:
        logger.error("DynamoDB get failed | intake_id=%s | error=%s", intake_id, str(e))
        return _response(500, {"error": "Failed to retrieve case."})

    if not item:
        return _response(404, {"error": "Case not found."})

    return _response(200, item)


def handle_status_update(intake_id: str, body: dict):
    """POST /case/{intake_id}/status — accept or decline a case."""
    logger.info("Status update request | intake_id=%s", intake_id)

    new_status = body.get("status", "").strip().lower()
    attorney_note = body.get("note", "").strip()

    if new_status not in VALID_STATUSES:
        return _response(400, {
            "error": f"Invalid status '{new_status}'. Must be one of: {', '.join(VALID_STATUSES)}"
        })

    try:
        db.update_status(
            table_name=DYNAMODB_TABLE,
            intake_id=intake_id,
            new_status=new_status,
            note=attorney_note,
            region=AWS_REGION
        )
    except Exception as e:
        logger.error("Status update failed | intake_id=%s | error=%s", intake_id, str(e))
        return _response(500, {"error": "Failed to update case status."})

    logger.info("Status updated | intake_id=%s | status=%s", intake_id, new_status)
    return _response(200, {
        "intake_id": intake_id,
        "status": new_status,
        "message": f"Case successfully marked as {new_status}."
    })


def lambda_handler(event, context):
    """Main router — dispatches to correct handler based on path."""
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/dashboard")

    logger.info("Request | method=%s | path=%s", method, path)

    # Handle CORS preflight
    if method == "OPTIONS":
        return _response(200, {})

    # Route: GET /dashboard
    if path == "/dashboard" and method == "GET":
        return handle_dashboard(event, context)

    # Route: GET /case/{intake_id}
    if path.startswith("/case/") and method == "GET" and not path.endswith("/status"):
        intake_id = path.split("/case/")[1]
        return handle_case_detail(intake_id)

    # Route: POST /case/{intake_id}/status
    if path.startswith("/case/") and path.endswith("/status") and method == "POST":
        intake_id = path.split("/case/")[1].replace("/status", "")
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _response(400, {"error": "Invalid JSON body."})
        return handle_status_update(intake_id, body)

    return _response(404, {"error": f"Route not found: {method} {path}"})