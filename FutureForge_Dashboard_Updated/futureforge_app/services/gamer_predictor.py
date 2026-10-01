"""Gamer Performance — behavioural performance insights only, no medical claims."""
from .base import DomainPredictor, FeatureSpec as F


class GamerPredictor(DomainPredictor):
    key, title, score_name = "gamer", "Gamer Performance", "Performance Forecast"
    features = [
        F("gaming_hours", "Gaming Hours (per day)", 0, 16, 3, 0.5, "optimum", (1, 4), 1.0, " h",
          "Very little practice — short regular sessions help skill retention.",
          "Very long gaming days often reduce performance; cap total hours."),
        F("session_minutes", "Session Duration", 10, 480, 90, 10, "optimum", (45, 120), 1.5, " min",
          "Very short sessions may not reach a full warm-up; aim for 45+ minutes.",
          "Long unbroken sessions hurt reaction and decision quality; split them."),
        F("sleep_hours", "Sleep Hours", 0, 12, 7, 0.5, "optimum", (7, 9), 1.5, " h",
          "Sleep strongly affects reaction time and focus — protect 7–9 hours.",
          "Regularly sleeping above 9 h — keep a consistent wake time."),
        F("break_frequency", "Breaks (per session)", 0, 8, 1, 1, "optimum", (1, 3), 1.0,
          low_tip="Take a 5-minute break at least once per session to reset focus.",
          high_tip="Frequent interruptions can break flow — consolidate into fewer, slightly longer breaks."),
        F("previous_performance", "Previous Performance", 0, 100, 60, 1, "higher", weight=1.5, unit="%",
          low_tip="Review recent losses/replays for one or two repeating mistakes to fix."),
        F("reaction_score", "Reaction / Performance Score", 0, 100, 65, 1, "higher", weight=1.5, unit="%",
          low_tip="Do a short warm-up (aim trainer / reaction drill) before ranked play."),
        F("focus_level", "Focus Level (1-10)", 1, 10, 7, 1, "higher", weight=1.5,
          low_tip="Remove distractions, hydrate and take a short break before your next session."),
    ]
    patterns = [
        ("Marathon grinder", lambda v, s: v["session_minutes"] >= 180 and v["break_frequency"] <= 1),
        ("Sleep-deprived play", lambda v, s: v["sleep_hours"] < 6 and v["gaming_hours"] >= 4),
        ("Peak-form", lambda v, s: v["focus_level"] >= 8 and v["reaction_score"] >= 75 and s["sleep_hours"] >= 75),
        ("Casual / light", lambda v, s: v["gaming_hours"] <= 1),
    ]
    default_pattern = "Consistent competitor"

    def extras(self, v, s, score):
        long_no_break = v["session_minutes"] >= 150 and v["break_frequency"] < 2
        analysis = ("Long sessions with few breaks — likely fatigue late in the session." if long_no_break else
                    "Session length and breaks look sustainable." if s["session_minutes"] >= 70 and s["break_frequency"] >= 70
                    else "Session structure could be tightened (length or break timing).")
        return {"Focus Score": self.subscore(s, ["focus_level", "reaction_score", "sleep_hours"]),
                "Session Analysis": analysis}
