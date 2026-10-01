"""
FutureForge — AI Coach engine
------------------------------
Two modes:

1. GENERATIVE (preferred) — if the user supplies an Anthropic API key
   (Settings page, kept only in st.session_state for the session, never
   written to disk), every message is sent to the real Claude API together
   with a system prompt grounded in the user's *own* saved history, so
   replies are genuinely conversational and context-aware (follow-ups,
   clarifying questions, tone changes, etc.) — not template lookups.

2. LOCAL SMART-ASSIST (fallback, no key needed) — an intent + slot
   engine that still answers in natural, varied sentences built from the
   user's real numbers, and is honest in the UI about running in local mode.
"""

from __future__ import annotations

import random
import re
from typing import Optional

import pandas as pd

COACH_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT_TEMPLATE = """You are the FutureForge AI Coach, a warm, encouraging but honest \
personal-performance coach embedded in a productivity dashboard. You help the user understand \
their focus, stress, sleep, mood and productivity patterns, and suggest small, concrete, \
evidence-based next steps. Keep replies conversational and concise (usually 2-5 sentences unless \
the user asks for a detailed breakdown). Reference the user's real data below when relevant instead \
of generic advice. If the data doesn't cover something, say so plainly rather than inventing numbers. \
Never give medical diagnoses; for anything clinical, gently suggest a professional.

USER CONTEXT
------------
Name: {name}
{context}
"""


def build_user_context(reports_df: pd.DataFrame, tests_df: pd.DataFrame) -> str:
    """Turns the local SQLite history into a compact natural-language brief
    that grounds every reply (generative or local) in the user's real data."""
    if reports_df is None or reports_df.empty:
        base = "No daily reports saved yet."
    else:
        d = reports_df.sort_values("date")
        last = d.iloc[-1]
        n = len(d)
        avg_focus = d["focus_score"].mean()
        avg_stress = d["stress_score"].mean()
        avg_sleep = d["sleep_hours"].mean()
        avg_prod = d["productivity_score"].mean()
        best_row = d.loc[d["focus_score"].idxmax()]
        worst_row = d.loc[d["focus_score"].idxmin()]
        trend = "improving" if len(d) >= 4 and d["focus_score"].tail(3).mean() > d["focus_score"].head(3).mean() else \
            "declining" if len(d) >= 4 and d["focus_score"].tail(3).mean() < d["focus_score"].head(3).mean() else "stable"

        corr_txt = ""
        if n >= 5:
            corr = d[["sleep_hours", "focus_score"]].corr().iloc[0, 1]
            if pd.notna(corr):
                strength = "strong" if abs(corr) > 0.5 else "moderate" if abs(corr) > 0.25 else "weak"
                direction = "positive" if corr > 0 else "negative"
                corr_txt = f"\n- Sleep↔Focus correlation: {strength} {direction} (r={corr:.2f})"

        base = (
            f"{n} saved daily reports.\n"
            f"- Most recent ({last['date'].strftime('%b %d')}): focus {last['focus_score']:.0f}, "
            f"stress {last['stress_score']:.0f}, mood {last['mood_score']:.1f}/10, sleep {last['sleep_display']}, "
            f"productivity {last['productivity_score']:.0f}%\n"
            f"- Averages: focus {avg_focus:.0f}, stress {avg_stress:.0f}, sleep {avg_sleep:.1f}h, productivity {avg_prod:.0f}%\n"
            f"- Best focus day: {best_row['date'].strftime('%b %d')} ({best_row['focus_score']:.0f})\n"
            f"- Lowest focus day: {worst_row['date'].strftime('%b %d')} ({worst_row['focus_score']:.0f})\n"
            f"- Recent trend: {trend}{corr_txt}"
        )

    if tests_df is not None and not tests_df.empty:
        t_summary = []
        for ttype in tests_df["test_type"].unique():
            sub = tests_df[tests_df["test_type"] == ttype]
            t_summary.append(f"{ttype}: {len(sub)} attempts, best score {sub['score'].max():.0f}")
        base += "\n\nFocus Lab tests:\n- " + "\n- ".join(t_summary)

    return base


def get_coach_reply(
    messages: list[dict],
    reports_df: pd.DataFrame,
    tests_df: pd.DataFrame,
    user_name: str = "",
    api_key: Optional[str] = None,
) -> tuple[str, str]:
    """Returns (reply_text, mode) where mode is 'generative' or 'local'."""
    context = build_user_context(reports_df, tests_df)

    if api_key:
        try:
            return _generative_reply(messages, context, user_name, api_key), "generative"
        except Exception as exc:  # noqa: BLE001 — surface a friendly fallback, not a stack trace
            fallback = _local_reply(messages, reports_df, tests_df, context)
            return (
                f"⚠️ Couldn't reach the Claude API ({exc.__class__.__name__}), "
                f"answering with local smart-assist instead:\n\n{fallback}"
            ), "local"

    return _local_reply(messages, reports_df, tests_df, context), "local"


def _generative_reply(messages: list[dict], context: str, user_name: str, api_key: str) -> str:
    import anthropic  # imported lazily so the package is only required in generative mode

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(name=user_name or "there", context=context)

    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")]

    resp = client.messages.create(
        model=COACH_MODEL,
        max_tokens=600,
        system=system_prompt,
        messages=api_messages,
    )
    text_parts = [block.text for block in resp.content if getattr(block, "type", "") == "text"]
    return "".join(text_parts).strip() or "I didn't get a text response back — try rephrasing?"


# ---------------------------------------------------------------------------
# Local smart-assist fallback (no API key) — intent detection over real data,
# with varied natural-language phrasing so it doesn't feel like a fixed lookup.
# ---------------------------------------------------------------------------
_OPENERS = [
    "Looking at your data — ", "Here's what your history shows: ", "Based on what you've logged, ",
    "From your saved reports: ", "",
]

_ENCOURAGERS = [
    "Nice work staying consistent.", "Keep that pattern going.", "Small, steady changes compound fast.",
    "That's a solid trend to build on.",
]


def _local_reply(messages: list[dict], reports_df: pd.DataFrame, tests_df: pd.DataFrame, context: str) -> str:
    last_user = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user = m["content"]
            break
    q = last_user.lower()

    if reports_df is None or reports_df.empty:
        return (
            "You haven't saved any daily reports yet, so I don't have anything to coach you on. "
            "Head to **Prediction**, run today's numbers, and save it — then ask me again."
        )

    df = reports_df.sort_values("date")
    opener = random.choice(_OPENERS)

    def fmt_day(row):
        return row["date"].strftime("%B %d")

    if re.search(r"\bbest\b", q):
        row = df.loc[df["focus_score"].idxmax()]
        return f"{opener}your best focus day was **{fmt_day(row)}** at {row['focus_score']:.0f}/100, with {row['sleep_display']} sleep and a '{row['mood']}' mood. {random.choice(_ENCOURAGERS)}"

    if re.search(r"\bworst\b|\blow(est)?\b|\bstruggl", q):
        row = df.loc[df["focus_score"].idxmin()]
        return f"{opener}your lowest focus day was **{fmt_day(row)}** at {row['focus_score']:.0f}/100. Sleep that day was {row['sleep_display']} and stress was {row['stress_score']:.0f}/100 — worth watching if that pattern repeats."

    if re.search(r"\bstress\b", q):
        avg = df["stress_score"].mean()
        recent = df["stress_score"].tail(3).mean()
        direction = "up" if recent > avg + 3 else "down" if recent < avg - 3 else "steady"
        return f"{opener}average stress is **{avg:.0f}/100**, and your last few days are trending **{direction}** versus that average."

    if re.search(r"\bsleep\b", q):
        avg = df["sleep_hours"].mean()
        return f"{opener}you're averaging **{avg:.1f} hours** of sleep. " + (
            "That's a healthy range — protect it." if avg >= 7 else "That's a bit under the 7-9h most adults need, and it likely shows up in your focus scores."
        )

    if re.search(r"\bimprove|\bbetter|\bhelp\b|\btip", q) and "sleep" not in q:
        if len(df) >= 5:
            corr = df[["sleep_hours", "focus_score"]].corr().iloc[0, 1]
            hint = ""
            if pd.notna(corr) and corr > 0.25:
                hint = " Your sleep and focus are positively correlated in your own data, so that's the highest-leverage lever right now."
            return f"{opener}your top 25% focus days tend to have more sleep and lower stress than average.{hint} Try protecting one extra hour of sleep tonight and see how tomorrow's score compares."
        return "I need a few more saved days before I can spot a reliable pattern — keep logging and ask me again in a few days."

    if re.search(r"\btrend|\bhow am i doing|\bprogress", q):
        if len(df) >= 4:
            trend_dir = "improving 📈" if df["focus_score"].tail(3).mean() > df["focus_score"].head(3).mean() else "dipping slightly 📉"
            return f"{opener}your focus trend looks like it's **{trend_dir}** over your saved history. Average sits at {df['focus_score'].mean():.0f}/100."
        return "You've got a couple of data points so far — a few more days will make the trend clearer."

    if re.search(r"\btest|\bfocus lab|\battention|\bmemory|\breaction|\bstroop", q):
        if tests_df is not None and not tests_df.empty:
            best = tests_df.loc[tests_df["score"].idxmax()]
            return f"{opener}your strongest Focus Lab result so far is **{best['test_type']}** with a score of {best['score']:.0f}. Try the others in the Focus Lab tab if you haven't yet."
        return "You haven't run any Focus Lab tests yet — try Reaction Time, Stroop, Attention Grid or Memory Sequence to get a cognitive baseline."

    return (
        f"{opener}I can talk through your best/worst days, stress or sleep trends, what tends to improve your "
        f"focus, or your Focus Lab test results. Try asking something like *\"what improves my focus?\"* or "
        f"*\"how's my sleep trending?\"* — or add a Claude API key in Settings for fully open-ended conversation."
    )
