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

# TensorFlow is heavy (10-60 s to import on some machines). It is only needed when an LSTM model file exists or when
# training, so it is imported lazily instead of at module import (keeps app start-up instant). Behaviour is unchanged.
import importlib.util

TENSORFLOW_AVAILABLE = importlib.util.find_spec("tensorflow") is not None
_TF = None


def _load_tf():
    """Return (LSTM, Dense, Sequential, load_model, Adam), or None if TensorFlow is missing/broken."""
    global _TF, TENSORFLOW_AVAILABLE
    if _TF is None and TENSORFLOW_AVAILABLE:
        try:
            from tensorflow.keras.layers import LSTM, Dense
            from tensorflow.keras.models import Sequential, load_model
            from tensorflow.keras.optimizers import Adam

            _TF = (LSTM, Dense, Sequential, load_model, Adam)
        except Exception:
            TENSORFLOW_AVAILABLE = False
    return _TF


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
    def __init__(self, dataset_path: str, artifact_dir: str):
        self.dataset_path = Path(dataset_path)
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.scaler_path = self.artifact_dir / "scaler.joblib"
        self.kmeans_path = self.artifact_dir / "kmeans.joblib"
        self.rf_path = self.artifact_dir / "random_forest.joblib"
        self.lstm_path = self.artifact_dir / "lstm_model.keras"
        self.lstm_model = None
        self._bootstrap()

    def _bootstrap(self) -> None:
        if self.scaler_path.exists() and self.kmeans_path.exists() and self.rf_path.exists():
            self.scaler = joblib.load(self.scaler_path)
            self.kmeans = joblib.load(self.kmeans_path)
            self.random_forest = joblib.load(self.rf_path)
            if TENSORFLOW_AVAILABLE and self.lstm_path.exists():
                tf = _load_tf()
                if tf is not None:
                    self.lstm_model = tf[3](self.lstm_path)
            return

        self.train()

    def _load_dataset(self) -> pd.DataFrame:
        frame = pd.read_csv(self.dataset_path)
        frame["mood_score"] = frame["mood"].map(MOOD_MAP)
        return frame

    def _build_sequences(self, features: np.ndarray) -> np.ndarray:
        sequence_length = 3
        sequences = []
        for index in range(len(features)):
            window_start = max(0, index - sequence_length + 1)
            window = features[window_start : index + 1]
            if len(window) < sequence_length:
                padding = np.repeat(window[:1], sequence_length - len(window), axis=0)
                window = np.vstack([padding, window])
            sequences.append(window)
        return np.array(sequences)

    def train(self) -> None:
        frame = self._load_dataset()
        clustering_features = frame[["study_hours", "sleep_hours", "screen_time", "mood_score"]]
        self.scaler = StandardScaler()
        scaled_features = self.scaler.fit_transform(clustering_features)

        self.kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        frame["cluster"] = self.kmeans.fit_predict(scaled_features)

        base_features = frame[
            ["study_hours", "sleep_hours", "screen_time", "mood_score", "previous_score"]
        ].to_numpy()
        sequences = self._build_sequences(base_features)
        lstm_predictions = self._train_or_fallback_lstm(sequences, frame["future_score"].to_numpy())

        rf_features = np.column_stack([base_features, frame["cluster"].to_numpy(), lstm_predictions])
        self.random_forest = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=1)
        self.random_forest.fit(rf_features, frame["future_score"])

        joblib.dump(self.scaler, self.scaler_path)
        joblib.dump(self.kmeans, self.kmeans_path)
        joblib.dump(self.random_forest, self.rf_path)

    def _train_or_fallback_lstm(self, sequences: np.ndarray, targets: np.ndarray) -> np.ndarray:
        tf = _load_tf() if TENSORFLOW_AVAILABLE else None
        if tf is None:
            return np.clip(
                np.mean(sequences[:, :, 0], axis=1) * 12 + np.mean(sequences[:, :, 1], axis=1) * 2,
                0,
                100,
            )

        LSTM, Dense, Sequential, _load_model, Adam = tf
        self.lstm_model = Sequential(
            [
                LSTM(32, input_shape=(sequences.shape[1], sequences.shape[2])),
                Dense(16, activation="relu"),
                Dense(1),
            ]
        )
        self.lstm_model.compile(optimizer=Adam(learning_rate=0.01), loss="mse")
        self.lstm_model.fit(sequences, targets, epochs=40, batch_size=8, verbose=0)
        self.lstm_model.save(self.lstm_path)
        predictions = self.lstm_model.predict(sequences, verbose=0).flatten()
        return predictions

    def _build_feedback_insights(
        self,
        record: dict[str, Any],
        future_score: float,
        risk: str,
        confidence: float,
        previous_score: float,
    ) -> list[dict[str, Any]]:
        frame = self._load_dataset()
        avg7 = frame.tail(7)
        avg30 = frame.tail(min(30, len(frame)))

        seven_day_study = float(avg7["study_hours"].mean())
        seven_day_sleep = float(avg7["sleep_hours"].mean())
        seven_day_screen = float(avg7["screen_time"].mean())
        seven_day_previous = float(avg7["previous_score"].mean())
        seven_day_future = float(avg7["future_score"].mean())
        thirty_day_future = float(avg30["future_score"].mean())
        weekly_baseline = float(avg7["previous_score"].mean())
        thirty_day_study = float(avg30["study_hours"].mean())
        thirty_day_sleep = float(avg30["sleep_hours"].mean())
        thirty_day_screen = float(avg30["screen_time"].mean())
        night_screen_time = record["screen_time"] * (0.45 if record["mood"] in {"stressed", "tired"} else 0.30)

        predicted_shift_7d = round(((future_score - seven_day_future) / max(seven_day_future, 1)) * 100, 1)
        week_vs_month = round(((seven_day_future - thirty_day_future) / max(thirty_day_future, 1)) * 100, 1)
        next_day_focus_drop = round(max(0.0, (night_screen_time - 1.0) * 6.5), 1)
        study_gap = round(max(0.0, seven_day_study - record["study_hours"]), 1)
        sleep_gap = round(max(0.0, seven_day_sleep - record["sleep_hours"]), 1)
        screen_gap_pct = round(((record["screen_time"] - seven_day_screen) / max(seven_day_screen, 1)) * 100, 1)
        score_gap = round(future_score - previous_score, 1)
        study_vs_30 = _safe_pct_delta(record["study_hours"], thirty_day_study)
        sleep_vs_30 = _safe_pct_delta(record["sleep_hours"], thirty_day_sleep)
        screen_vs_30 = _safe_pct_delta(record["screen_time"], thirty_day_screen)
        output_vs_7 = _safe_pct_delta(future_score, seven_day_previous)
        behavior_pressure = round(max(0.0, record["screen_time"] * 2.8 - record["sleep_hours"] * 1.4), 1)

        insights: list[dict[str, Any]] = []

        if score_gap < 0:
            insights.append(
                {
                    "priority": "High" if score_gap <= -8 else "Medium",
                    "title": "Performance Drop Detected",
                    "tag": "Risk",
                    "why": f"Your projected score is {future_score:.1f}, which is {abs(score_gap):.1f} points below your current behavior baseline of {previous_score:.1f}.",
                    "impact": "This suggests your present routine is not converting effort into output as efficiently as your recent normal.",
                    "action": "Fix the lowest habit first today: improve sleep if below 7h, or cut screen time if above 4h before increasing workload.",
                    "outcome": f"+{max(6.0, abs(score_gap) * 1.1):.0f}% recovery potential if the main weak habit is corrected for 3 straight days.",
                    "confidence": min(97, int(confidence)),
                    "cta": ["Recover Today", "Review Weak Habit"],
                }
            )
        else:
            insights.append(
                {
                    "priority": "Low",
                    "title": "Performance Edge Building",
                    "tag": "Momentum",
                    "why": f"Your projected score is {score_gap:.1f} points above your current baseline of {previous_score:.1f}.",
                    "impact": "This means the current combination of recovery, focus, and effort is supporting forward momentum.",
                    "action": "Keep today simple: repeat the same sleep timing and one protected study block instead of changing too many things at once.",
                    "outcome": f"+{max(4.0, score_gap * 0.8):.0f}% continued performance upside over the next 7 days.",
                    "confidence": min(95, int(confidence - 3)),
                    "cta": ["Keep This Momentum", "Track Today"],
                }
            )

        if night_screen_time > 1.0:
            insights.append(
                {
                    "priority": "High" if night_screen_time > 1.5 else "Medium",
                    "title": "Screen Time Alert",
                    "tag": "Risk",
                    "why": f"Estimated post-10 PM screen use is {night_screen_time:.1f}h, {screen_gap_pct:+.1f}% vs your 7-day average.",
                    "impact": f"Late screen exposure is likely reducing next-day focus by about {next_day_focus_drop:.1f}% and dragging down recovery.",
                    "action": "Reduce post-10 PM screen time to under 1 hour and enable app limits for entertainment apps.",
                    "outcome": f"+{max(8.0, next_day_focus_drop):.0f}% expected concentration improvement over the next 3 days.",
                    "confidence": min(97, int(confidence)),
                    "cta": ["Enable Focus Mode", "Set Night Reminder"],
                }
            )

        if record["screen_time"] > 4.5 and record["sleep_hours"] < 7.0:
            insights.append(
                {
                    "priority": "High",
                    "title": "Sleep and Screen Collision",
                    "tag": "Risk",
                    "why": f"Screen time is {record['screen_time']:.1f}h and sleep is {record['sleep_hours']:.1f}h, a pattern that usually creates next-day recovery pressure of {behavior_pressure:.1f}.",
                    "impact": "High stimulation plus short sleep is one of the strongest combinations for weak focus, irritability, and unstable productivity.",
                    "action": "Cut evening screen use by 1 to 1.5 hours tonight and aim for at least 7.5 hours of sleep before pushing harder tomorrow.",
                    "outcome": "+15% to +20% expected next-day focus stability if both habits improve together.",
                    "confidence": min(97, int(confidence)),
                    "cta": ["Reduce Distraction", "Protect Sleep"],
                }
            )

        if record["sleep_hours"] < 7.0:
            insights.append(
                {
                    "priority": "High" if record["sleep_hours"] < 6.0 else "Medium",
                    "title": "Sleep Recovery Gap",
                    "tag": "Risk",
                    "why": f"Sleep is {record['sleep_hours']:.1f}h, which is {sleep_gap:.1f}h below your recent 7-day pattern of {seven_day_sleep:.1f}h.",
                    "impact": "Low sleep depth weakens memory consolidation, raises fatigue, and lowers stable productivity blocks the next day.",
                    "action": "Bring sleep to 7.5 to 8.0 hours for the next 5 days and keep bedtime within the same 30-minute window.",
                    "outcome": f"+{max(10.0, sleep_gap * 7):.0f}% expected productivity stability within 5 days.",
                    "confidence": min(96, int(confidence - 2 if risk == 'high' else confidence)),
                    "cta": ["Start Sleep Routine", "Set Bedtime Alert"],
                }
            )

        if 7.0 <= record["sleep_hours"] <= 8.5 and record["screen_time"] <= 3.5:
            insights.append(
                {
                    "priority": "Low",
                    "title": "Recovery Window Found",
                    "tag": "Growth",
                    "why": f"Sleep is {record['sleep_hours']:.1f}h and screen time is {record['screen_time']:.1f}h, which matches your stronger recovery zone.",
                    "impact": "This combination typically improves consistency, mental freshness, and study-to-output conversion.",
                    "action": "Keep this recovery window unchanged for the next few days and place your toughest work in the first high-energy block.",
                    "outcome": f"+{max(5.0, output_vs_7):.0f}% expected productivity support over the next week.",
                    "confidence": min(93, int(confidence - 5)),
                    "cta": ["Keep Recovery Zone", "Lock Routine"],
                }
            )

        if record["study_hours"] < seven_day_study:
            insights.append(
                {
                    "priority": "Medium",
                    "title": "Deep Work Consistency",
                    "tag": "Growth",
                    "why": f"Study time is {record['study_hours']:.1f}h today versus your 7-day average of {seven_day_study:.1f}h.",
                    "impact": "Lower study consistency reduces momentum and makes forecast gains harder to compound through the week.",
                    "action": "Add one 45 to 60 minute deep-work block during your highest-energy period tomorrow morning.",
                    "outcome": f"+{max(6.0, study_gap * 6):.0f}% expected score lift in the next 7 days if repeated daily.",
                    "confidence": min(94, int(confidence - 4)),
                    "cta": ["Schedule Deep Work", "Start 50-min Timer"],
                }
            )
        elif record["study_hours"] >= 5.0:
            insights.append(
                {
                    "priority": "Low",
                    "title": "Study Momentum Signal",
                    "tag": "Growth",
                    "why": f"Study time is {record['study_hours']:.1f}h today, {study_vs_30:+.1f}% versus your 30-day average.",
                    "impact": "Higher quality study repetition usually supports better forward score movement when recovery is also protected.",
                    "action": "Hold this study volume steady and avoid spreading effort too thin across low-value tasks.",
                    "outcome": f"+{max(4.0, record['study_hours']):.0f}% expected forecast support if sustained through the week.",
                    "confidence": min(92, int(confidence - 6)),
                    "cta": ["Protect Deep Work", "Review Study Plan"],
                }
            )

        if record["mood"] == "focused":
            insights.append(
                {
                    "priority": "Low",
                    "title": "Focused State Advantage",
                    "tag": "Momentum",
                    "why": f"Mood is focused, which historically supports better execution when sleep ({record['sleep_hours']:.1f}h) and screen control are stable.",
                    "impact": "Focused emotional state raises the chance that your planned effort turns into actual output.",
                    "action": "Use this state for your hardest task first and keep reactive work for later.",
                    "outcome": "+6% expected output efficiency if you protect the next deep-work window.",
                    "confidence": min(90, int(confidence - 7)),
                    "cta": ["Start Deep Work", "Protect Focus Block"],
                }
            )
        elif record["mood"] == "balanced":
            insights.append(
                {
                    "priority": "Low",
                    "title": "Balanced Mode Stability",
                    "tag": "Growth",
                    "why": f"Mood is balanced, giving you a stable base for consistent work without the drag of overload.",
                    "impact": "Balanced days are usually the best time to reinforce habits that keep weekly performance steady.",
                    "action": "Use this stable state to repeat your best routine instead of forcing extra workload.",
                    "outcome": "+5% expected consistency gain across the next few tracked days.",
                    "confidence": min(89, int(confidence - 8)),
                    "cta": ["Repeat Best Routine", "Track Stable Day"],
                }
            )

        if week_vs_month > 0:
            insights.append(
                {
                    "priority": "Low",
                    "title": "You Are Beating Last Month",
                    "tag": "Momentum",
                    "why": f"Your recent 7-day forecast trend is {week_vs_month:.1f}% higher than your 30-day baseline.",
                    "impact": "This means your current routine is outperforming your longer-term average and building positive momentum.",
                    "action": "Protect the habits that improved this week, especially steady sleep and reduced distraction windows.",
                    "outcome": f"If this pattern continues, productivity may improve by another +{max(4.0, predicted_shift_7d):.0f}% in the next 7 days.",
                    "confidence": min(92, int(confidence - 6)),
                    "cta": ["Keep This Routine", "Review Weekly Wins"],
                }
            )
        else:
            insights.append(
                {
                    "priority": "Medium",
                    "title": "Weekly Decline Watch",
                    "tag": "Risk",
                    "why": f"Your current 7-day trend is {abs(week_vs_month):.1f}% below your 30-day baseline.",
                    "impact": "This decline suggests recent habits are weaker than your normal standard and may keep reducing output.",
                    "action": "Return to your strongest recent routine: earlier sleep, lower night screen use, and one protected focus block daily.",
                    "outcome": f"+{max(5.0, abs(week_vs_month)):.0f}% recovery potential over the next 7 days.",
                    "confidence": min(93, int(confidence - 3)),
                    "cta": ["Reset This Week", "Compare Last 30 Days"],
                }
            )

        if record["mood"] in {"stressed", "tired"}:
            time_label = "Morning" if record["mood"] == "tired" else "Night"
            action = (
                "Use morning deep-work only after a light recovery start: hydration, sunlight, and the first focused block before notifications."
                if record["mood"] == "tired"
                else "At night, replace 20 minutes of scrolling with breathing, yoga, or a short walk to lower stress load."
            )
            insights.append(
                {
                    "priority": "High" if record["mood"] == "stressed" else "Medium",
                    "title": "Adaptive Timing Signal",
                    "tag": "Growth" if record["mood"] == "tired" else "Risk",
                    "why": f"Current mood is '{record['mood']}', which is historically linked with weaker late-day performance patterns.",
                    "impact": "Mood-driven overload tends to reduce quality focus time and lowers how efficiently study hours convert into results.",
                    "action": action,
                    "outcome": f"+{8 if record['mood'] == 'tired' else 10}% expected next-day focus recovery if followed for 3 days.",
                    "confidence": min(91, int(confidence - 5)),
                    "cta": ["Start Recovery Block", f"{time_label} Routine"],
                }
            )

        insights.append(
            {
                "priority": "High" if risk == "high" else "Medium" if risk == "medium" else "Low",
                "title": "Forward Productivity Forecast",
                "tag": "Growth" if predicted_shift_7d >= 0 else "Risk",
                "why": f"Current future score is {future_score:.1f} against a current baseline of {weekly_baseline:.1f}, with risk marked {risk}.",
                "impact": "This combines your current state, recent routine pattern, and model confidence into a forward-looking trajectory.",
                "action": "Keep only the top 1 to 2 habit changes active this week so the gains are measurable and repeatable.",
                "outcome": f"If current pattern continues, productivity will {'increase' if predicted_shift_7d >= 0 else 'decrease'} by {abs(predicted_shift_7d):.1f}% over the next 7 days.",
                "confidence": min(98, int(confidence)),
                "cta": ["Track Next 7 Days", "Review Forecast"],
            }
        )

        unique_titles: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for insight in sorted(insights, key=lambda item: (PRIORITY_ORDER[item["priority"]], -item["confidence"])):
            if insight["title"] in unique_titles:
                continue
            unique_titles.add(insight["title"])
            deduped.append(insight)
        return deduped[:5]

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
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

        seq_features = np.array(
            [
                [
                    [
                        payload["study_hours"] * 0.8,
                        payload["sleep_hours"] * 0.95,
                        payload["screen_time"] * 1.1,
                        mood_score,
                        previous_score - 6,
                    ],
                    [
                        payload["study_hours"] * 0.9,
                        payload["sleep_hours"],
                        payload["screen_time"],
                        mood_score,
                        previous_score - 2,
                    ],
                    [
                        payload["study_hours"],
                        payload["sleep_hours"],
                        payload["screen_time"],
                        mood_score,
                        previous_score,
                    ],
                ]
            ]
        )

        if self.lstm_model is not None:
            lstm_output = float(self.lstm_model.predict(seq_features, verbose=0).flatten()[0])
        else:
            lstm_output = float(
                np.clip(
                    payload["study_hours"] * 11 + payload["sleep_hours"] * 3 - payload["screen_time"] * 2.5,
                    0,
                    100,
                )
            )

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
        future_score = float(np.clip(self.random_forest.predict(rf_features)[0], 0, 100))

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
