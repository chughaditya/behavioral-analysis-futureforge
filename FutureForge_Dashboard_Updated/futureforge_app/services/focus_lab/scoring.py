"""Focus Lab scoring — real, deterministic scores from the user's answers (no randomness)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .tests_bank import OPTIONS

MAX_POINTS = len(OPTIONS) - 1          # 3 points per question
CATEGORIES = [(80, "Strong"), (60, "Moderate"), (40, "Needs Attention"), (0, "High Attention")]
_CATEGORY_TEXT = {
    "Strong": "is a strength right now",
    "Moderate": "is fairly steady, with room to improve",
    "Needs Attention": "needs attention",
    "High Attention": "is the area with the most room for improvement",
}


@dataclass
class ScoreResult:
    total: int
    max_total: int
    percentage: int
    category: str
    observations: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    points: list[int] = field(default_factory=list)


def category_for(pct: float) -> str:
    return next(name for lo, name in CATEGORIES if pct >= lo)


def question_points(answer_idx: int, reverse: bool) -> int:
    return MAX_POINTS - answer_idx if reverse else answer_idx


def score_answers(test: dict, answers: list[int]) -> ScoreResult:
    qs = test["questions"]
    if len(answers) != len(qs) or any(a is None for a in answers):
        raise ValueError(f"Please answer all {len(qs)} questions.")
    if any((not isinstance(a, int)) or not 0 <= a < len(OPTIONS) for a in answers):
        raise ValueError("Invalid answer value.")
    pts = [question_points(a, rev) for a, (_, rev) in zip(answers, qs)]
    total, mx = sum(pts), MAX_POINTS * len(qs)
    pct = int(round(total / mx * 100))
    cat = category_for(pct)

    weakest = sorted(range(len(qs)), key=lambda i: pts[i])[:2]
    obs = [f"Your responses indicate {test['area']} {_CATEGORY_TEXT[cat]}."]
    for i in weakest:
        if pts[i] <= 1:
            text, rev = qs[i]
            obs.append(f"{'Reported often' if rev else 'Reported less often'}: “{text.rstrip('.')}”.")
    if len(obs) == 1 and cat != "Strong":
        obs.append("No single answer stands out — small improvements across the board will help.")
    actions = test["actions"][:2] + ["Re-take this test in 2–3 weeks to track your progress."] if cat == "Strong" else list(test["actions"])
    return ScoreResult(total, mx, pct, cat, obs, actions, pts)
