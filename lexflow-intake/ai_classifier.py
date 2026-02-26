import json
import logging
import anthropic
from prompt import SYSTEM_PROMPT, USER_TEMPLATE

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {
    "case_type",
    "viability_score",
    "urgency",
    "statute_of_limitations_flag",
    "key_facts",
    "recommended_specialty",
    "recommended_action",
    "client_acknowledgment",
}

VALID_CASE_TYPES = {
    # Personal Injury
    "Personal Injury - Vehicle Accident",
    "Personal Injury - Slip and Fall",
    "Personal Injury - Medical Malpractice",
    "Personal Injury - Workplace Injury",
    # Defamation & False Accusation
    "Defamation - Libel (Written)",
    "Defamation - Slander (Spoken)",
    "Malicious Prosecution - False Criminal Accusation",
    "Malicious Prosecution - Workplace False Accusation",
    "Malicious Prosecution - False Sexual Misconduct Accusation",
    # Other
    "Family Law",
    "Employment Law",
    "Out of Scope",
}

VALID_URGENCY = {"low", "medium", "high", "critical"}


def _strip_fences(text: str) -> str:
    """Remove accidental markdown code fences from model output."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        content = parts[1]
        if content.startswith("json"):
            content = content[4:]
        return content.strip()
    return text


def _validate(result: dict) -> None:
    """Raise ValueError on any schema violation."""
    missing = REQUIRED_KEYS - result.keys()
    if missing:
        raise ValueError(f"Missing required keys: {missing}")

    if result["case_type"] not in VALID_CASE_TYPES:
        raise ValueError(f"Invalid case_type: '{result['case_type']}'")

    if result["urgency"] not in VALID_URGENCY:
        raise ValueError(f"Invalid urgency: '{result['urgency']}'")

    score = result["viability_score"]
    if not isinstance(score, int) or score < 0 or score > 10:
        raise ValueError(f"viability_score out of range: {score}")


    if not isinstance(result["statute_of_limitations_flag"], bool):
        raise ValueError("statute_of_limitations_flag must be a boolean")

    facts = result["key_facts"]
    if not isinstance(facts, list) or not (3 <= len(facts) <= 5):
        raise ValueError(f"key_facts must be a list of 3-5 strings, got {len(facts) if isinstance(facts, list) else type(facts)}")
    for i, fact in enumerate(facts):
        if not isinstance(fact, str):
            raise ValueError(f"key_facts[{i}] is not a string")

    for field in ("recommended_specialty", "recommended_action", "client_acknowledgment"):
        if not isinstance(result[field], str) or not result[field].strip():
            raise ValueError(f"'{field}' must be a non-empty string")


def classify(
    name: str,
    description: str,
    incident_date: str,
    prior_attorney: bool,
    api_key: str,
) -> dict:
    """
    Call Claude to classify a legal intake submission.
    Returns a validated dict with all required fields.
    Raises an exception if the API call fails or response is invalid.
    """
    client = anthropic.Anthropic(api_key=api_key)

    user_message = USER_TEMPLATE.format(
        name=name,
        incident_date=incident_date,
        prior_attorney="Yes" if prior_attorney else "No",
        description=description,
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        temperature=0.1,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_message}
        ],
    )

    raw_text = response.content[0].text
    logger.debug("Raw Claude response: %s", raw_text)

    cleaned = _strip_fences(raw_text)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed. Raw text was: %s", raw_text)
        raise ValueError(f"Claude returned invalid JSON: {e}") from e

    _validate(result)

    logger.info(
        "Classification complete | case_type=%s | viability=%s | urgency=%s",
        result["case_type"],
        result["viability_score"],
        result["urgency"],
    )

    return result