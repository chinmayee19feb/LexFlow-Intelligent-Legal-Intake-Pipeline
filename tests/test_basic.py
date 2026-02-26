"""
Basic smoke tests for LexFlow.
These run in CI on every push to main.
"""
import sys
import os

# Set required env vars once at the top before any imports
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["DYNAMODB_TABLE_NAME"] = "test-table"
os.environ["ATTORNEY_EMAIL"] = "test@test.com"
os.environ["FROM_EMAIL"] = "noreply@test.com"

# Add lexflow-intake to path once at the top
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lexflow-intake'))


def test_imports():
    """Verify core modules can be imported."""
    import db
    import emailer
    import ai_classifier
    assert db is not None
    assert emailer is not None
    assert ai_classifier is not None


def test_valid_case_types():
    """Verify valid case types are defined."""
    from ai_classifier import VALID_CASE_TYPES, VALID_URGENCY
    assert "Personal Injury - Vehicle Accident" in VALID_CASE_TYPES
    assert "Personal Injury - Slip and Fall" in VALID_CASE_TYPES
    assert "high" in VALID_URGENCY
    assert "critical" in VALID_URGENCY
    assert "low" in VALID_URGENCY


def test_cors_headers():
    """Verify CORS headers are correct."""
    import handler
    headers = handler._cors_headers()
    assert headers["Access-Control-Allow-Origin"] == "*"
    assert headers["Access-Control-Allow-Methods"] is not None
    assert len(headers["Access-Control-Allow-Methods"]) > 0