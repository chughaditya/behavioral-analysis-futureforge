"""
FutureForge — Analytics Engine
Statistical analysis over real saved history (pandas). Clearly rule/statistics based,
not deep learning — per spec: "do not pretend it is a deep AI model."
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd


def pct_delta(current: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return round(((current - baseline) / baseline) * 100, 1)


def filter_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if df.empty:
        return df
    if period == "7D":
        cutoff = datetime.now() - timedelta(days=7)
    elif period == "30D":
        cutoff = datetime.now() - timedelta(days=30)
    elif period == "90D":
        cutoff = datetime.now() - timedelta(days=90)
    elif period == "1Y":
        cutoff = datetime.now() - timedelta(days=365)
    else:
        return df
    return df[df["date"] >= cutoff]


def history_comparison(df: pd.DataFrame, today_metrics: dict[str, Any], window_days: int = 30) -> dict[str, Any] | None:
    """Compare today's metrics against the trailing N-day average of saved history."""
    if df.empty:
        return None
    cutoff = datetime.now() - timedelta(days=window_days)
    recent = df[df["date"] >= cutoff]
    if recent.empty:
        return None

    return {
        "n_days": len(recent),
        "focus": {
            "today": today_metrics["focus_score"],
            "avg": round(recent["focus_score"].mean(), 1),
            "delta_pct": pct_delta(today_metrics["focus_score"], recent["focus_score"].mean()),
        },
        "stress": {
            "today": today_metrics["stress_score"],
            "avg": round(recent["stress_score"].mean(), 1),
            "delta_pct": pct_delta(today_metrics["stress_score"], recent["stress_score"].mean()),
        },
        "sleep": {
            "today": today_metrics["sleep_hours"],
            "avg": round(recent["sleep_hours"].mean(), 2),
            "delta_min": round((today_metrics["sleep_hours"] - recent["sleep_hours"].mean()) * 60),
        },
        "productivity": {
            "today": today_metrics["productivity_score"],
            "avg": round(recent["productivity_score"].mean(), 1),
            "delta_pct": pct_delta(today_metrics["productivity_score"], recent["productivity_score"].mean()),
        },
    }


MIN_DAYS_FOR_INSIGHTS = 5


def generate_insights(df: pd.DataFrame) -> list[dict[str, str]]:
    """Pattern insights computed from real saved data via correlation/grouping.
    Returns 'not enough data' style messages when history is too small."""
    insights: list[dict[str, str]] = []

    if len(df) < MIN_DAYS_FOR_INSIGHTS:
        insights.append(
            {
                "type": "Not Enough Data",
                "message": f"Not enough data yet — save at least {MIN_DAYS_FOR_INSIGHTS} daily reports "
                f"to unlock behavioral insights. You have {len(df)} so far.",
            }
        )
        return insights

    # Focus vs sleep
    high_sleep = df[df["sleep_hours"] > 7]
    low_sleep = df[df["sleep_hours"] <= 7]
    if len(high_sleep) >= 2 and len(low_sleep) >= 2:
        diff = high_sleep["focus_score"].mean() - low_sleep["focus_score"].mean()
        if abs(diff) > 3:
            direction = "best" if diff > 0 else "worse"
            insights.append(
                {
                    "type": "Focus Pattern",
                    "message": f"You focus {direction} when your sleep exceeds 7 hours "
                    f"(avg {high_sleep['focus_score'].mean():.0f} vs {low_sleep['focus_score'].mean():.0f}).",
                }
            )

    # Stress vs sleep
    low_sleep_stress = df[df["sleep_hours"] < 6]
    if len(low_sleep_stress) >= 2:
        rest = df[df["sleep_hours"] >= 6]
        if not rest.empty and low_sleep_stress["stress_score"].mean() > rest["stress_score"].mean() + 5:
            insights.append(
                {
                    "type": "Stress Pattern",
                    "message": "Your stress tends to increase on days with less than 6 hours of sleep "
                    f"(avg stress {low_sleep_stress['stress_score'].mean():.0f} vs {rest['stress_score'].mean():.0f}).",
                }
            )

    # Mood trend over last 7 entries
    last7 = df.tail(7)
    if len(last7) >= 4:
        first_half = last7.iloc[: len(last7) // 2]["mood_score"].mean()
        second_half = last7.iloc[len(last7) // 2 :]["mood_score"].mean()
        if second_half - first_half > 0.4:
            insights.append(
                {"type": "Mood Pattern", "message": "Your mood has improved consistently over the past 7 tracked days."}
            )
        elif first_half - second_half > 0.4:
            insights.append(
                {"type": "Mood Pattern", "message": "Your mood has dipped over the past 7 tracked days — worth watching."}
            )

    # Productivity vs stress
    low_stress = df[df["stress_score"] < 40]
    high_stress = df[df["stress_score"] >= 40]
    if len(low_stress) >= 2 and len(high_stress) >= 2:
        if low_stress["productivity_score"].mean() > high_stress["productivity_score"].mean() + 3:
            insights.append(
                {
                    "type": "Productivity Pattern",
                    "message": "Your productivity is strongest during low-stress days "
                    f"(avg {low_stress['productivity_score'].mean():.0f} vs {high_stress['productivity_score'].mean():.0f}).",
                }
            )

    if not insights:
        insights.append(
            {"type": "Steady State", "message": "Your metrics are fairly stable — no strong patterns detected yet."}
        )

    return insights


def best_conditions(df: pd.DataFrame) -> dict[str, Any] | None:
    if len(df) < MIN_DAYS_FOR_INSIGHTS:
        return None
    top = df.nlargest(max(1, len(df) // 3), "focus_score")
    return {
        "sleep_min": round(top["sleep_hours"].min(), 1),
        "stress_max": round(top["stress_score"].max(), 1),
        "mood_min": round(top["mood_score"].min(), 1),
    }


def weekly_report(df: pd.DataFrame) -> dict[str, Any] | None:
    if df.empty:
        return None
    cutoff = datetime.now() - timedelta(days=7)
    week = df[df["date"] >= cutoff]
    if week.empty:
        return None
    best_day_row = week.loc[week["focus_score"].idxmax()]
    worst_day_row = week.loc[week["focus_score"].idxmin()]
    return {
        "range": f"{week['date'].min().strftime('%b %d')} – {week['date'].max().strftime('%b %d')}",
        "avg_focus": round(week["focus_score"].mean(), 1),
        "avg_stress": round(week["stress_score"].mean(), 1),
        "avg_mood": round(week["mood_score"].mean(), 1),
        "avg_sleep_hours": round(week["sleep_hours"].mean(), 2),
        "best_day": best_day_row["date"].strftime("%A"),
        "worst_day": worst_day_row["date"].strftime("%A"),
        "n_days": len(week),
    }


def monthly_report(df: pd.DataFrame) -> dict[str, Any] | None:
    if df.empty:
        return None
    cutoff = datetime.now() - timedelta(days=30)
    month = df[df["date"] >= cutoff]
    if month.empty:
        return None
    prev_cutoff = cutoff - timedelta(days=30)
    prev_month = df[(df["date"] >= prev_cutoff) & (df["date"] < cutoff)]
    improvement = None
    if not prev_month.empty:
        improvement = pct_delta(month["focus_score"].mean(), prev_month["focus_score"].mean())

    best_day_row = month.loc[month["focus_score"].idxmax()]
    worst_day_row = month.loc[month["focus_score"].idxmin()]
    return {
        "avg_focus": round(month["focus_score"].mean(), 1),
        "avg_stress": round(month["stress_score"].mean(), 1),
        "avg_mood": round(month["mood_score"].mean(), 1),
        "avg_sleep_hours": round(month["sleep_hours"].mean(), 2),
        "avg_productivity": round(month["productivity_score"].mean(), 1),
        "best_day": best_day_row["date"].strftime("%b %d"),
        "worst_day": worst_day_row["date"].strftime("%b %d"),
        "improvement_pct": improvement,
        "n_days": len(month),
    }


def compute_streaks(df: pd.DataFrame) -> dict[str, int]:
    """Report-saving streak + healthy-sleep streak, based on consecutive calendar days."""
    if df.empty:
        return {"report_streak": 0, "best_report_streak": 0, "sleep_streak": 0, "focus_streak": 0}

    dates = sorted(df["date"].dt.date.unique())
    today = datetime.now().date()

    def current_and_best_streak(day_list, condition_dates=None):
        day_set = set(condition_dates) if condition_dates is not None else set(day_list)
        best = 0
        run = 0
        prev = None
        for d in sorted(day_set):
            if prev is not None and (d - prev).days == 1:
                run += 1
            else:
                run = 1
            best = max(best, run)
            prev = d
        # current streak: consecutive days ending today or yesterday
        current = 0
        cursor = today
        while cursor in day_set:
            current += 1
            cursor -= timedelta(days=1)
        if current == 0 and (today - timedelta(days=1)) in day_set:
            cursor = today - timedelta(days=1)
            while cursor in day_set:
                current += 1
                cursor -= timedelta(days=1)
        return current, best

    report_current, report_best = current_and_best_streak(dates)

    sleep_days = df[df["sleep_hours"] >= 7]["date"].dt.date.tolist()
    sleep_current, sleep_best = current_and_best_streak(dates, sleep_days)

    focus_days = df[df["focus_score"] >= 75]["date"].dt.date.tolist()
    focus_current, focus_best = current_and_best_streak(dates, focus_days)

    return {
        "report_streak": report_current,
        "best_report_streak": report_best,
        "sleep_streak": sleep_current,
        "best_sleep_streak": sleep_best,
        "focus_streak": focus_current,
        "best_focus_streak": focus_best,
    }


def compute_achievements(df: pd.DataFrame, tests_df: pd.DataFrame, streaks: dict[str, int]) -> list[dict[str, Any]]:
    achievements = []

    def item(icon, title, desc, unlocked):
        return {"icon": icon, "title": title, "desc": desc, "unlocked": unlocked}

    achievements.append(item("🏆", "First Report", "Save your first daily report.", len(df) >= 1))
    achievements.append(item("🔥", "7 Day Streak", "Save reports 7 days in a row.", streaks.get("best_report_streak", 0) >= 7))
    achievements.append(
        item("🧠", "Focus Master", "Reach a focus score of 80+.", not df.empty and df["focus_score"].max() >= 80)
    )
    achievements.append(
        item("😌", "Stress Controller", "Keep stress under 35 for a day.", not df.empty and df["stress_score"].min() <= 35)
    )
    achievements.append(
        item("🌙", "Sleep Consistency", "Hit a 5-day healthy sleep streak (7h+).", streaks.get("best_sleep_streak", 0) >= 5)
    )
    if len(df) >= 2:
        improvement = pct_delta(df["focus_score"].iloc[-1], df["focus_score"].iloc[0])
        ten_pct = improvement >= 5
    else:
        ten_pct = False
    achievements.append(item("📈", "10% Improvement", "Improve focus by 5% since your first report.", ten_pct))
    achievements.append(item("🎯", "Test Taker", "Complete your first Focus Lab test.", len(tests_df) >= 1))

    return achievements


def smart_alerts(df: pd.DataFrame) -> list[dict[str, str]]:
    alerts = []
    if len(df) < 4:
        return alerts

    this_week = filter_period(df, "7D")
    prev_cutoff_start = datetime.now() - timedelta(days=14)
    prev_cutoff_end = datetime.now() - timedelta(days=7)
    prev_week = df[(df["date"] >= prev_cutoff_start) & (df["date"] < prev_cutoff_end)]

    if not this_week.empty and not prev_week.empty:
        stress_change = pct_delta(this_week["stress_score"].mean(), prev_week["stress_score"].mean())
        if stress_change > 15:
            alerts.append({"icon": "⚠️", "message": f"Stress has increased {stress_change:.0f}% this week."})
        elif stress_change < -15:
            alerts.append({"icon": "✅", "message": f"Stress has dropped {abs(stress_change):.0f}% this week — great work."})

    high_sleep = df[df["sleep_hours"] > 7]
    low_sleep = df[df["sleep_hours"] <= 7]
    if len(high_sleep) >= 2 and len(low_sleep) >= 2:
        diff = high_sleep["focus_score"].mean() - low_sleep["focus_score"].mean()
        if diff > 8:
            alerts.append({"icon": "💡", "message": "Your focus is significantly better after 7+ hours of sleep."})

    last3 = df.tail(3)
    if len(last3) == 3 and (last3["sleep_hours"] < 6.5).all():
        alerts.append({"icon": "🌙", "message": "Your sleep duration has stayed low for 3 consecutive entries."})

    return alerts
