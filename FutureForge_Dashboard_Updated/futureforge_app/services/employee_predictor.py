"""Employee Productivity — model-ready service (no trained employee model ships yet)."""
from .base import DomainPredictor, FeatureSpec as F


def _level(x: float) -> str:
    return "High" if x >= 7 else "Moderate" if x >= 4 else "Low"


class EmployeePredictor(DomainPredictor):
    key, title, score_name = "employee", "Employee Productivity", "Productivity Forecast"
    features = [
        F("working_hours", "Working Hours", 0, 14, 8, 0.5, "optimum", (6, 9), 1.5, " h",
          "Very short days may mean blocked or fragmented work — check what is stopping focused time.",
          "Long days usually cut output per hour; cap the day and protect recovery time."),
        F("task_completion", "Task Completion Rate", 0, 100, 70, 1, "higher", weight=2.0, unit="%",
          low_tip="Pick the 2–3 tasks that matter most and finish them before opening new ones."),
        F("meeting_hours", "Meeting Hours", 0, 10, 2, 0.5, "optimum", (0, 3), 1.0, " h",
          high_tip="Trim or shorten recurring meetings; batch the rest to leave uninterrupted blocks."),
        F("break_minutes", "Break Duration", 0, 180, 60, 5, "optimum", (40, 90), 1.0, " min",
          "Take short breaks (5–10 min every 60–90 min) to sustain attention.",
          "Very long breaks can fragment the day; keep them shorter and more regular."),
        F("workload", "Workload (1-10)", 1, 10, 6, 1, "optimum", (4, 7), 1.5,
          low_tip="Capacity is under-used — consider taking on a stretch task.",
          high_tip="Workload is high: renegotiate deadlines or delegate before quality suffers."),
        F("sleep_hours", "Sleep Hours", 0, 12, 7, 0.5, "optimum", (7, 9), 1.5, " h",
          "Aim for 7–9 hours; sleep debt is one of the most consistent drags on work output.",
          "Consistently sleeping more than 9 h can point to poor sleep quality — keep a steady schedule."),
        F("energy", "Mood / Energy (1-10)", 1, 10, 7, 1, "higher", weight=1.5,
          low_tip="Low energy: schedule demanding work for your best hours and add a short walk."),
    ]
    patterns = [
        ("Overloaded", lambda v, s: v["workload"] >= 8 and v["working_hours"] >= 10),
        ("Meeting-heavy", lambda v, s: v["meeting_hours"] >= 5),
        ("Recovery-limited", lambda v, s: s["sleep_hours"] < 55 and v["energy"] <= 5),
        ("Steady high performer", lambda v, s: v["task_completion"] >= 80 and s["sleep_hours"] >= 75),
        ("Under-utilised", lambda v, s: v["workload"] <= 3 and v["task_completion"] < 60),
    ]
    default_pattern = "Balanced work rhythm"

    def extras(self, v, s, score):
        return {"Workload Level": _level(v["workload"]),
                "Recovery Index": self.subscore(s, ["sleep_hours", "energy", "break_minutes"])}
