"""
Student Productivity — thin adapter over the EXISTING trained pipeline.

Reuses hybrid_pipeline.HybridPredictor (StandardScaler + K-Means + LSTM/statistical fallback + Random Forest)
and core.scoring exactly as the Student page does. Nothing is retrained and no artifacts are moved or renamed:
the trained files stay in backend/data/artifacts/. The Student page itself (pages/1_Prediction.py) is unchanged
and does not depend on this file; this adapter exists so Student can be used through the same interface.
"""
from __future__ import annotations

from typing import Any

from .base import PredictionResult, risk_from_score

STUDENT_INPUTS = ("study_hours", "sleep_hours", "screen_time", "mood")


class StudentPredictor:
    key, title, score_name = "student", "Student Productivity", "Focus / Productivity Forecast"

    def __init__(self, hybrid_predictor=None) -> None:
        if hybrid_predictor is None:
            from core.theme import load_predictor
            hybrid_predictor = load_predictor()
        self._hp = hybrid_predictor

    @property
    def has_trained_model(self) -> bool:
        return True

    def predict(self, values: dict[str, Any]) -> PredictionResult:
        from core import scoring
        payload = {k: values[k] for k in STUDENT_INPUTS}
        raw = self._hp.predict(payload)
        m = scoring.compute_scores(payload, raw)
        return PredictionResult(
            domain=self.key, score=raw["future_score"], risk=raw["risk"] or risk_from_score(raw["future_score"]),
            confidence=raw["confidence"], pattern=f"Behavioral cluster #{raw['cluster']}", source="ml_model",
            extras={"Stress Score": m["stress_score"], "Productivity Score": m["productivity_score"]},
            insights=list(m.get("key_factors", [])), recommendations=list(m.get("recommendations", [])),
        )
