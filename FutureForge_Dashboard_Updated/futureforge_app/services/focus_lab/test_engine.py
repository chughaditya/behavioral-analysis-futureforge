"""Focus Lab test engine: lookup, validation and scoring (pure logic, no UI, no DB)."""
from __future__ import annotations

from .scoring import ScoreResult, score_answers
from .tests_bank import OPTIONS, TESTS


def list_tests() -> list[dict]:
    return [{"id": k, **v} for k, v in TESTS.items()]


def get_test(test_id: str) -> dict:
    if test_id not in TESTS:
        raise KeyError(f"Unknown Focus Lab test: {test_id}")
    return {"id": test_id, **TESTS[test_id]}


def title_of(test_id: str) -> str:
    return TESTS[test_id]["title"]


def submit(test_id: str, answers: list) -> dict:
    """Validate + score. Returns a plain dict (JSON-friendly) with the score, category, observations, actions."""
    test = get_test(test_id)
    r: ScoreResult = score_answers(test, list(answers))
    return {"test_id": test_id, "title": test["title"], "icon": test["icon"], "score": r.percentage, "total": r.total,
            "max_total": r.max_total, "category": r.category, "observations": r.observations, "actions": r.actions,
            "answers": [int(a) for a in answers]}


TESTS_IDS = frozenset(TESTS)
