from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

# ============= MOOD MAPPING =============
MOOD_MAP = {
    "focused": 3,
    "balanced": 2,
    "tired": 1,
    "stressed": 0,
}

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def _safe_pct_delta(current: float, baseline: float) -> float:
    return round(((current - baseline) / max(baseline, 1.0)) * 100, 1)


class HybridPredictor:
    """Simplified Hybrid ML Model (No TensorFlow required!)"""
    
    def __init__(self, dataset_path: str, artifact_dir: str):
        self.dataset_path = Path(dataset_path)
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.scaler_path = self.artifact_dir / "scaler.joblib"
        self.kmeans_path = self.artifact_dir / "kmeans.joblib"
        self.rf_path = self.artifact_dir / "random_forest.joblib"
        self.rf_model = None
        self.scaler = None
        self.kmeans = None
        self._bootstrap()

    def _bootstrap(self) -> None:
        """Load or train models"""
        if self.scaler_path.exists() and self.kmeans_path.exists() and self.rf_path.exists():
            self.scaler = joblib.load(self.scaler_path)
            self.kmeans = joblib.load(self.kmeans_path)
            self.rf_model = joblib.load(self.rf_path)
            return

        self.train()

    def _load_dataset(self) -> pd.DataFrame:
        """Load and prepare dataset"""
        frame = pd.read_csv(self.dataset_path)
        frame["mood_score"] = frame["mood"].map(MOOD_MAP)
        return frame

    def train(self) -> None:
        """Train the model ensemble"""
        print("🚀 Training Hybrid Model (K-Means + Random Forest)...")
        
        frame = self._load_dataset()
        
        # Feature selection
        clustering_features = frame[["study_hours", "sleep_hours", "screen_time", "mood_score"]]
        
        # StandardScaler
        self.scaler = StandardScaler()
        scaled_features = self.scaler.fit_transform(clustering_features)

        # K-Means Clustering
        print("  📊 Training K-Means clustering...")
        self.kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        frame["cluster"] = self.kmeans.fit_predict(scaled_features)

        # Prepare features for Random Forest
        base_features = frame[
            ["study_hours", "sleep_hours", "screen_time", "mood_score", "previous_score"]
        ].to_numpy()
        
        # Create LSTM-like features (sequence simulation using heuristics)
        lstm_predictions = self._simulate_lstm(base_features, frame["future_score"].to_numpy())

        # Random Forest Ensemble
        rf_features = np.column_stack([base_features, frame["cluster"].to_numpy(), lstm_predictions])
        
        print("  🌳 Training Random Forest regressor...")
        self.rf_model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1, max_depth=10)
        self.rf_model.fit(rf_features, frame["future_score"])

        # Save models
        joblib.dump(self.scaler, self.scaler_path)
        joblib.dump(self.kmeans, self.kmeans_path)
        joblib.dump(self.rf_model, self.rf_path)
        
        print("✅ Models trained and saved!")

    def _simulate_lstm(self, features: np.ndarray, targets: np.ndarray) -> np.ndarray:
        """Simulate LSTM predictions using heuristics (no TensorFlow needed)"""
        # Weighted average of features as a simple time-series approximation
        study_weight = features[:, 0] * 12
        sleep_weight = features[:, 1] * 3
        screen_weight = features[:, 2] * -2.5
        
        predictions = np.clip(study_weight + sleep_weight + screen_weight, 0, 100)
        return predictions

    def _build_feedback_insights(
        self,
        record: dict[str, Any],
        future_score: float,
        risk: str,
        confidence: float,
        previous_score: float,
    ) -> list[dict[str, Any]]:
        """Generate AI-powered insights"""
        frame = self._load_dataset()
        avg7 = frame.tail(7)
        avg30 = frame.tail(min(30, len(frame)))

        seven_day_study = float(avg7["study_hours"].mean())
        seven_day_sleep = float(avg7["sleep_hours"].mean())
        seven_day_screen = float(avg7["screen_time"].mean())
        seven_day_previous = float(avg7["previous_score"].mean())
        seven_day_future = float(avg7["future_score"].mean())
        thirty_day_future = float(avg30["future_score"].mean())
        thirty_day_study = float(avg30["study_hours"].mean())
        thirty_day_sleep = float(avg30["sleep_hours"].mean())
        thirty_day_screen = float(avg30["screen_time"].mean())

        predicted_shift_7d = round(((future_score - seven_day_future) / max(seven_day_future, 1)) * 100, 1)
        week_vs_month = round(((seven_day_future - thirty_day_future) / max(thirty_day_future, 1)) * 100, 1)
        score_gap = round(future_score - previous_score, 1)

        insights: list[dict[str, Any]] = []

        # Performance Drop Insight
        if score_gap < 0:
            insights.append(
                {
                    "priority": "High" if score_gap <= -8 else "Medium",
                    "title": "Performance Drop Detected",
                    "tag": "Risk",
                    "why": f"Your projected score is {future_score:.1f}, which is {abs(score_gap):.1f} points below baseline.",
                    "impact": "Current routine is not efficient",
                    "action": "Improve sleep (7h+) or reduce screen time (<4h)",
                    "outcome": f"+{max(6.0, abs(score_gap) * 1.1):.0f}% recovery if corrected",
                    "confidence": min(89, int(confidence - 8)),
                    "cta": ["Improve Sleep", "Reduce Screen Time"],
                }
            )

        # Balanced Mood Insight
        if record["mood"] == "balanced":
            insights.append(
                {
                    "priority": "Low",
                    "title": "Mood is Balanced",
                    "tag": "Growth",
                    "why": "Balanced state provides stable base",
                    "impact": "Perfect time to reinforce good habits",
                    "action": "Repeat your best routine today",
                    "outcome": "+5% expected consistency",
                    "confidence": min(89, int(confidence - 8)),
                    "cta": ["Repeat Routine", "Track Day"],
                }
            )

        # Weekly Trend
        if week_vs_month > 0:
            insights.append(
                {
                    "priority": "Low",
                    "title": "You Are Beating Last Month",
                    "tag": "Momentum",
                    "why": f"7-day average is {week_vs_month:.1f}% higher than 30-day",
                    "impact": "Building positive momentum",
                    "action": "Protect habits that improved this week",
                    "outcome": f"+{max(4.0, predicted_shift_7d):.0f}% next week",
                    "confidence": min(92, int(confidence - 6)),
                    "cta": ["Keep Routine", "Review Wins"],
                }
            )

        # Mood Signal
        if record["mood"] in {"stressed", "tired"}:
            insights.append(
                {
                    "priority": "High" if record["mood"] == "stressed" else "Medium",
                    "title": "Adaptive Timing Signal",
                    "tag": "Growth" if record["mood"] == "tired" else "Risk",
                    "why": f"Current mood '{record['mood']}' linked with weaker performance",
                    "impact": "Mood affects productivity patterns",
                    "action": "Take recovery break or adjust schedule",
                    "outcome": f"+{8 if record['mood'] == 'tired' else 10}% next day",
                    "confidence": min(91, int(confidence - 5)),
                    "cta": ["Start Recovery", "Adjust Schedule"],
                }
            )

        # Forward Forecast
        insights.append(
            {
                "priority": "High" if risk == "high" else "Medium" if risk == "medium" else "Low",
                "title": "Forward Productivity Forecast",
                "tag": "Growth" if predicted_shift_7d >= 0 else "Risk",
                "why": f"Score {future_score:.1f} with {risk} risk level",
                "impact": "Combined prediction for next week",
                "action": "Focus on 1-2 key habit improvements",
                "outcome": f"Will {'increase' if predicted_shift_7d >= 0 else 'decrease'} by {abs(predicted_shift_7d):.1f}%",
                "confidence": min(98, int(confidence)),
                "cta": ["Track Next 7 Days", "View Forecast"],
            }
        )

        # Deduplicate
        unique_titles: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for insight in sorted(insights, key=lambda item: (PRIORITY_ORDER[item["priority"]], -item["confidence"])):
            if insight["title"] in unique_titles:
                continue
            unique_titles.add(insight["title"])
            deduped.append(insight)
        
        return deduped[:5]

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Make prediction"""
        mood_score = MOOD_MAP.get(payload["mood"], 1)
        previous_score = max(
            25.0,
            min(95.0, payload["study_hours"] * 9 + payload["sleep_hours"] * 4 - payload["screen_time"] * 3),
        )
        
        base_row = pd.DataFrame(
            [
                {
                    "study_hours": payload["study_hours"],
                    "sleep_hours": payload["sleep_hours"],
                    "screen_time": payload["screen_time"],
                    "mood_score": mood_score,
                }
            ]
        )
        
        cluster = int(self.kmeans.predict(self.scaler.transform(base_row))[0])

        # LSTM simulation
        lstm_output = float(
            np.clip(
                payload["study_hours"] * 11 + payload["sleep_hours"] * 3 - payload["screen_time"] * 2.5,
                0,
                100,
            )
        )

        # Random Forest prediction
        rf_features = np.array(
            [
                [
                    payload["study_hours"],
                    payload["sleep_hours"],
                    payload["screen_time"],
                    mood_score,
                    previous_score,
                    cluster,
                    lstm_output,
                ]
            ]
        )
        
        future_score = float(np.clip(self.rf_model.predict(rf_features)[0], 0, 100))

        # Risk assessment
        if future_score >= 75:
            risk = "low"
        elif future_score >= 55:
            risk = "medium"
        else:
            risk = "high"

        confidence = float(np.clip(72 + abs(future_score - 50) / 2.3 + (8 if cluster == 1 else 4), 0, 98))

        return {
            "future_score": round(future_score, 1),
            "risk": risk,
            "confidence": round(confidence, 1),
            "cluster": cluster,
            "feedback": self._build_feedback_insights(payload, future_score, risk, confidence, previous_score),
        }
