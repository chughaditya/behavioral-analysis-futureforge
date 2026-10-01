"""Registry of the 9 forecasting domains (single source of truth for sidebar, dashboard cards, pages, history)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .digital_wellbeing_predictor import DigitalWellbeingPredictor
from .employee_predictor import EmployeePredictor
from .fitness_predictor import FitnessPredictor
from .freelancer_predictor import FreelancerPredictor
from .gamer_predictor import GamerPredictor
from .habit_predictor import HabitPredictor
from .learning_predictor import LearningPredictor
from .team_predictor import TeamPredictor


@dataclass(frozen=True)
class Domain:
    key: str
    title: str
    icon: str
    blurb: str
    page: str                      # Streamlit page path
    predictor_cls: Optional[type]  # None => Student (existing pipeline / existing page)


DOMAINS: list[Domain] = [
    Domain("student", "Student Productivity", "🎓", "Forecast study focus with the trained hybrid ML pipeline.", "pages/1_Prediction.py", None),
    Domain("employee", "Employee Productivity", "💼", "Work hours, workload and energy behind your output.", "pages/10_Employee_Productivity.py", EmployeePredictor),
    Domain("fitness", "Fitness & Lifestyle", "🏃", "Sleep, exercise and recovery balance.", "pages/11_Fitness_Lifestyle.py", FitnessPredictor),
    Domain("digital_wellbeing", "Digital Well-being", "📱", "Screen habits, focus sessions and breaks.", "pages/12_Digital_Wellbeing.py", DigitalWellbeingPredictor),
    Domain("personalized_learning", "Personalized Learning", "📚", "Revision, practice and consistency for learners.", "pages/13_Personalized_Learning.py", LearningPredictor),
    Domain("freelancer", "Freelancer / Remote Worker", "💻", "Project load, client demand and deep-work time.", "pages/14_Freelancer_Remote.py", FreelancerPredictor),
    Domain("team_project", "Team / Project Performance", "👥", "Team throughput, backlog and deadline pressure.", "pages/15_Team_Project.py", TeamPredictor),
    Domain("gamer", "Gamer Performance", "🎮", "Session length, sleep and focus for gaming form.", "pages/16_Gamer_Performance.py", GamerPredictor),
    Domain("habit_routine", "Habit & Routine Forecasting", "🔄", "Routine consistency and habit patterns over time.", "pages/17_Habit_Routine.py", HabitPredictor),
]
BY_KEY = {d.key: d for d in DOMAINS}
_cache: dict[str, object] = {}


def get_predictor(key: str):
    """Cached predictor for a NEW domain (Student uses the existing page/pipeline)."""
    d = BY_KEY[key]
    if d.predictor_cls is None:
        raise KeyError("Student Productivity uses the existing prediction page and trained pipeline.")
    if key not in _cache:
        _cache[key] = d.predictor_cls()
    return _cache[key]
