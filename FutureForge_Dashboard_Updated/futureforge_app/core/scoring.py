"""
FutureForge — Scoring Engine
Turns the HybridPredictor's raw output (future_score, risk, confidence, cluster, feedback)
into the full metric set the dashboard needs: Focus, Stress, Mood, Sleep, Productivity.

All formulas here are transparent and rule-based (documented inline) — combined with the
real ML prediction (future_score / risk / confidence / cluster) which comes straight from
the trained KMeans + LSTM/RF pipeline. Nothing is randomly generated.
"""

from __future__ import annotations

from datetime import date
from typing import Any

MOOD_TO_10 = {"focused": 9.2, "balanced": 7.4, "tired": 4.3, "stressed": 3.1}

PREDICTION_LABELS = {
    "low": "High Focus Potential",
    "medium": "Moderate Focus Potential",
    "high": "Focus At Risk",
}


def sleep_to_display(hours: float) -> str:
    h = int(hours)
    m = round((hours - h) * 60)
    if m == 60:
        h += 1
        m = 0
    return f"{h}h {m}m"


def compute_stress(payload: dict[str, Any]) -> float:
    """Stress = weighted function of screen time, sleep debt and mood.
    Higher screen time + lower sleep + negative mood -> higher stress."""
    sleep_debt = max(0.0, 8.0 - payload["sleep_hours"])
    mood_penalty = {"stressed": 22, "tired": 12, "balanced": 4, "focused": 0}.get(payload["mood"], 8)
    raw = payload["screen_time"] * 7.5 + sleep_debt * 8.5 + mood_penalty
    return round(min(100.0, max(0.0, raw)), 1)


def compute_scores(payload: dict[str, Any], prediction_result: dict[str, Any], for_date: date | None = None) -> dict[str, Any]:
    """Combine model output + rule-based formulas into the full dashboard metric set.
    `for_date` lets callers (e.g. the Weekly Log, which logs several days at once)
    compute scores for a day other than today; defaults to today for the normal
    single-day Prediction page flow."""
    focus_score = prediction_result["future_score"]  # real ML output
    stress_score = compute_stress(payload)
    mood_score = MOOD_TO_10.get(payload["mood"], 5.0)
    productivity_score = round(min(100.0, max(0.0, focus_score * 0.65 + (100 - stress_score) * 0.35)), 1)
    sleep_display = sleep_to_display(payload["sleep_hours"])

    prediction_label = PREDICTION_LABELS.get(prediction_result["risk"], "Moderate Focus Potential")

    feedback = prediction_result.get("feedback", [])
    key_factors = [f["title"] for f in feedback[:4]]
    recommendations = [f["action"] for f in feedback[:3]]
    explanation = " ".join(f["why"] for f in feedback[:2]) if feedback else ""

    target_date = for_date or date.today()

    return {
        "date": target_date.isoformat(),
        "day": target_date.strftime("%A"),
        "month": target_date.strftime("%B"),
        "year": target_date.year,
        "study_hours": payload["study_hours"],
        "sleep_hours": payload["sleep_hours"],
        "screen_time": payload["screen_time"],
        "mood": payload["mood"],
        "focus_score": focus_score,
        "stress_score": stress_score,
        "mood_score": mood_score,
        "sleep_display": sleep_display,
        "productivity_score": productivity_score,
        "prediction": prediction_label,
        "prediction_confidence": prediction_result["confidence"],
        "prediction_explanation": explanation,
        "recommendations": " | ".join(recommendations),
        "cluster": prediction_result.get("cluster", -1),
        "key_factors": key_factors,
        "risk": prediction_result["risk"],
        "feedback": feedback,
    }


def stress_label(score: float) -> str:
    if score < 35:
        return "Low"
    if score < 65:
        return "Moderate"
    return "High"


def performance_grade(focus: float, stress: float) -> str:
    """Used for calendar heatmap coloring."""
    net = focus - stress * 0.3
    if net >= 65:
        return "Excellent"
    if net >= 45:
        return "Good"
    if net >= 25:
        return "Average"
    return "Needs Attention"
