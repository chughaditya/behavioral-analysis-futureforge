"""
Risk -> Focus Lab test recommendation engine (rule-based, deterministic, no randomness).

analyze(domain, values, score=..., risk=..., suitability=...) looks at the prediction that was just produced and returns
a `Recommendation`: whether a meaningful risk exists, the ranked risk areas, and the Focus Lab test for each area.
Every domain has its OWN rule table, and each risk area maps to a different test.

Domain predictors provide per-input suitability (0-100, closeness to a healthy range); a rule fires when any of its
inputs scores below TRIGGER_BELOW. Student uses the trained model's focus/stress scores plus its raw inputs.
Neutral behavioural wording only — this is not a medical or psychological assessment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

TRIGGER_BELOW = 60          # same "weak input" cut-off the domain predictors use (suitability below 60)
STRONG_SIGNAL = 70          # severity that justifies a card even when the overall risk level is 'low'


@dataclass
class RiskArea:
    key: str
    label: str
    test_id: str
    why: str
    severity: float          # 0-100, higher = needs more attention


@dataclass
class Recommendation:
    domain: str
    has_risk: bool
    risk_level: str                                   # low | medium | high (from the prediction)
    headline: str
    primary: Optional[RiskArea] = None
    others: list[RiskArea] = field(default_factory=list)   # up to 2 more areas, each with a different test

    @property
    def test_ids(self) -> list[str]:
        return [a.test_id for a in ([self.primary] if self.primary else []) + self.others]


# (key, label, test_id, features, why)
_R = lambda key, label, test, feats, why: (key, label, test, tuple(feats), why)

RULES: dict[str, list] = {
    "employee": [
        _R("workload", "Workload Balance", "workload_management", ["workload", "working_hours", "meeting_hours"],
           "Your work pattern shows workload-related pressure (hours, workload or meeting time)."),
        _R("task_completion", "Task Completion", "time_management", ["task_completion"],
           "Task completion is lower than your pattern suggests it could be — time use is worth reviewing."),
        _R("focus_energy", "Work Focus & Energy", "work_focus", ["energy", "break_minutes", "sleep_hours"],
           "Energy, breaks or sleep are outside a steady range, which can affect work focus."),
    ],
    "fitness": [
        _R("routine", "Activity & Routine", "lifestyle_consistency", ["exercise_minutes", "daily_steps", "screen_time"],
           "Activity level or screen habits suggest your daily routine could be more consistent."),
        _R("sleep", "Sleep Consistency", "sleep_routine", ["sleep_hours"],
           "Your sleep duration is outside a steady range — a pattern to monitor."),
        _R("recovery", "Recovery & Habits", "habit_consistency", ["recovery", "mood"],
           "Recovery or mood is below a steady range — steadier daily habits may help."),
    ],
    "digital_wellbeing": [
        _R("screen", "Screen & Social Media Use", "digital_distraction", ["screen_time", "social_media"],
           "Screen and social-media time is high, which can pull attention away from planned tasks."),
        _R("focus", "Focus Sessions", "focus_consistency", ["focus_sessions", "break_frequency"],
           "Few focus sessions or irregular breaks point to inconsistent focus."),
        _R("balance", "Screen-Time Balance", "screen_time_management", ["study_work"],
           "Study/work time versus screen time looks unbalanced."),
        _R("habits", "Digital Habits & Routine", "digital_habit", ["sleep_hours", "mood"],
           "Sleep or mood patterns suggest your digital habits are worth a closer look."),
    ],
    "personalized_learning": [
        _R("consistency", "Learning Consistency", "learning_consistency", ["study_hours", "revision_frequency"],
           "Study or revision frequency is outside a steady range."),
        _R("assignments", "Assignments & Practice", "study_habit", ["assignment_completion", "practice_hours"],
           "Assignment completion or practice time is lower than ideal."),
        _R("focus", "Focus Level", "focus_consistency", ["focus_level", "sleep_hours"],
           "Focus level or sleep is below a steady range."),
        _R("performance", "Study Time Use", "time_management", ["previous_performance"],
           "Recent performance suggests reviewing how study time is used."),
    ],
    "freelancer": [
        _R("workload", "Workload Balance", "workload_balance", ["project_load", "client_workload"],
           "Project and client load is outside a comfortable range."),
        _R("hours", "Working Hours & Breaks", "time_management", ["working_hours", "break_minutes", "sleep_hours"],
           "Long or irregular working hours, breaks or sleep — time use is worth reviewing."),
        _R("completion", "Task Completion", "task_prioritization", ["tasks_completed"],
           "Completed tasks are lower than ideal — clearer prioritisation may help."),
        _R("focus", "Remote-Work Focus", "remote_work_focus", ["focus_hours", "meeting_hours"],
           "Deep-work time is limited, possibly by meetings or scattered focus."),
    ],
    "team_project": [
        _R("workload", "Team Workload", "team_workload", ["workload", "team_size"],
           "Workload per team looks outside a comfortable range."),
        _R("completion", "Task Completion", "task_prioritization", ["tasks_completed", "pending_tasks", "pending_per_member"],
           "Pending work is high relative to what is being completed."),
        _R("deadline", "Deadline & Project Progress", "project_risk", ["deadline_pressure", "project_progress"],
           "Deadline pressure is high or progress is behind — a pattern to monitor."),
        _R("time", "Meetings & Team Activity", "time_management", ["meeting_hours", "team_activity"],
           "Meeting load or team activity suggests time use is worth reviewing."),
    ],
    "gamer": [
        _R("session", "Session Length & Breaks", "session_management", ["session_minutes", "break_frequency"],
           "Long sessions with few breaks can lower performance late in a session."),
        _R("sleep", "Sleep Consistency", "sleep_routine", ["sleep_hours"],
           "Sleep is outside a steady range, which commonly affects reaction and focus."),
        _R("routine", "Gaming Routine", "gaming_routine", ["gaming_hours"],
           "Total daily gaming time is outside a balanced range."),
        _R("performance", "Performance & Focus", "focus_consistency", ["previous_performance", "reaction_score", "focus_level"],
           "Recent performance, reaction or focus is below your best range."),
    ],
    "habit_routine": [
        _R("sleep", "Sleep Regularity", "sleep_routine", ["sleep_consistency"],
           "Sleep timing looks irregular."),
        _R("routine", "Routine Stability", "routine_stability", ["routine_consistency"],
           "Routine consistency is lower than ideal."),
        _R("digital", "Screen Habits", "digital_habit", ["screen_time"],
           "Screen time is high relative to a steady routine."),
        _R("habits", "Activity & Breaks", "habit_consistency", ["exercise_frequency", "break_frequency", "mood"],
           "Exercise, breaks or mood patterns suggest habits could be more consistent."),
    ],
}
FALLBACK = {   # medium/high risk but no single input stands out
    "employee": ("Overall Work Pattern", "work_productivity"), "fitness": ("Overall Lifestyle Pattern", "lifestyle_consistency"),
    "digital_wellbeing": ("Overall Digital Pattern", "digital_habit"), "personalized_learning": ("Overall Learning Pattern", "learning_consistency"),
    "freelancer": ("Overall Work Pattern", "time_management"), "team_project": ("Overall Project Pattern", "project_risk"),
    "gamer": ("Overall Gaming Pattern", "gaming_routine"), "habit_routine": ("Overall Routine Pattern", "habit_consistency"),
    "student": ("Overall Study Pattern", "time_management"),
}
_TITLES = {"student": "productivity", "employee": "productivity", "fitness": "lifestyle", "digital_wellbeing": "digital well-being",
           "personalized_learning": "learning", "freelancer": "work", "team_project": "project", "gamer": "performance",
           "habit_routine": "routine"}


def _student_areas(v: dict, score: float, extras: dict) -> list[RiskArea]:
    out: list[RiskArea] = []
    if score < 75:
        out.append(RiskArea("focus", "Focus Consistency", "focus_consistency",
                            "Your productivity pattern indicates that focus consistency needs attention.", round(100 - score, 1)))
    screen = float(v.get("screen_time", 0))
    if screen >= 6:
        out.append(RiskArea("screen", "Screen Time & Distraction", "digital_distraction",
                            "High screen time can pull attention away from study.", min(100.0, 40 + (screen - 6) * 10)))
    study = float(v.get("study_hours", 6))
    if study < 3:
        out.append(RiskArea("study", "Study Consistency", "study_habit",
                            "Study time is low, so building a steadier study habit may help.", min(100.0, 60 + (3 - study) * 10)))
    sleep = float(v.get("sleep_hours", 8))
    if sleep < 6 or str(v.get("mood", "")).lower() in ("tired", "stressed"):
        out.append(RiskArea("routine", "Routine & Recovery", "routine_consistency",
                            "Sleep or mood suggests your daily routine could be steadier.", min(100.0, 50 + max(0.0, 6 - sleep) * 10)))
    stress = float(extras.get("stress_score", 0))
    if stress >= 60:
        out.append(RiskArea("time", "Time Management", "time_management",
                            "A high pressure score suggests reviewing how your time is planned.", stress))
    return out


def _rule_areas(domain: str, v: dict, suit: dict) -> list[RiskArea]:
    out: list[RiskArea] = []
    for key, label, test, feats, why in RULES.get(domain, []):
        vals = [suit[f] for f in feats if f in suit]
        if vals and min(vals) < TRIGGER_BELOW:
            out.append(RiskArea(key, label, test, why, round(100 - min(vals), 1)))
    return out


def analyze(domain: str, values: dict[str, Any], *, score: float, risk: str,
            suitability: Optional[dict[str, float]] = None, extras: Optional[dict] = None) -> Recommendation:
    if domain != "student" and domain not in RULES:
        raise KeyError(f"Unknown domain: {domain}")
    areas = _student_areas(values, float(score), extras or {}) if domain == "student" else _rule_areas(domain, values, suitability or {})
    areas.sort(key=lambda a: -a.severity)                      # stable: table order breaks ties
    level = risk if risk in ("low", "medium", "high") else "medium"
    strong = bool(areas) and areas[0].severity >= STRONG_SIGNAL
    if level == "low" and not strong:
        return Recommendation(domain, False, level, "Your current behavioral pattern looks stable.")
    if not areas:
        label, test = FALLBACK[domain]
        areas = [RiskArea("overall", label, test, "Your overall pattern has room for improvement.", round(100 - float(score), 1))]
    seen, uniq = set(), []
    for a in areas:                                             # one card entry per distinct test
        if a.test_id not in seen:
            seen.add(a.test_id); uniq.append(a)
    topic = _TITLES[domain]
    headline = (f"Your current {topic} risk level is {level.capitalize()} — a pattern to monitor." if level != "low"
                else f"Your {topic} pattern looks stable overall, with one area worth a closer look.")
    return Recommendation(domain, True, level, headline, uniq[0], uniq[1:3])


def analyze_result(domain: str, values: dict, result, ) -> Recommendation:
    """Adapter for a services.base.PredictionResult (all non-student domains)."""
    return analyze(domain, values, score=result.score, risk=result.risk, suitability=result.suitability, extras=result.extras)


def analyze_student(payload: dict, metrics: dict) -> Recommendation:
    """Adapter for the Student page: `metrics` = scoring.compute_scores(...) output (model result already inside)."""
    return analyze("student", payload, score=metrics["focus_score"], risk=metrics.get("risk") or "medium",
                   extras={"stress_score": metrics.get("stress_score", 0)})
