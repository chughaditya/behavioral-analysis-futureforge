"""Freelancer / Remote Worker — model-ready service."""
from .base import DomainPredictor, FeatureSpec as F


class FreelancerPredictor(DomainPredictor):
    key, title, score_name = "freelancer", "Freelancer / Remote Worker", "Productivity Forecast"
    features = [
        F("working_hours", "Working Hours", 0, 14, 7, 0.5, "optimum", (5, 9), 1.5, " h",
          "Anchor the day with a consistent start time and a minimum focused block.",
          "Long days erode output; set a hard stop and protect off-hours."),
        F("tasks_completed", "Tasks Completed", 0, 20, 5, 1, "higher", weight=2.0,
          low_tip="Define 3 must-do tasks each morning and finish them before anything reactive."),
        F("project_load", "Project Load (1-10)", 1, 10, 5, 1, "optimum", (3, 7), 1.0,
          low_tip="Light pipeline — set aside time for outreach or portfolio work.",
          high_tip="Too many concurrent projects: sequence them or renegotiate a deadline."),
        F("break_minutes", "Break Duration", 0, 180, 60, 5, "optimum", (40, 90), 1.0, " min",
          "Add short scheduled breaks; working from home makes them easy to skip.",
          "Long or unstructured breaks — plan them so the day keeps its rhythm."),
        F("client_workload", "Client Workload (1-10)", 1, 10, 5, 1, "optimum", (3, 7), 1.0,
          low_tip="Few active client demands — a good window for proactive work.",
          high_tip="Client demands are high: set response-time expectations and batch communication."),
        F("meeting_hours", "Meeting Hours", 0, 8, 1, 0.5, "optimum", (0, 2), 1.0, " h",
          high_tip="Move updates to async messages and batch calls into one block."),
        F("sleep_hours", "Sleep", 0, 12, 7, 0.5, "optimum", (7, 9), 1.0, " h",
          "Protect 7–9 hours — no one else will schedule your rest.",
          "Regularly sleeping above 9 h — keep a steady wake time."),
        F("focus_hours", "Focus Time", 0, 10, 4, 0.5, "higher", weight=2.0, unit=" h",
          low_tip="Block 2–3 hours of notifications-off deep work at your best time of day."),
    ]
    patterns = [
        ("Overcommitted", lambda v, s: v["project_load"] >= 8 and v["client_workload"] >= 8),
        ("Always available", lambda v, s: v["working_hours"] >= 10 and v["focus_hours"] < 3),
        ("Deep-work driven", lambda v, s: v["focus_hours"] >= 5 and v["meeting_hours"] <= 2),
        ("Reactive / interrupted", lambda v, s: v["meeting_hours"] >= 4 and v["focus_hours"] < 3),
    ]
    default_pattern = "Balanced freelance rhythm"

    def extras(self, v, s, score):
        load = (v["project_load"] + v["client_workload"]) / 2
        return {"Workload Level": "High" if load >= 7 else "Moderate" if load >= 4 else "Low",
                "Focus Score": self.subscore(s, ["focus_hours", "meeting_hours", "break_minutes"])}
