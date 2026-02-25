"""
lexflow-dashboard Lambda handler.

Returns aggregated metrics from all intake records for the ops dashboard.
"""

import json
import logging
import os
from collections import defaultdict

import db

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE_NAME"]
AWS_REGION     = os.environ.get("AWS_REGION", "us-east-1")


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
    }


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body, default=str),  # default=str handles Decimal from DynamoDB
    }


def lambda_handler(event, context):
    logger.info("Dashboard request received")

    # ------------------------------------------------------------------
    # BLOCK 1: Scan DynamoDB
    # ------------------------------------------------------------------
    try:
        items = db.scan_all(table_name=DYNAMODB_TABLE, region=AWS_REGION)
    except Exception as e:
        logger.error("DynamoDB scan failed | error=%s", str(e))
        return _response(500, {"error": "Failed to retrieve intake data."})

    # ------------------------------------------------------------------
    # BLOCK 2: Aggregate
    # ------------------------------------------------------------------
    total = len(items)
    by_case_type = defaultdict(int)
    by_urgency   = defaultdict(int)
    by_status    = defaultdict(int)
    viability_scores = []

    for item in items:
        # Count by case type
        by_case_type[item.get("case_type", "Unknown")] += 1

        # Count by urgency
        by_urgency[item.get("urgency", "unknown")] += 1

        # Count by status
        by_status[item.get("status", "unknown")] += 1

        # Collect viability scores (skip AI-failed records with score 0)
        score = item.get("viability_score")
        if score and int(score) > 0:
            viability_scores.append(int(score))

    avg_viability = round(sum(viability_scores) / len(viability_scores), 1) if viability_scores else 0.0
    new_count      = by_status.get("new", 0)
    critical_count = by_urgency.get("critical", 0)

    # Last 10 records sorted by timestamp descending
    sorted_items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)
    last_10 = [
        {
            "intake_id":    item.get("intake_id"),
            "timestamp":    item.get("timestamp"),
            "client_name":  item.get("client_name"),
            "case_type":    item.get("case_type"),
            "viability_score": int(item.get("viability_score", 0)),
            "urgency":      item.get("urgency"),
            "status":       item.get("status"),
            "statute_of_limitations_flag": item.get("statute_of_limitations_flag", False),
        }
        for item in sorted_items[:10]
    ]

    # ------------------------------------------------------------------
    # BLOCK 3: Return JSON
    # ------------------------------------------------------------------
    payload = {
        "total_intakes":    total,
        "avg_viability":    avg_viability,
        "new_unreviewed":   new_count,
        "critical_urgency": critical_count,
        "by_case_type":     dict(by_case_type),
        "by_urgency":       dict(by_urgency),
        "by_status":        dict(by_status),
        "last_10_intakes":  last_10,
    }

    logger.info(
        "Dashboard aggregation complete | total=%d | avg_viability=%s | critical=%d",
        total, avg_viability, critical_count,
    )

    return _response(200, payload)