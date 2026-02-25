"""
LexFlow AI Classifier — Day 1 & 2 Test Script

Run locally before touching Lambda:
    pip install anthropic
    ANTHROPIC_API_KEY=sk-ant-... python test_classifier.py

Prints a pass/fail table for all 15 test cases.
"""

import json
import os
import sys
import time

# ---------------------------------------------------------------------------
# Inline the classifier so this script is self-contained for local testing.
# In Lambda, ai_classifier.py is imported directly.
# ---------------------------------------------------------------------------
from ai_classifier import classify

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    sys.exit("ERROR: Set ANTHROPIC_API_KEY environment variable before running.")

# ---------------------------------------------------------------------------
# 15 test cases from the blueprint + expected rough outcomes for assertion
# ---------------------------------------------------------------------------
TEST_CASES = [
    {
        "id": "TC01",
        "label": "Clear vehicle accident with injuries and police report",
        "name": "Maria Santos",
        "incident_date": "2025-01-15",
        "prior_attorney": False,
        "description": (
            "I was hit by a car while crossing at a pedestrian crossing. "
            "The driver ran a red light. I have a broken wrist and missed 3 weeks of work. "
            "I have photos and a police report."
        ),
        "expect_case_type": "Personal Injury - Vehicle Accident",
        "expect_viability_min": 7,
    },
    {
        "id": "TC02",
        "label": "Slip and fall with no witnesses",
        "name": "James O'Brien",
        "incident_date": "2025-02-01",
        "prior_attorney": False,
        "description": (
            "I slipped on a wet floor at a grocery store. There were no wet floor signs. "
            "I hurt my knee. There were no witnesses."
        ),
        "expect_case_type": "Personal Injury - Slip and Fall",
        "expect_viability_min": 4,
    },
    {
        "id": "TC03",
        "label": "Medical malpractice with documented misdiagnosis",
        "name": "Aisha Patel",
        "incident_date": "2024-11-10",
        "prior_attorney": False,
        "description": (
            "My doctor misdiagnosed my appendicitis as stomach flu. "
            "Three days later my appendix ruptured. I have all medical records showing the misdiagnosis. "
            "I spent 2 weeks in hospital and had emergency surgery."
        ),
        "expect_case_type": "Personal Injury - Medical Malpractice",
        "expect_viability_min": 7,
    },
    {
        "id": "TC04",
        "label": "Workplace injury, employer denies fault",
        "name": "Tom Reyes",
        "incident_date": "2025-01-20",
        "prior_attorney": False,
        "description": (
            "I fell from scaffolding at a construction site because the safety harness was faulty. "
            "I broke two ribs. My employer says it was my fault for not checking the equipment."
        ),
        "expect_case_type": "Personal Injury - Workplace Injury",
        "expect_viability_min": 5,
    },
    {
        "id": "TC05",
        "label": "Fender bender, client feels fine but wants to sue",
        "name": "Linda Park",
        "incident_date": "2025-02-10",
        "prior_attorney": False,
        "description": (
            "Someone rear-ended me at low speed. My car has a small scratch. "
            "I feel totally fine, no pain at all, but I want to sue them for damages."
        ),
        "expect_case_type": "Personal Injury - Vehicle Accident",
        "expect_viability_max": 4,
    },
    {
        "id": "TC06",
        "label": "Incident from 4.5 years ago (statute of limitations test)",
        "name": "David Chen",
        "incident_date": "2020-08-01",
        "prior_attorney": False,
        "description": (
            "I was injured in a car accident 4.5 years ago. The other driver was at fault. "
            "I had significant injuries but never pursued a claim."
        ),
        "expect_statute_flag": True,
    },
    {
        "id": "TC07",
        "label": "Divorce inquiry (out of scope test)",
        "name": "Sarah Bloom",
        "incident_date": "2025-02-01",
        "prior_attorney": False,
        "description": (
            "I want to file for divorce from my husband of 12 years. "
            "We have two children and shared property. I need help with custody arrangements."
        ),
        "expect_case_type": "Family Law",
    },
    {
        "id": "TC08",
        "label": "One-sentence vague description with no details",
        "name": "Anonymous User",
        "incident_date": "2025-02-01",
        "prior_attorney": False,
        "description": "I got hurt and I think someone should pay.",
        "expect_viability_max": 5,
    },
    {
        "id": "TC09",
        "label": "Client who previously settled with insurance already",
        "name": "Kevin Murray",
        "incident_date": "2024-06-15",
        "prior_attorney": True,
        "description": (
            "I was in a car accident last year and already settled with the insurance company. "
            "I signed papers but now I think the settlement was too low. Can I reopen the case?"
        ),
    },
    {
        "id": "TC10",
        "label": "Clear case but client is also partially at fault",
        "name": "Rachel Kim",
        "incident_date": "2025-01-05",
        "prior_attorney": False,
        "description": (
            "I was jaywalking when a car hit me. The driver was speeding. "
            "I have a broken leg and missed 6 weeks of work. I know I wasn't supposed to cross there."
        ),
        "expect_case_type": "Personal Injury - Vehicle Accident",
    },
    {
        "id": "TC11",
        "label": "Construction site accident with multiple parties",
        "name": "Marco Russo",
        "incident_date": "2024-12-01",
        "prior_attorney": False,
        "description": (
            "I was injured on a construction site. The general contractor, a subcontractor, "
            "and the equipment manufacturer may all be responsible. I have a fractured pelvis "
            "and will be unable to work for 6 months. OSHA is already investigating."
        ),
        "expect_case_type": "Personal Injury - Workplace Injury",
        "expect_viability_min": 7,
    },
    {
        "id": "TC12",
        "label": "Dog bite in a public park",
        "name": "Fatima Al-Hassan",
        "incident_date": "2025-02-05",
        "prior_attorney": False,
        "description": (
            "A dog attacked me in a public park. The owner was present. "
            "I needed 12 stitches on my arm. I have photos of the injuries and the owner's contact info."
        ),
    },
    {
        "id": "TC13",
        "label": "Non-English description (robustness test)",
        "name": "Hans Mueller",
        "incident_date": "2025-01-25",
        "prior_attorney": False,
        "description": (
            "Ich hatte einen Autounfall. Der andere Fahrer hat eine rote Ampel überfahren. "
            "Ich habe mir das Bein gebrochen und war 2 Wochen im Krankenhaus."
        ),
    },
    {
        "id": "TC14",
        "label": "Emotional distress claim only, no physical injury",
        "name": "Grace Thompson",
        "incident_date": "2025-01-10",
        "prior_attorney": False,
        "description": (
            "I witnessed a terrible car accident right in front of me. "
            "I have severe PTSD and anxiety now. I have not been physically injured "
            "but I cannot work or sleep. I am seeing a therapist."
        ),
    },
    {
        "id": "TC15",
        "label": "Clearly fraudulent-sounding claim",
        "name": "Mike Dollar",
        "incident_date": "2025-02-14",
        "prior_attorney": False,
        "description": (
            "I want to sue my neighbor for 10 million dollars because their tree "
            "made a shadow on my garden. I also slipped on a leaf from that tree "
            "but I wasn't hurt. This is definitely worth millions."
        ),
        "expect_viability_max": 3,
    },
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"


def check(result: dict, tc: dict) -> list[str]:
    """Return list of failure reasons. Empty = pass."""
    failures = []

    if "expect_case_type" in tc:
        if result["case_type"] != tc["expect_case_type"]:
            failures.append(
                f"case_type expected '{tc['expect_case_type']}', got '{result['case_type']}'"
            )

    if "expect_viability_min" in tc:
        if result["viability_score"] < tc["expect_viability_min"]:
            failures.append(
                f"viability_score {result['viability_score']} < expected min {tc['expect_viability_min']}"
            )

    if "expect_viability_max" in tc:
        if result["viability_score"] > tc["expect_viability_max"]:
            failures.append(
                f"viability_score {result['viability_score']} > expected max {tc['expect_viability_max']}"
            )

    if "expect_statute_flag" in tc:
        if result["statute_of_limitations_flag"] != tc["expect_statute_flag"]:
            failures.append(
                f"statute_of_limitations_flag expected {tc['expect_statute_flag']}, got {result['statute_of_limitations_flag']}"
            )

    return failures


def run_tests():
    results_log = []
    passed = 0
    failed = 0

    print(f"\n{'='*80}")
    print("  LexFlow AI Classifier — Stress Test Suite")
    print(f"{'='*80}\n")

    for tc in TEST_CASES:
        print(f"[{tc['id']}] {tc['label']}")
        start = time.time()

        try:
            result = classify(
                name=tc["name"],
                description=tc["description"],
                incident_date=tc["incident_date"],
                prior_attorney=tc["prior_attorney"],
                api_key=API_KEY,
            )
            elapsed_ms = int((time.time() - start) * 1000)

            failures = check(result, tc)
            status = PASS if not failures else FAIL

            print(f"  Status     : {status}")
            print(f"  case_type  : {result['case_type']}")
            print(f"  viability  : {result['viability_score']}/10")
            print(f"  urgency    : {result['urgency']}")
            print(f"  sol_flag   : {result['statute_of_limitations_flag']}")
            print(f"  key_facts  : {len(result['key_facts'])} facts")
            print(f"  time       : {elapsed_ms}ms")

            if failures:
                for f in failures:
                    print(f"  {FAIL}: {f}")
                failed += 1
            else:
                passed += 1

            results_log.append({
                "id": tc["id"],
                "label": tc["label"],
                "passed": not failures,
                "result": result,
                "elapsed_ms": elapsed_ms,
                "failures": failures,
            })

        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            print(f"  Status     : {FAIL} (EXCEPTION)")
            print(f"  Error      : {e}")
            failed += 1
            results_log.append({
                "id": tc["id"],
                "label": tc["label"],
                "passed": False,
                "error": str(e),
                "elapsed_ms": elapsed_ms,
                "failures": [str(e)],
            })

        print()

    # Summary
    print(f"{'='*80}")
    print(f"  Results: {passed} passed / {failed} failed / {len(TEST_CASES)} total")

    if failed == 0:
        print(f"  {PASS} All test cases passed.")
    elif failed <= 1:
        print(f"  {WARN} {failed} failure — within acceptable range for Day 2 target (14/15).")
    else:
        print(f"  {FAIL} {failed} failures — review prompt and re-run failing cases.")

    print(f"{'='*80}\n")

    # Write full results to JSON for review
    with open("test_results.json", "w") as f:
        json.dump(results_log, f, indent=2)
    print("  Full results written to test_results.json\n")


if __name__ == "__main__":
    run_tests()
