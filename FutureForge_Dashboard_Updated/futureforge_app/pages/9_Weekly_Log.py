import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, scoring
from core.theme import inject_theme, render_top_nav, load_predictor

st.set_page_config(page_title="FutureForge | Weekly Log", page_icon="📅", layout="wide")
inject_theme()
render_top_nav("Weekly Log")

predictor = load_predictor()

st.markdown('<div class="hero-title">📅 Weekly Log</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Log a full week — sleep, study hours, screen time — in one table. '
    "Each row is auto-dated with the correct day, so you can double-check exactly which "
    "entry belongs to which date before saving or exporting.</div>",
    unsafe_allow_html=True,
)

MOOD_OPTIONS = ["focused", "balanced", "tired", "stressed"]

# ---------------------------------------------------------------------------
# Week picker — any date snaps to that week's Monday→Sunday
# ---------------------------------------------------------------------------
anchor = st.date_input("Pick any date in the week you want to log", value=date.today())
week_start = anchor - timedelta(days=anchor.weekday())  # Monday
week_dates = [week_start + timedelta(days=i) for i in range(7)]

nav1, nav2, nav3 = st.columns([1, 2, 1])
if nav1.button("⬅️ Previous week", use_container_width=True):
    st.session_state["_weeklog_anchor"] = week_start - timedelta(days=1)
    st.rerun()
nav2.markdown(
    f"<div style='text-align:center; padding-top:6px;'><b>{week_dates[0].strftime('%b %d')} – {week_dates[-1].strftime('%b %d, %Y')}</b></div>",
    unsafe_allow_html=True,
)
if nav3.button("Next week ➡️", use_container_width=True):
    st.session_state["_weeklog_anchor"] = week_start + timedelta(days=7)
    st.rerun()

if "_weeklog_anchor" in st.session_state and st.session_state["_weeklog_anchor"] != anchor:
    anchor = st.session_state["_weeklog_anchor"]
    week_start = anchor - timedelta(days=anchor.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]

st.markdown("---")

# ---------------------------------------------------------------------------
# Build the editable table — prefill from existing saved reports for this week
# if they exist, otherwise sensible defaults, so you can see/verify what's
# already saved before overwriting it.
# ---------------------------------------------------------------------------
reports_df = db.get_all_reports()
existing_by_date = {}
if not reports_df.empty:
    for _, row in reports_df.iterrows():
        existing_by_date[row["date"].date().isoformat()] = row

rows = []
for d in week_dates:
    key = d.isoformat()
    if key in existing_by_date:
        r = existing_by_date[key]
        rows.append(
            {
                "Date": d.strftime("%Y-%m-%d"), "Day": d.strftime("%A"),
                "Study Hours": float(r["study_hours"]), "Sleep Hours": float(r["sleep_hours"]),
                "Screen Time": float(r["screen_time"]), "Mood": r["mood"], "Already Saved": "✅",
            }
        )
    else:
        rows.append(
            {
                "Date": d.strftime("%Y-%m-%d"), "Day": d.strftime("%A"),
                "Study Hours": 5.5, "Sleep Hours": 7.5, "Screen Time": 3.5, "Mood": "balanced", "Already Saved": "—",
            }
        )

edited = st.data_editor(
    pd.DataFrame(rows),
    column_config={
        "Date": st.column_config.TextColumn("Date", disabled=True),
        "Day": st.column_config.TextColumn("Day", disabled=True),
        "Study Hours": st.column_config.NumberColumn("Study Hours", min_value=0.0, max_value=16.0, step=0.5),
        "Sleep Hours": st.column_config.NumberColumn("Sleep Hours", min_value=0.0, max_value=14.0, step=0.5),
        "Screen Time": st.column_config.NumberColumn("Screen Time (hrs)", min_value=0.0, max_value=16.0, step=0.5),
        "Mood": st.column_config.SelectboxColumn("Mood", options=MOOD_OPTIONS),
        "Already Saved": st.column_config.TextColumn("Already Saved", disabled=True, width="small"),
    },
    hide_index=True,
    use_container_width=True,
    key=f"weeklog_editor_{week_start.isoformat()}",
)

# ---------------------------------------------------------------------------
# Quick sanity flags — spot obviously "wrong" entries before saving
# ---------------------------------------------------------------------------
def _flags(row) -> list[str]:
    f = []
    if row["Sleep Hours"] < 5:
        f.append("⚠️ Very low sleep")
    elif row["Sleep Hours"] > 11:
        f.append("⚠️ Unusually high sleep")
    if row["Screen Time"] > 8:
        f.append("⚠️ Very high screen time")
    if row["Study Hours"] > 12:
        f.append("⚠️ Unusually high study hours")
    if row["Study Hours"] + row["Sleep Hours"] + row["Screen Time"] > 24:
        f.append("🚫 Hours add up to more than 24 in a day")
    return f

flag_rows = []
for _, row in edited.iterrows():
    fl = _flags(row)
    if fl:
        flag_rows.append(f"**{row['Day']} ({row['Date']})** — " + ", ".join(fl))

if flag_rows:
    st.warning("Some entries look off — worth double-checking:\n\n" + "\n\n".join(flag_rows))

st.markdown("---")

save_col, export_col = st.columns([1, 1])

# ---------------------------------------------------------------------------
# Save the whole week — runs each day through the real predictor so every
# row gets a proper focus/stress/mood/productivity score, not just raw inputs.
# ---------------------------------------------------------------------------
with save_col:
    if st.button("💾 Save Whole Week to History", use_container_width=True):
        saved_rows = []
        progress = st.progress(0.0)
        for i, (_, row) in enumerate(edited.iterrows()):
            d = datetime.strptime(row["Date"], "%Y-%m-%d").date()
            payload = {
                "study_hours": float(row["Study Hours"]),
                "sleep_hours": float(row["Sleep Hours"]),
                "screen_time": float(row["Screen Time"]),
                "mood": row["Mood"],
            }
            result = predictor.predict(payload)
            metrics = scoring.compute_scores(payload, result, for_date=d)
            metrics["name"] = st.session_state.get("user_name", "")
            db.insert_report(metrics, force_new=False)
            saved_rows.append(metrics)
            progress.progress((i + 1) / 7)
        st.session_state["_weeklog_last_saved"] = saved_rows
        st.success(f"✅ Saved all 7 days ({week_dates[0].strftime('%b %d')} – {week_dates[-1].strftime('%b %d')}) to History.")
        st.balloons()

with export_col:
    export_df = edited.copy()
    export_df.insert(0, "Week", f"{week_dates[0].isoformat()} to {week_dates[-1].isoformat()}")
    st.download_button(
        "⬇️ Export This Week (CSV)",
        export_df.to_csv(index=False).encode("utf-8"),
        f"futureforge_week_{week_dates[0].isoformat()}_to_{week_dates[-1].isoformat()}.csv",
        "text/csv",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Results — what actually got scored, so you can verify correctness at a glance
# ---------------------------------------------------------------------------
if "_weeklog_last_saved" in st.session_state:
    st.markdown("#### 📊 This Week's Scores (just saved)")
    res_df = pd.DataFrame(st.session_state["_weeklog_last_saved"])
    view = res_df[["date", "day", "study_hours", "sleep_hours", "screen_time", "mood", "focus_score", "stress_score", "productivity_score"]].rename(
        columns={
            "date": "Date", "day": "Day", "study_hours": "Study", "sleep_hours": "Sleep",
            "screen_time": "Screen", "mood": "Mood", "focus_score": "Focus",
            "stress_score": "Stress", "productivity_score": "Productivity %",
        }
    )
    st.dataframe(view, use_container_width=True, hide_index=True)
