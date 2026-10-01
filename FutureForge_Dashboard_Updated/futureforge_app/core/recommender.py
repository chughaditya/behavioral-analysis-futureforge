"""
FutureForge — Smart Recommendation engine.

Takes the forecast produced for ANY user input (Student: trained hybrid ML pipeline; other domains: their
DomainPredictor) and turns it into:

  * which Focus Lab test to take right now, and why
  * a focus plan (session length, break, number of blocks)

The mapping is deterministic and documented below — it is a rule layer ON TOP of the model's score/risk, so
the recommendation always follows the model output and every result reports where the score came from
(`source`: 'ml_model' or 'rule_based'). No randomness, no fabricated numbers.

Pure logic (no Streamlit import) so it can be unit-tested directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd

TESTS = ("Reaction Time", "Stroop Test", "Attention Grid", "Memory Sequence")

# Score band -> preferred test order (first = best fit). Bands reuse the app's risk thresholds (75 / 55).
_ORDER = {
    "high":   ["Memory Sequence", "Stroop Test", "Attention Grid", "Reaction Time"],   # fresh -> challenge the brain
    "medium": ["Attention Grid", "Stroop Test", "Memory Sequence", "Reaction Time"],   # steady -> train sustained focus
    "low":    ["Reaction Time", "Attention Grid", "Stroop Test", "Memory Sequence"],   # depleted -> quick, light check
}
_WHY = {
    "Reaction Time":   "quick 1-minute alertness check — the lightest of the four.",
    "Attention Grid":  "trains sustained attention (spot the target, avoid wrong cells).",
    "Stroop Test":     "measures focus under distraction (read the colour, ignore the word).",
    "Memory Sequence": "working-memory challenge — the most demanding of the four.",
}
# Score band -> focus plan: (session minutes, break minutes, blocks)
_PLAN = {"high": (50, 10, 3), "medium": (25, 5, 4), "low": (15, 5, 2)}
_REPEAT_WINDOW = timedelta(days=2)


@dataclass
class Recommendation:
    band: str                        # high | medium | low
    test: str
    test_reason: str
    alternatives: list[str]
    session_minutes: int
    break_minutes: int
    blocks: int
    headline: str
    reasons: list[str] = field(default_factory=list)
    ranking: list[tuple[str, str]] = field(default_factory=list)   # all 4 Focus Lab tests, best fit first, with reason
    source: str = "rule_based"       # copied from the forecast: 'ml_model' | 'rule_based'
    confidence: Optional[float] = None
    score: float = 0.0

    @property
    def total_focus_minutes(self) -> int:
        return self.session_minutes * self.blocks


def band_for(score: float) -> str:
    return "high" if score >= 75 else "medium" if score >= 55 else "low"


def _recent_tests(tests_df: Optional[pd.DataFrame]) -> set[str]:
    if tests_df is None or tests_df.empty or "created_at" not in tests_df.columns:
        return set()
    ts = pd.to_datetime(tests_df["created_at"], errors="coerce")
    recent = tests_df[ts >= datetime.now() - _REPEAT_WINDOW]
    return set(recent["test_type"])


def recommend(score: float, inputs: dict[str, Any], *, source: str = "rule_based", confidence: Optional[float] = None,
              suitability: Optional[dict[str, float]] = None, tests_df: Optional[pd.DataFrame] = None) -> Recommendation:
    """Build a recommendation from a forecast score and the user's raw inputs.

    `inputs`       raw input values (any domain); recognised by name: sleep*, screen*/distraction*, mood, stress*
    `suitability`  optional per-input 0-100 closeness-to-healthy-range (domain predictors provide it)
    `tests_df`     optional past Focus Lab results, used to avoid repeating a test taken in the last 2 days
    """
    score = float(score)
    band = band_for(score)
    order = list(_ORDER[band])
    reasons = [f"Forecast score {score:.0f}/100 → {band} band."]
    plan_min, brk, blocks = _PLAN[band]

    # --- input-driven overrides (only what the user's own inputs justify) --------------------------------
    sleep_bad = screen_bad = mood_bad = False
    for name, val in inputs.items():
        n = name.lower()
        try:
            v = float(val)
        except (TypeError, ValueError):
            v = None
        weak = suitability is not None and suitability.get(name, 100) < 60
        if "sleep" in n and v is not None and (v < 6 or weak):
            sleep_bad = True
        if ("screen" in n or "distraction" in n) and v is not None and (weak or (suitability is None and v >= 6)):
            screen_bad = True
        if n == "mood" and str(val).lower() in ("tired", "stressed"):
            mood_bad = True
        if "stress" in n and v is not None and (weak or (suitability is None and v >= 7)):
            mood_bad = True

    if sleep_bad or mood_bad:
        order.insert(0, order.pop(order.index("Reaction Time")))
        plan_min, brk = min(plan_min, 20), max(brk, 5)
        reasons.append("Low sleep / tired or stressed state → start with the light Reaction Time check and use shorter blocks.")
    elif screen_bad:
        order.insert(0, order.pop(order.index("Attention Grid")))
        reasons.append("High screen / distraction load → Attention Grid targets sustained attention.")

    # --- avoid repeating a test the user already took in the last 2 days ------------------------------------
    recent = _recent_tests(tests_df)
    test = next((t for t in order if t not in recent), order[0])
    if test != order[0]:
        reasons.append(f"You already took {order[0]} in the last 2 days, so the next best test is suggested.")

    headline = {"high": "You're in good form — go for a deep-work block.",
                "medium": "Decent focus — build it with steady, structured sessions.",
                "low": "Focus is at risk today — keep it light and recover first."}[band]
    if band == "low":
        reasons.append("Consider fixing sleep / reducing screen time before long study sessions.")
    return Recommendation(band=band, test=test, test_reason=_WHY[test], alternatives=[t for t in order if t != test],
                          ranking=[(t, _WHY[t]) for t in [test] + [x for x in order if x != test]],
                          session_minutes=plan_min, break_minutes=brk, blocks=blocks, headline=headline,
                          reasons=reasons, source=source, confidence=confidence, score=score)


# ------------------------------------------------------------------ adapters: user input -> model -> recommendation
def from_student(hybrid_predictor, payload: dict[str, Any], tests_df: Optional[pd.DataFrame] = None) -> Recommendation:
    """Student: run the ALREADY-TRAINED hybrid pipeline on the user's inputs, then recommend."""
    raw = hybrid_predictor.predict({k: payload[k] for k in ("study_hours", "sleep_hours", "screen_time", "mood")})
    return recommend(raw["future_score"], payload, source="ml_model", confidence=raw.get("confidence"), tests_df=tests_df)


def from_domain(key: str, values: dict[str, Any], tests_df: Optional[pd.DataFrame] = None) -> Recommendation:
    """Any other domain: use its DomainPredictor (ML if a trained model is installed, else the rule-based indicator)."""
    from services.registry import get_predictor
    r = get_predictor(key).predict(values)
    return recommend(r.score, values, source=r.source, confidence=r.confidence, suitability=r.suitability, tests_df=tests_df)
