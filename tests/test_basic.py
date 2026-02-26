"""
Basic smoke tests for LexFlow.
These run in CI on every push to main.
"""

def test_imports():
    """Verify core modules can be imported."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lexflow-intake'))
    import db
    import emailer
    import ai_classifier
    assert db is not None
    assert emailer is not None
    assert ai_classifier is not None


def test_valid_case_types():
    """Verify valid case types are defined."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lexflow-intake'))
    from ai_classifier import VALID_CASE_TYPES, VALID_URGENCY
    assert "Personal Injury - Vehicle Accident" in VALID_CASE_TYPES
    assert "high" in VALID_URGENCY
    assert "critical" in VALID_URGENCY


def test_cors_headers():
    """Verify CORS headers are correct."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lexflow-intake'))
    import handler
    headers = handler._cors_headers()
    assert headers["Access-Control-Allow-Origin"] == "*"
    assert "POST" in headers["Access-Control-Allow-Methods"]