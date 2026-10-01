"""Fitness & Lifestyle — model-ready service."""
from .base import DomainPredictor, FeatureSpec as F


class FitnessPredictor(DomainPredictor):
    key, title, score_name = "fitness", "Fitness & Lifestyle", "Lifestyle Score"
    features = [
        F("sleep_hours", "Sleep Hours", 0, 12, 7.5, 0.5, "optimum", (7, 9), 1.5, " h",
          "Aim for 7–9 hours to support recovery and training quality.",
          "Regularly sleeping above 9 h — keep a consistent schedule and check sleep quality."),
        F("exercise_minutes", "Exercise Duration", 0, 180, 40, 5, "optimum", (30, 75), 1.5, " min",
          "Build toward 30+ minutes of movement most days, starting with what feels easy.",
          "Very long sessions need matching recovery — add a rest day or reduce intensity."),
        F("daily_steps", "Daily Activity (thousand steps)", 0, 20, 7, 0.5, "higher", weight=1.0, unit="k",
          low_tip="Add short walks — even two 10-minute walks lift daily movement."),
        F("screen_time", "Screen Time", 0, 14, 4, 0.5, "lower", weight=1.0, unit=" h",
          high_tip="Reduce non-essential screen time, especially in the hour before bed."),
        F("mood", "Mood (1-10)", 1, 10, 7, 1, "higher", weight=1.0,
          low_tip="Lower mood days: prefer gentle movement, daylight and time with people."),
        F("recovery", "Rest / Recovery (1-10)", 1, 10, 7, 1, "higher", weight=1.5,
          low_tip="Schedule an easier day, stretching or mobility work, and protect your sleep window."),
    ]
    patterns = [
        ("Under-recovered", lambda v, s: s["recovery"] < 50 and v["exercise_minutes"] >= 60),
        ("Sedentary", lambda v, s: v["exercise_minutes"] < 15 and v["daily_steps"] < 4),
        ("Active & recovered", lambda v, s: s["exercise_minutes"] >= 90 and s["recovery"] >= 70),
        ("Screen-heavy", lambda v, s: v["screen_time"] >= 8),
    ]
    default_pattern = "Balanced lifestyle"

    def extras(self, v, s, score):
        return {"Activity Balance": self.subscore(s, ["exercise_minutes", "daily_steps"]),
                "Recovery Balance": self.subscore(s, ["sleep_hours", "recovery"])}
