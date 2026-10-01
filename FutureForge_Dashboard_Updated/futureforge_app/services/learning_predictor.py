"""Personalized Learning — model-ready service (separate from the Student Productivity model)."""
from .base import DomainPredictor, FeatureSpec as F


class LearningPredictor(DomainPredictor):
    key, title, score_name = "personalized_learning", "Personalized Learning", "Learning Performance Forecast"
    features = [
        F("study_hours", "Study Hours", 0, 12, 3, 0.5, "optimum", (2, 6), 1.5, " h",
          "Add a short, regular study block — consistency beats occasional long sessions.",
          "Long study days show diminishing returns; split into sessions with breaks."),
        F("revision_frequency", "Revision Frequency (per week)", 0, 14, 3, 1, "optimum", (4, 8), 1.5,
          low_tip="Revise each topic at spaced intervals (next day, 3 days, 1 week).",
          high_tip="Reduce repeat revision of known material and shift time to new practice."),
        F("assignment_completion", "Assignment Completion", 0, 100, 75, 1, "higher", weight=2.0, unit="%",
          low_tip="Break assignments into small daily chunks and submit early drafts."),
        F("practice_hours", "Practice Time", 0, 8, 1.5, 0.5, "optimum", (1, 3), 1.5, " h",
          "Add active practice (problems, past papers, teaching back) rather than only re-reading.",
          "Balance heavy practice with review of mistakes."),
        F("previous_performance", "Previous Performance", 0, 100, 65, 1, "higher", weight=1.5, unit="%",
          low_tip="Review your recent mistakes and build a short list of weak topics to target."),
        F("sleep_hours", "Sleep", 0, 12, 7, 0.5, "optimum", (7, 9), 1.0, " h",
          "Sleep consolidates learning; protect 7–9 hours, especially before exams.",
          "Regularly sleeping above 9 h — keep a steady schedule."),
        F("focus_level", "Focus Level (1-10)", 1, 10, 7, 1, "higher", weight=1.5,
          low_tip="Remove your phone from the room and use 25-minute timed sessions."),
    ]
    patterns = [
        ("Crammer", lambda v, s: v["study_hours"] >= 6 and v["revision_frequency"] <= 2),
        ("Practice-driven", lambda v, s: v["practice_hours"] >= 2 and v["assignment_completion"] >= 75),
        ("Passive reader", lambda v, s: v["practice_hours"] < 0.5 and v["study_hours"] >= 3),
        ("Consistent revisor", lambda v, s: s["revision_frequency"] >= 80 and s["assignment_completion"] >= 75),
    ]
    default_pattern = "Developing learner"

    def extras(self, v, s, score):
        return {"Consistency Score": self.subscore(s, ["revision_frequency", "assignment_completion", "study_hours"])}
