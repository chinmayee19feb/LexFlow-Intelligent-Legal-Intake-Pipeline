"""
lexflow-intake Lambda handler.
Receives client intake form submissions, runs AI classification,
saves to DynamoDB, and sends confirmation emails.
"""
import json
import logging
import os
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import ai_classifier
import db
import emailer

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE  = os.environ["DYNAMODB_TABLE_NAME"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
ATTORNEY_EMAIL  = os.environ["ATTORNEY_EMAIL"]
FROM_EMAIL      = os.environ["FROM_EMAIL"]
AWS_REGION      = os.environ.get("AWS_REGION", "us-east-1")

REQUIRED_FIELDS = {"client_name", "client_email", "client_phone", "incident_date", "description"}

def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }

def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }

def lambda_handler(event, context):
    # Handle CORS preflight
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "OPTIONS":
        return _response(200, {})

    # Route to portal handler if path is /portal
    path = event.get("rawPath", "")
    if path == "/portal":
        if method == "OPTIONS":
            return {"statusCode": 200, "headers": PORTAL_CORS_HEADERS, "body": ""}
        return handle_portal(event)

    logger.info("Intake request received")

    # Parse body
    try:
        raw_body = event.get("body", "{}")
        if isinstance(raw_body, str):
            body = json.loads(raw_body)
        else:
            body = raw_body or {}
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON body | error=%s", str(e))
        return _response(400, {"error": "Invalid JSON in request body."})

    # Validate required fields
    missing = REQUIRED_FIELDS - body.keys()
    if missing:
        logger.warning("Missing required fields | fields=%s", missing)
        return _response(400, {"error": f"Missing required fields: {sorted(missing)}"})

    client_name    = body["client_name"].strip()
    client_email   = body["client_email"].strip()
    client_phone   = body["client_phone"].strip()
    incident_date  = body["incident_date"].strip()
    description    = body["description"].strip()
    prior_attorney = bool(body.get("prior_attorney", False))

    # Run AI classification
    try:
        ai_result = ai_classifier.classify(
            name=client_name,
            description=description,
            incident_date=incident_date,
            prior_attorney=prior_attorney,
            api_key=ANTHROPIC_KEY,
        )
        logger.info(
            "AI classification complete | case_type=%s | score=%s | urgency=%s",
            ai_result["case_type"], ai_result["viability_score"], ai_result["urgency"]
        )
    except Exception as e:
        logger.error("AI classification failed | error=%s", str(e))
        return _response(500, {"error": "AI classification failed. Please try again."})

    # Build record
    intake_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    record = {
        "intake_id":                   intake_id,
        "timestamp":                   timestamp,
        "client_name":                 client_name,
        "client_email":                client_email,
        "client_phone":                client_phone,
        "incident_date":               incident_date,
        "prior_attorney":              prior_attorney,
        "raw_description":             description,
        "case_type":                   ai_result["case_type"],
        "viability_score":             ai_result["viability_score"],
        "urgency":                     ai_result["urgency"],
        "statute_of_limitations_flag": ai_result["statute_of_limitations_flag"],
        "key_facts":                   ai_result["key_facts"],
        "recommended_specialty":       ai_result["recommended_specialty"],
        "recommended_action":          ai_result["recommended_action"],
        "client_acknowledgment":       ai_result["client_acknowledgment"],
        "ai_model_used":               "claude-haiku-4-5",
        "status":                      "new",
        "attorney_note":               "",
        "portal_token":                secrets.token_urlsafe(32),
    }

    # Save to DynamoDB
    try:
        db.put_item(table_name=DYNAMODB_TABLE, item=record, region=AWS_REGION)
        logger.info("DynamoDB record saved | intake_id=%s", intake_id)
    except Exception as e:
        logger.error("DynamoDB save failed | error=%s", str(e))
        return _response(500, {"error": "Failed to save intake record."})

    # Send emails
    try:
        portal_url = f"https://d18dh3vfl8g5tq.cloudfront.net/portal.html?token={record['portal_token']}"
        emailer.send_client_ack(
            to_email=client_email,
            client_name=client_name,
            case_type=ai_result["case_type"],
            acknowledgment_text=ai_result["client_acknowledgment"],
            portal_url=portal_url,
            from_email=FROM_EMAIL,
            region=AWS_REGION,
        )
        emailer.send_attorney_alert(
            to_email=ATTORNEY_EMAIL,
            record=record,
            from_email=FROM_EMAIL,
            region=AWS_REGION,
        )
        logger.info("Emails sent | intake_id=%s", intake_id)
    except Exception as e:
        logger.warning("Email sending failed | error=%s", str(e))

    logger.info("Intake complete | intake_id=%s", intake_id)
    return _response(200, {
        "intake_id": intake_id,
        "message":   "Your inquiry has been received. We will be in touch shortly.",
        "status":    "received",
    })

    REQUIRED_FIELDS = {"client_name", "client_email", "client_phone", "incident_date", "description"}
    PORTAL_CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}


def handle_portal(event):
    """GET /portal?token=xxx — returns case status for client portal."""
    params = event.get("queryStringParameters") or {}
    token = params.get("token", "").strip()

    if not token:
        return {
            "statusCode": 400,
            "headers": {**PORTAL_CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing token."}),
        }

    record = db.get_by_token(
        table_name=DYNAMODB_TABLE,
        portal_token=token,
        region=AWS_REGION,
    )

    if not record:
        return {
            "statusCode": 404,
            "headers": {**PORTAL_CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({"error": "Case not found. Your link may have expired."}),
        }

    # Return only what the client needs — never expose attorney notes or AI internals
    safe = {
        "client_name":   record.get("client_name"),
        "case_type":     record.get("case_type"),
        "status":        record.get("status", "new"),
        "timestamp":     record.get("timestamp"),
        "incident_date": record.get("incident_date"),
    }
    return {
        "statusCode": 200,
        "headers": {**PORTAL_CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(safe, default=str),
    }
