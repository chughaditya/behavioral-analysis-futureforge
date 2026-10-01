"""Digital Well-being — behavioural / productivity insights only (no medical or psychological diagnosis)."""
from .base import DomainPredictor, FeatureSpec as F


class DigitalWellbeingPredictor(DomainPredictor):
    key, title, score_name = "digital_wellbeing", "Digital Well-being", "Digital Well-being Score"
    features = [
        F("screen_time", "Screen Time", 0, 16, 6, 0.5, "lower", weight=1.5, unit=" h",
          high_tip="Set a daily screen budget and schedule screen-free blocks."),
        F("social_media", "Social Media Usage", 0, 8, 2, 0.5, "lower", weight=1.5, unit=" h",
          high_tip="Use app timers or move social apps off your home screen during focus hours."),
        F("study_work", "Study/Work Time", 0, 12, 6, 0.5, "optimum", (4, 8), 1.0, " h",
          "Aim for a few dependable focus blocks rather than one big push.",
          "Very long study/work days tend to reduce quality — cap the day."),
        F("sleep_hours", "Sleep Hours", 0, 12, 7, 0.5, "optimum", (7, 9), 1.0, " h",
          "Try a screen curfew 60 minutes before bed to protect sleep time.",
          "Regularly sleeping above 9 h — keep a steady wake time."),
        F("break_frequency", "Break Frequency (per day)", 0, 15, 5, 1, "optimum", (4, 8), 1.0,
          low_tip="Take a 5-minute screen-free break roughly every 60–90 minutes.",
          high_tip="Very frequent breaks may be interrupting deep work — try longer focus blocks."),
        F("focus_sessions", "Focus Sessions (per day)", 0, 10, 3, 1, "higher", weight=1.5,
          low_tip="Start with one 25-minute distraction-free session and build from there."),
        F("mood", "Mood (1-10)", 1, 10, 7, 1, "higher", weight=0.5,
          low_tip="On low-mood days, keep goals small and take a short walk away from screens."),
    ]
    patterns = [
        ("Social-media dominant", lambda v, s: v["social_media"] >= 4),
        ("Always-on", lambda v, s: v["screen_time"] >= 10 and v["break_frequency"] < 3),
        ("Fragmented focus", lambda v, s: v["focus_sessions"] <= 1 and v["screen_time"] >= 6),
        ("Deliberate digital use", lambda v, s: s["screen_time"] >= 65 and v["focus_sessions"] >= 3),
    ]
    default_pattern = "Mixed digital habits"

    def extras(self, v, s, score):
        return {"Focus Index": self.subscore(s, ["focus_sessions", "break_frequency", "social_media", "study_work"])}
