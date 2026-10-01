"""
FutureForge — Focus Mode (UI)

Rendered as an extra tab inside the existing Focus Lab page. All data lives in the
existing SQLite database through core.db (focus_sessions / focus_settings tables);
Streamlit session_state only keeps small UI flags (distraction-free on/off, chosen
duration, dismissed banner) — never the session itself, so a refresh or rerun always
recovers the real session from the database.

Focus analytics are deliberately separate from the ML pipeline: the models' four
input features (study_hours, sleep_hours, screen_time, mood_score) are untouched.
"""

import html
import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core import db

log = logging.getLogger(__name__)

# FutureForge is a single-user local app (no login), so Focus Mode uses one profile.
PROFILE_TYPE = "local"
PROFILE_KEY = "default"

DF_KEY = "focus_distraction_free"
DISMISSED_KEY = "fm_dismissed_completed_id"
ERROR_KEY = "fm_db_error"
COMPLETED_WINDOW_MIN = 30  # how long the "session completed" banner is offered after finishing

TIPS = [
    "Keep your phone away during the session.",
    "Work on one task at a time.",
    "Take a short break after completing a session.",
    "Set a clear goal before starting.",
    "Close tabs you don't need before you begin.",
    "Stand up and stretch during your break — don't scroll.",
    "Start with the hardest task while your energy is highest.",
    "Write down distracting thoughts and come back to them after the session.",
]

TARGET_OPTIONS_MIN = [60, 120, 180, 240, 300, 360, 480]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _fmt_minutes(minutes) -> str:
    m = int(round(float(minutes or 0)))
    h, mm = divmod(m, 60)
    if h and mm:
        return f"{h}h {mm}m"
    if h:
        return f"{h}h"
    return f"{mm}m"


def _fmt_clock(seconds) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def _safe(fn, default=None):
    """Run a DB call; on failure log it, flag it, return `default` (no raw tracebacks in the UI)."""
    try:
        return fn()
    except Exception:  # noqa: BLE001 - UI must degrade gracefully
        log.exception("Focus Mode database call failed")
        st.session_state[ERROR_KEY] = True
        return default


def _selected_minutes() -> int:
    choice = st.session_state.get("fm_dur_choice", "25 min")
    if choice == "25 min":
        return 25
    if choice == "50 min":
        return 50
    try:
        return int(st.session_state.get("fm_dur_custom", 45))
    except (TypeError, ValueError):
        return 0


def break_recommendation(planned_minutes: float, completed_today: int) -> tuple[int, str]:
    """Deterministic break suggestion: long break every 4th session, else scaled to session length."""
    if completed_today > 0 and completed_today % 4 == 0:
        return 20, "You've finished 4 sessions today — take a proper 20-minute break: walk, eat, hydrate."
    if planned_minutes >= 45:
        return 10, "Take a 10-minute break — stretch, drink water and rest your eyes."
    return 5, "Take a 5-minute break — stand up, breathe and look away from the screen."


def _tip_for_today(completed_today: int) -> str:
    return TIPS[(datetime.now().date().toordinal() + completed_today) % len(TIPS)]


def _inject_focus_css() -> None:
    st.markdown(
        """
        <style>
        .fm-goal { font-size:0.78rem; color:var(--text-sub); text-transform:uppercase; letter-spacing:1px; }
        .fm-goal-text { font-family:'Space Grotesk',sans-serif; font-size:1.25rem; font-weight:600;
                        color:var(--text-main); margin:2px 0 6px 0; word-break:break-word; }
        .fm-timer-wrap { display:flex; flex-direction:column; align-items:center; margin:8px 0 6px 0; }
        .fm-ring { width:230px; height:230px; border-radius:50%; display:flex; align-items:center; justify-content:center;
                   box-shadow: 0 0 40px rgba(139,92,246,0.18); }
        .fm-ring-inner { width:198px; height:198px; border-radius:50%; background:var(--card-bg);
                         display:flex; flex-direction:column; align-items:center; justify-content:center; }
        .fm-time { font-family:'Space Grotesk',sans-serif; font-size:3.4rem; font-weight:700; color:var(--text-main);
                   letter-spacing:2px; line-height:1; font-variant-numeric: tabular-nums; }
        .fm-sub { font-size:0.8rem; color:var(--text-sub); margin-top:8px; }
        .fm-badge { display:inline-block; padding:4px 14px; border-radius:999px; font-size:0.75rem; font-weight:700;
                    text-transform:uppercase; letter-spacing:0.5px; }
        .fm-ready { background:rgba(152,152,159,0.15); color:var(--text-sub); border:1px solid var(--card-border); }
        .fm-focusing { background:rgba(52,211,153,0.18); color:#34d399; border:1px solid rgba(52,211,153,0.4); }
        .fm-paused { background:rgba(251,191,36,0.18); color:#fbbf24; border:1px solid rgba(251,191,36,0.4); }
        .fm-completed { background:rgba(139,92,246,0.18); color:#a78bfa; border:1px solid rgba(139,92,246,0.45); }
        .fm-score { font-family:'Space Grotesk',sans-serif; font-size:2.6rem; font-weight:700; color:var(--text-main); }
        .fm-break { background:linear-gradient(90deg, rgba(139,92,246,0.16), rgba(99,102,241,0.10));
                    border:1px solid rgba(139,92,246,0.4); border-radius:16px; padding:14px 18px; margin-bottom:14px; }
        .fm-tip { border-left:3px solid #8b5cf6; background:var(--card-bg); border-radius:12px; padding:12px 16px;
                  color:var(--text-main); font-size:0.95rem; }
        @media (max-width: 640px) {
            .fm-ring { width:190px; height:190px; } .fm-ring-inner { width:164px; height:164px; }
            .fm-time { font-size:2.6rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Distraction-free mode (used by pages/4_Focus_Lab.py before the nav renders)
# ---------------------------------------------------------------------------
def is_distraction_free() -> bool:
    return bool(st.session_state.get(DF_KEY, False))


def render_distraction_free() -> None:
    """Minimal full-focus screen: timer, goal, pause/resume, end, progress, exit. Nothing else."""
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"], header[data-testid="stHeader"] { display:none !important; }
        .block-container { max-width: 760px !important; padding-top: 3rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _inject_focus_css()
    if st.button("✖ Exit Focus Mode", key="fm_exit_df"):
        st.session_state[DF_KEY] = False
        st.rerun()
    st.session_state[ERROR_KEY] = False
    _safe(db.init_db)
    _render_focus_mode_contents(PROFILE_TYPE, PROFILE_KEY, distraction_free=True)


# ---------------------------------------------------------------------------
# Public entry point (Focus Lab tab)
# ---------------------------------------------------------------------------
def render_focus_mode() -> None:
    _inject_focus_css()
    st.session_state[ERROR_KEY] = False
    _safe(db.init_db)  # CREATE TABLE IF NOT EXISTS — safe if a table was never created
    _render_focus_mode_contents(PROFILE_TYPE, PROFILE_KEY, distraction_free=False)


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
def _render_focus_mode_contents(profile_type: str, profile_key: str, distraction_free: bool = False) -> None:
    session = _safe(lambda: db.get_open_focus_session(profile_type, profile_key))
    last = _safe(lambda: db.get_last_finished_focus_session(profile_type, profile_key))
    day = _safe(lambda: db.get_focus_day_summary(profile_type, profile_key), None)

    completed_banner = _completed_recently(session, last)

    if distraction_free:
        _render_focus_card(profile_type, profile_key, session, last, completed_banner, day, distraction_free=True)
        _render_target_block(profile_type, profile_key, day, editable=False)
        st.markdown(f'<div class="fm-tip">💡 {html.escape(_tip_for_today(day["sessions_completed"] if day else 0))}</div>',
                    unsafe_allow_html=True)
        _render_db_warning()
        return

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        _render_focus_card(profile_type, profile_key, session, last, completed_banner, day, distraction_free=False)
    with right:
        _render_target_block(profile_type, profile_key, day, editable=True)
        _render_streak_and_score(profile_type, profile_key)

    completed_today = day["sessions_completed"] if day else 0
    st.markdown(f'<div class="fm-tip">💡 <b>Quick tip</b> — {html.escape(_tip_for_today(completed_today))}</div>',
                unsafe_allow_html=True)
    st.markdown("")
    _render_recommendations(profile_type, profile_key, day)
    _render_history(profile_type, profile_key)
    _render_db_warning()


def _render_db_warning() -> None:
    if st.session_state.get(ERROR_KEY):
        st.warning("Focus Mode couldn't reach its database just now. Your saved data is safe — "
                   "please refresh the page in a moment.")


def _completed_recently(session, last) -> dict | None:
    """Latest session if it was COMPLETED in the last few minutes, nothing is open, and the banner wasn't dismissed."""
    if session is not None or not last or last.get("status") != "completed":
        return None
    if st.session_state.get(DISMISSED_KEY) == last["id"]:
        return None
    try:
        ended = datetime.fromisoformat(last["ended_at"])
    except (TypeError, ValueError):
        return None
    if datetime.now() - ended > timedelta(minutes=COMPLETED_WINDOW_MIN):
        return None
    return last


# ---------------------------------------------------------------------------
# Session card: goal, duration, timer, controls
# ---------------------------------------------------------------------------
def _render_focus_card(profile_type, profile_key, session, last, completed_banner, day, distraction_free: bool) -> None:
    if session is not None:
        status_key = "focusing" if session["status"] == "running" else "paused"
        status_label = "Focusing" if status_key == "focusing" else "Paused"
    elif completed_banner is not None:
        status_key, status_label = "completed", "Completed"
    else:
        status_key, status_label = "ready", "Ready"

    with st.container(border=not distraction_free):
        head_l, head_r = st.columns([3, 1])
        head_l.markdown("### 🎯 Focus Mode")
        head_r.markdown(f'<div style="text-align:right"><span class="fm-badge fm-{status_key}">{status_label}</span></div>',
                        unsafe_allow_html=True)

        # ---- Goal + duration ------------------------------------------------
        if session is not None:
            goal = session.get("label") or "No goal set"
            st.markdown(f'<div class="fm-goal">Current goal</div><div class="fm-goal-text">{html.escape(goal)}</div>',
                        unsafe_allow_html=True)
        else:
            if completed_banner is not None:
                _render_break_banner(completed_banner, day)
            st.text_input("Study goal", key="fm_goal", max_chars=120,
                          placeholder="e.g. Complete DBMS Unit 2 · Revise Machine Learning · Complete Java Assignment")
            st.radio("Duration", ["25 min", "50 min", "Custom"], horizontal=True, key="fm_dur_choice")
            if st.session_state.get("fm_dur_choice") == "Custom":
                st.number_input("Custom duration (minutes)", min_value=1, max_value=480, value=45, step=5,
                                key="fm_dur_custom")

        # ---- Timer (live) ---------------------------------------------------
        _render_focus_timer(profile_type, profile_key, session)

        # ---- Controls -------------------------------------------------------
        _render_controls(profile_type, profile_key, session, completed_banner, distraction_free)


def _render_break_banner(last: dict, day) -> None:
    completed_today = day["sessions_completed"] if day else 1
    minutes, message = break_recommendation(last["planned_seconds"] / 60.0, completed_today)
    goal = last.get("label")
    goal_txt = f' on “{html.escape(goal)}”' if goal else ""
    st.markdown(
        f'<div class="fm-break">🎉 <b>Session completed{goal_txt}!</b> '
        f'You focused for {_fmt_minutes(last["elapsed_seconds"] / 60.0)}. '
        f'Sessions completed today: <b>{completed_today}</b><br>☕ {html.escape(message)}</div>',
        unsafe_allow_html=True,
    )
    if st.button("Dismiss break reminder", key="fm_dismiss_break"):
        st.session_state[DISMISSED_KEY] = last["id"]
        st.rerun()


def _render_focus_timer(profile_type: str, profile_key: str, session) -> None:
    """Live countdown. Remaining time is computed from DB timestamps on every tick, so it is
    correct across reruns/refreshes. A fragment ticks once a second only while running."""
    running = session is not None and session["status"] == "running"
    idle_seconds = max(0, _selected_minutes()) * 60

    def _tick():
        current = _safe(lambda: db.get_open_focus_session(profile_type, profile_key))
        if running and current is None:
            # The session finished (timer hit 00:00 -> auto-completed by the DB layer) or was closed
            # elsewhere: refresh the whole page so status, stats, streak and break banner update.
            st.rerun()
        _draw_timer(current, idle_seconds)

    if hasattr(st, "fragment"):
        st.fragment(run_every=1 if running else None)(_tick)()
    else:  # very old Streamlit: bounded 1s refresh loop, only while a session is running
        _tick()
        if running:
            time.sleep(1)
            st.rerun()


def _draw_timer(session, idle_seconds: int) -> None:
    if session is not None:
        remaining = session["remaining_seconds"]
        planned = session["planned_seconds"]
        pct = 100.0 * (planned - remaining) / planned if planned else 0.0
        sub = "Focusing…" if session["status"] == "running" else "Paused — resume when you're ready"
        shown = _fmt_clock(remaining)
    else:
        pct, sub, shown = 0.0, "Choose a duration and start", _fmt_clock(idle_seconds)
    ring = f"conic-gradient(#8b5cf6 {pct:.1f}%, var(--ring-track) 0)"
    st.markdown(
        f'<div class="fm-timer-wrap"><div class="fm-ring" style="background:{ring}">'
        f'<div class="fm-ring-inner"><div class="fm-time">{shown}</div>'
        f'<div class="fm-sub">{html.escape(sub)}</div></div></div></div>',
        unsafe_allow_html=True,
    )


def _render_controls(profile_type, profile_key, session, completed_banner, distraction_free: bool) -> None:
    if session is None:
        if st.button("▶ Start Focus" if completed_banner is None else "▶ Start Next Session",
                     key="fm_start", type="primary", use_container_width=True):
            minutes = _selected_minutes()
            if minutes < 1 or minutes > 480:
                st.error("Please choose a duration between 1 and 480 minutes.")
            else:
                goal = (st.session_state.get("fm_goal") or "").strip() or None
                try:
                    # Idempotent: if a session is already open (double click / rerun) it is reused.
                    db.create_focus_session(profile_type, profile_key, minutes, goal)
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:  # noqa: BLE001
                    log.exception("Could not start focus session")
                    st.error("Couldn't start the session right now. Please try again.")
                else:
                    st.rerun()
        if not distraction_free:
            if st.button("🧘 Enter Distraction-Free Mode", key="fm_enter_df", use_container_width=True):
                st.session_state[DF_KEY] = True
                st.rerun()
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        if session["status"] == "running":
            if st.button("⏸ Pause", key="fm_pause", use_container_width=True):
                _run_action(db.pause_focus_session, profile_type, profile_key)
        else:
            if st.button("▶ Resume", key="fm_resume", type="primary", use_container_width=True):
                _run_action(db.resume_focus_session, profile_type, profile_key)
    with c2:
        if st.button("⏹ End Session", key="fm_end", use_container_width=True,
                     help="Stop early — the time you focused is still recorded"):
            _run_action(db.end_focus_session, profile_type, profile_key)
    with c3:
        if st.button("↺ Reset", key="fm_reset", use_container_width=True,
                     help="Discard this session (not recorded in history)"):
            _run_action(db.reset_focus_session, profile_type, profile_key)

    if session["status"] == "paused":
        st.caption(f"⏸ Paused {session.get('pause_count', 1)}× this session")
    if not distraction_free:
        if st.button("🧘 Enter Distraction-Free Mode", key="fm_enter_df_open", use_container_width=True):
            st.session_state[DF_KEY] = True
            st.rerun()


def _run_action(fn, profile_type, profile_key) -> None:
    try:
        fn(profile_type, profile_key)
    except Exception:  # noqa: BLE001
        log.exception("Focus action failed")
        st.error("That action couldn't be completed. Please try again.")
        return
    st.rerun()


# ---------------------------------------------------------------------------
# Daily target, streak, score
# ---------------------------------------------------------------------------
def _save_target(profile_type: str, profile_key: str) -> None:
    try:
        db.set_focus_daily_target(profile_type, profile_key, st.session_state["fm_target_sel"])
    except Exception:  # noqa: BLE001
        log.exception("Could not save daily target")
        st.session_state[ERROR_KEY] = True


def _render_target_block(profile_type, profile_key, day, editable: bool) -> None:
    with st.container(border=True):
        st.markdown("#### ⏳ Daily Focus Target")
        if day is None:
            st.caption("Focus statistics are unavailable right now.")
            return
        if editable:
            options = sorted(set(TARGET_OPTIONS_MIN + [day["target_minutes"]]))
            st.selectbox(
                "Daily target", options, index=options.index(day["target_minutes"]),
                format_func=_fmt_minutes, key="fm_target_sel",
                on_change=_save_target, args=(profile_type, profile_key),
            )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Target", _fmt_minutes(day["target_minutes"]))
        c2.metric("Completed", _fmt_minutes(day["focused_minutes"]))
        c3.metric("Remaining", _fmt_minutes(day["remaining_minutes"]))
        c4.metric("Progress", f"{day['progress_pct']:.1f}%")
        st.progress(min(1.0, day["progress_pct"] / 100.0))
        logged = _logged_study_hours_today()
        if logged is not None and editable:
            st.caption(f"📚 Study hours logged in today's Prediction report: {logged:.1f}h "
                       f"(separate from focus-tracked time)")


def _logged_study_hours_today():
    """Read-only look at today's saved report (existing table); never modifies it."""
    try:
        reports = db.get_all_reports()
        if reports.empty:
            return None
        today = datetime.now().date().isoformat()
        rows = reports[reports["date"].dt.date.astype(str) == today]
        return None if rows.empty else float(rows.iloc[-1]["study_hours"])
    except Exception:  # noqa: BLE001
        return None


def _render_streak_and_score(profile_type, profile_key) -> None:
    streak = _safe(lambda: db.get_focus_streak(profile_type, profile_key), 0)
    score = _safe(lambda: db.get_focus_score(profile_type, profile_key), None)

    with st.container(border=True):
        unit = "day" if streak == 1 else "days"
        st.markdown(f'<span class="streak-pill">🔥 Current Focus Streak: {streak} {unit}</span>', unsafe_allow_html=True)
        st.caption("Consecutive days with at least one completed focus session.")

    with st.container(border=True):
        st.markdown("#### ⭐ Focus Score")
        if not score or score["sessions"] == 0:
            st.markdown('<div class="fm-score">—</div>', unsafe_allow_html=True)
            st.caption("Complete a focus session to get your score. It's calculated from your real sessions "
                       "in the last 7 days.")
            return
        st.markdown(f'<div class="fm-score">{score["score"]}<span style="font-size:1rem;color:var(--text-sub)"> / 100</span></div>',
                    unsafe_allow_html=True)
        st.caption(f'Based on {score["sessions"]} finished session(s) in the last {score["days"]} days.')
        with st.expander("How is this calculated?"):
            st.markdown(
                f"- **Focus volume** — {score['volume']:.1f} / 40 (focused time vs. your daily target × {score['days']} days)\n"
                f"- **Completion** — {score['completion']:.1f} / 30 (share of sessions you finished)\n"
                f"- **Steadiness** — {score['steadiness']:.1f} / 15 (fewer pauses per session is better)\n"
                f"- **Consistency** — {score['consistency']:.1f} / 15 (focus streak, up to 7 days)"
            )


# ---------------------------------------------------------------------------
# Recommendations (rule-based from real data)
# ---------------------------------------------------------------------------
def _render_recommendations(profile_type, profile_key, day) -> None:
    score = _safe(lambda: db.get_focus_score(profile_type, profile_key), None)
    totals = _safe(lambda: db.get_focus_totals(profile_type, profile_key), None)
    streak = score["streak"] if score else 0
    recs: list[str] = []

    if totals is not None and totals["finished"] == 0:
        recs.append("Start with a single 25-minute session — short sessions are the easiest way to build the habit.")
    if day is not None:
        if day["sessions_completed"] == 0 and streak > 0:
            recs.append(f"Complete one session today to keep your {streak}-day focus streak alive.")
        if 0 < day["remaining_minutes"] <= 60 and day["focused_minutes"] > 0:
            recs.append(f"You're only {_fmt_minutes(day['remaining_minutes'])} away from today's focus target.")
        if day["progress_pct"] >= 100:
            recs.append("Daily target reached — great work. Rest well; tomorrow's streak starts with one session.")
    if score and score["sessions"] >= 3:
        if score["completed"] / score["sessions"] < 0.5:
            recs.append("Less than half of your recent sessions were completed — try 25-minute sessions to raise completion.")
        if score["steadiness"] < 7.5:
            recs.append("You pause often. Silence notifications and keep your phone out of reach before you start.")

    if not recs:
        return
    st.markdown("#### 💡 Focus Recommendations")
    for r in recs[:3]:
        st.markdown(f"- {r}")


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
def _render_history(profile_type, profile_key) -> None:
    st.markdown("---")
    st.markdown("### 🕘 Focus History")
    totals = _safe(lambda: db.get_focus_totals(profile_type, profile_key), None)
    streak = _safe(lambda: db.get_focus_streak(profile_type, profile_key), 0)
    history = _safe(lambda: db.get_focus_history(profile_type, profile_key, limit=100), pd.DataFrame())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total focus time", _fmt_minutes(totals["total_minutes"]) if totals else "—")
    m2.metric("Sessions completed", totals["completed"] if totals else "—")
    m3.metric("Avg session duration", _fmt_minutes(totals["avg_minutes"]) if totals else "—")
    m4.metric("Current streak", f"{streak} day{'s' if streak != 1 else ''}")

    if history is None or history.empty:
        st.info("No focus sessions yet. Start your first session above — finished sessions show up here.")
        return

    rows = []
    for _, r in history.iterrows():
        planned = float(r["planned_seconds"] or 0)
        elapsed = float(r["elapsed_seconds"] or 0)
        rows.append({
            "Date": r["date"].strftime("%b %d, %Y"),
            "Goal": r["label"] if isinstance(r["label"], str) and r["label"] else "—",
            "Duration": _fmt_minutes(planned / 60.0),
            "Focused": _fmt_minutes(elapsed / 60.0),
            "Status": "Completed" if r["status"] == "completed" else "Ended early",
            "Completion": f"{min(100.0, 100.0 * elapsed / planned):.0f}%" if planned else "—",
            "Pauses": int(r.get("pause_count", 0) or 0),
            "Score contribution": db.focus_session_quality(planned, elapsed, r["status"], r.get("pause_count", 0)),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Score contribution (0–100) rates each session: time focused vs. planned, finishing it, and few pauses.")
