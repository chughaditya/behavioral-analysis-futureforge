"""Habit & Routine Forecasting — routine consistency and behavioural patterns."""
from .base import DomainPredictor, FeatureSpec as F


class HabitPredictor(DomainPredictor):
    key, title, score_name = "habit_routine", "Habit & Routine Forecasting", "Routine Score"
    features = [
        F("sleep_consistency", "Sleep Consistency", 0, 100, 70, 1, "higher", weight=2.0, unit="%",
          low_tip="Fix a wake-up time first and hold it 7 days a week; bedtime follows."),
        F("exercise_frequency", "Exercise Frequency (days/week)", 0, 7, 3, 1, "optimum", (3, 5), 1.5,
          low_tip="Schedule 2–3 fixed exercise slots per week and treat them as appointments.",
          high_tip="Daily hard training needs planned rest days."),
        F("study_work_hours", "Study/Work Hours", 0, 14, 7, 0.5, "optimum", (5, 9), 1.0, " h",
          "Anchor a daily block at the same time each day.",
          "Very long days undermine routine sustainability — cap the day."),
        F("screen_time", "Screen Time", 0, 14, 5, 0.5, "lower", weight=1.0, unit=" h",
          high_tip="Add screen-free anchors: first hour of the day and the hour before bed."),
        F("break_frequency", "Break Frequency (per day)", 0, 15, 5, 1, "optimum", (4, 8), 1.0,
          low_tip="Schedule short recurring breaks so they become automatic.",
          high_tip="Frequent breaks may be fragmenting your blocks."),
        F("mood", "Mood (1-10)", 1, 10, 7, 1, "higher", weight=0.5,
          low_tip="Keep the routine minimal on low days — protect just the two habits that matter most."),
        F("routine_consistency", "Daily Routine Consistency", 0, 100, 65, 1, "higher", weight=2.0, unit="%",
          low_tip="Pick 3 anchor habits (wake, first work block, wind-down) and repeat them daily."),
    ]
    patterns = [
        ("Erratic schedule", lambda v, s: v["sleep_consistency"] < 40 and v["routine_consistency"] < 40),
        ("Weekday-only routine", lambda v, s: v["routine_consistency"] >= 70 and v["sleep_consistency"] < 55),
        ("Locked-in routine", lambda v, s: v["sleep_consistency"] >= 80 and v["routine_consistency"] >= 80),
        ("Screen-anchored days", lambda v, s: v["screen_time"] >= 9 and v["routine_consistency"] < 60),
    ]
    default_pattern = "Building consistency"

    def extras(self, v, s, score):
        hc = round((v["sleep_consistency"] + v["routine_consistency"]) / 2, 1)
        return {"Habit Consistency": hc,
                "Routine Score": self.subscore(s, ["sleep_consistency", "routine_consistency", "exercise_frequency", "break_frequency"])}
