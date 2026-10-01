"""
FutureForge — common predictor interface for every forecasting domain.

Each domain declares its input schema (`FeatureSpec`) and inherits `DomainPredictor`.

TWO honest modes (reported in every result as `source`):

  ml_model    A trained model was found in  models/<domain>/  (model.joblib + metadata.json) and its
              feature list matches this domain's schema exactly. The score is the model's output.

  rule_based  No trained model exists yet. The score is a transparent, deterministic
              "behavioural indicator" computed from the inputs by documented rules (how close each input is to a
              healthy range, weighted). It is NOT a machine-learning forecast, and `confidence` is None.

To plug in a real model later: train on real data for that domain (see scripts/train_domain_model.py), drop
model.joblib + metadata.json into models/<domain>/, restart. No page/UI code needs to change.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

log = logging.getLogger("futureforge.services")
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


@dataclass(frozen=True)
class FeatureSpec:
    name: str                       # machine name — also the column name a trained model must use
    label: str
    lo: float
    hi: float
    default: float
    step: float = 0.5
    kind: str = "optimum"           # 'higher' (more is better) | 'lower' (less is better) | 'optimum' (band is best)
    opt: tuple[float, float] = (0, 0)   # target band for kind='optimum'
    weight: float = 1.0
    unit: str = ""
    low_tip: str = ""               # advice when the value is too low / weak
    high_tip: str = ""              # advice when the value is too high
    derived: bool = False           # computed by DomainPredictor.derive(), not asked from the user


@dataclass
class PredictionResult:
    domain: str
    score: float                    # 0-100 headline number
    risk: str                       # low | medium | high
    confidence: Optional[float]     # % — only when a trained model supplies it
    pattern: str
    source: str                     # 'ml_model' | 'rule_based'
    extras: dict[str, Any] = field(default_factory=dict)       # domain-specific named metrics
    insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    suitability: dict[str, float] = field(default_factory=dict)  # per-input 0-100
    model_version: Optional[str] = None


def risk_from_score(score: float) -> str:
    """Same thresholds as the existing Student pipeline (75 / 55)."""
    return "low" if score >= 75 else "medium" if score >= 55 else "high"


class DomainPredictor:
    key: str = ""                   # registry key, also models/<key>/
    title: str = ""
    score_name: str = "Forecast Score"
    features: list[FeatureSpec] = []
    # ordered (label, predicate(v, s)) rules — first match wins; v = raw values, s = per-input suitability 0-100
    patterns: list[tuple[str, Callable[[dict, dict], bool]]] = []
    default_pattern: str = "Balanced routine"

    def __init__(self) -> None:
        self._model = None
        self._meta: dict = {}
        self._load_model()

    # ------------------------------------------------------------------ model plug-in
    @property
    def input_features(self) -> list[FeatureSpec]:
        """Features the user supplies (and a trained model would receive)."""
        return [f for f in self.features if not f.derived]

    def derive(self, v: dict) -> dict:
        """Add derived values (ratios etc.) to the validated inputs. Override."""
        return v

    @property
    def model_dir(self) -> Path:
        return MODELS_DIR / self.key

    def _load_model(self) -> None:
        mp, meta_p = self.model_dir / "model.joblib", self.model_dir / "metadata.json"
        if not (mp.exists() and meta_p.exists()):
            return
        try:
            import joblib
            meta = json.loads(meta_p.read_text())
            if list(meta.get("features", [])) != [f.name for f in self.input_features]:
                log.warning("%s: model metadata features do not match this domain's schema — ignoring model.", self.key)
                return
            self._model, self._meta = joblib.load(mp), meta
        except Exception as exc:  # corrupt / incompatible artifact must never break the page
            log.warning("%s: could not load trained model (%s) — using rule-based indicator.", self.key, exc)
            self._model, self._meta = None, {}

    @property
    def has_trained_model(self) -> bool:
        return self._model is not None

    def status(self) -> dict:
        return {"domain": self.key, "has_trained_model": self.has_trained_model,
                "model_version": self._meta.get("version"), "trained_on": self._meta.get("trained_on"),
                "expected_features": [f.name for f in self.input_features], "model_dir": str(self.model_dir)}

    # ------------------------------------------------------------------ scoring
    @staticmethod
    def _suit(spec: FeatureSpec, v: float) -> float:
        span = max(spec.hi - spec.lo, 1e-9)
        if spec.kind == "higher":
            s = (v - spec.lo) / span
        elif spec.kind == "lower":
            s = (spec.hi - v) / span
        else:
            a, b = spec.opt
            if a <= v <= b:
                s = 1.0
            elif v < a:
                s = 1 - (a - v) / max(a - spec.lo, 1e-9)
            else:
                s = 1 - (v - b) / max(spec.hi - b, 1e-9)
        return float(np.clip(s, 0, 1) * 100)

    def validate(self, values: dict) -> dict[str, float]:
        out = {}
        for f in self.input_features:
            if f.name not in values:
                raise ValueError(f"Missing input: {f.label}")
            v = float(values[f.name])
            if not f.lo <= v <= f.hi:
                raise ValueError(f"{f.label} must be between {f.lo:g} and {f.hi:g}.")
            out[f.name] = v
        return out

    def subscore(self, s: dict, names: list[str]) -> float:
        ws = {f.name: f.weight for f in self.features}
        tot = sum(ws[n] for n in names)
        return round(sum(s[n] * ws[n] for n in names) / tot, 1)

    def extras(self, v: dict, s: dict, score: float) -> dict[str, Any]:
        """Domain-specific named metrics. Override."""
        return {}

    def _ml_predict(self, v: dict) -> tuple[float, Optional[float]]:
        import pandas as pd
        cols = [f.name for f in self.input_features]
        X = pd.DataFrame([[v[c] for c in cols]], columns=cols)
        score = float(np.clip(self._model.predict(X)[0], 0, 100))
        conf = None
        est = getattr(self._model, "estimators_", None)
        if est is not None and hasattr(est[0], "predict"):     # forest: agreement between trees
            spread = float(np.std([e.predict(X.to_numpy())[0] for e in est]))
            conf = round(float(np.clip(100 - spread * 2.5, 0, 98)), 1)
        return score, conf

    def predict(self, values: dict) -> PredictionResult:
        v = self.derive(self.validate(values))
        s = {f.name: round(self._suit(f, v[f.name]), 1) for f in self.features}
        total_w = sum(f.weight for f in self.features)
        indicator = sum(s[f.name] * f.weight for f in self.features) / total_w

        if self.has_trained_model:
            score, conf = self._ml_predict(v)
            source, version = "ml_model", self._meta.get("version")
        else:
            score, conf, source, version = indicator, None, "rule_based", None
        score = round(score, 1)

        pattern = next((label for label, pred in self.patterns if pred(v, s)), self.default_pattern)
        weak = sorted((f for f in self.features if f.weight > 0 and s[f.name] < 60), key=lambda f: s[f.name])
        recs: list[str] = []
        insights: list[str] = []
        for f in weak[:4]:
            spec_low = f.kind == "higher" or (f.kind == "optimum" and v[f.name] < f.opt[0])
            tip = f.low_tip if spec_low else f.high_tip
            if tip:
                recs.append(tip)
            insights.append(f"{f.label} ({v[f.name]:.4g}{f.unit}) is pulling your score down.")
        strong = [f for f in self.features if f.weight > 0 and s[f.name] >= 85]
        if strong:
            insights.append("Strengths: " + ", ".join(f.label for f in strong[:3]) + ".")
        if not recs:
            recs.append("Your inputs are all in a healthy range — keep the routine steady and re-check next week.")

        return PredictionResult(
            domain=self.key, score=score, risk=risk_from_score(score), confidence=conf, pattern=pattern,
            source=source, extras=self.extras(v, s, score), insights=insights, recommendations=recs,
            suitability=s, model_version=version,
        )
