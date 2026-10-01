"""Team / Project Performance — team-level analytics; model-ready service."""
from .base import DomainPredictor, FeatureSpec as F


class TeamPredictor(DomainPredictor):
    key, title, score_name = "team_project", "Team / Project Performance", "Project Performance Forecast"
    features = [
        # context inputs (weight 0 — shown and stored, used through the derived ratios below)
        F("team_size", "Team Size", 1, 50, 6, 1, "optimum", (3, 9), 0.0),
        F("tasks_completed", "Tasks Completed", 0, 500, 40, 1, "higher", weight=0.0),
        F("pending_tasks", "Pending Tasks", 0, 500, 20, 1, "lower", weight=0.0),
        F("workload", "Workload (1-10)", 1, 10, 6, 1, "optimum", (4, 7), 1.5,
          low_tip="Team capacity looks under-used — consider pulling in upcoming work.",
          high_tip="Workload is high: reprioritise the backlog, add capacity or move a deadline."),
        F("meeting_hours", "Meeting Hours (per person / week)", 0, 40, 6, 1, "optimum", (2, 8), 1.0, " h",
          high_tip="Team time is going into meetings — cut recurring syncs and use written updates."),
        F("project_progress", "Project Progress", 0, 100, 50, 1, "higher", weight=2.0, unit="%",
          low_tip="Progress is behind — identify the blocking items and assign clear owners."),
        F("deadline_pressure", "Deadline Pressure (1-10)", 1, 10, 5, 1, "lower", weight=1.5,
          high_tip="Deadline pressure is high: cut scope to a minimum deliverable and protect the critical path."),
        F("team_activity", "Team Activity (1-10)", 1, 10, 7, 1, "higher", weight=1.0,
          low_tip="Low activity — run a short check-in to surface blockers."),
        # derived
        F("completion_ratio", "Completion Ratio", 0, 100, 0, 1, "higher", weight=2.0, unit="%",
          low_tip="Pending work outweighs completed work — limit work-in-progress and finish before starting.",
          derived=True),
        F("pending_per_member", "Pending Tasks per Member", 0, 30, 0, 1, "lower", weight=1.5,
          high_tip="Backlog per person is heavy — rebalance assignments.", derived=True),
    ]
    patterns = [
        ("Overloaded team", lambda v, s: v["workload"] >= 8 and v["pending_per_member"] >= 10),
        ("Deadline-crunched", lambda v, s: v["deadline_pressure"] >= 8),
        ("Meeting-bound", lambda v, s: v["meeting_hours"] >= 12),
        ("High-throughput", lambda v, s: v["completion_ratio"] >= 70 and v["team_activity"] >= 7),
        ("Stalled", lambda v, s: v["team_activity"] <= 3 and v["project_progress"] < 40),
    ]
    default_pattern = "Steady delivery"

    def derive(self, v):
        done, pend = v["tasks_completed"], v["pending_tasks"]
        v["completion_ratio"] = round(100 * done / (done + pend), 1) if (done + pend) else 0.0
        v["pending_per_member"] = round(min(30.0, pend / max(v["team_size"], 1)), 2)
        return v

    def extras(self, v, s, score):
        tier = "High" if v["workload"] >= 8 or v["pending_per_member"] >= 12 else "Moderate" if v["workload"] >= 6 else "Low"
        return {"Progress Percentage": v["project_progress"], "Completion Ratio": v["completion_ratio"],
                "Workload Risk": tier, "Pending per Member": v["pending_per_member"]}
