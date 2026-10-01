"""FutureForge — Dashboard (Home)"""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from core import db, analytics
from core import predictions_db as pdb
from services.registry import DOMAINS
from core.theme import inject_theme, render_top_nav, load_predictor
from core.orb import render_orb

st.set_page_config(page_title="FutureForge | Dashboard", page_icon="🔮", layout="wide")
inject_theme()
name_input = render_top_nav("app")
st.session_state.user_name = name_input

predictor = load_predictor()
reports_df = db.get_all_reports()
tests_df = db.get_all_test_results()

greeting_hour = datetime.now().hour
greeting = "Good morning" if greeting_hour < 12 else "Good afternoon" if greeting_hour < 18 else "Good evening"
today_str = datetime.now().strftime("%A, %B %d")

first_name = (name_input or "").split()[0] if (name_input or "").split() else ""
st.markdown(f"## Welcome back{', ' + first_name if first_name else ''} 👋")
st.caption(f"{greeting} · {today_str} · 🟢 AI Analysis Ready")

# ---------------------------------------------------------------------------
# Multi-domain overview (all numbers come from this user's saved predictions)
# ---------------------------------------------------------------------------
ov = pdb.overview_stats()
o1, o2, o3, o4, o5 = st.columns(5)
o1.metric("Total Predictions", ov["total"])
o2.metric("Active Domain", ov["active_domain"] or "—")
o3.metric("Latest Prediction", f"{ov['latest']['score']:.0f}" if ov["latest"] else "—")
o4.metric("Current Risk", ov["current_risk"].title() if ov["current_risk"] else "—")
o5.metric("Average Score", f"{ov['avg_score']:.1f}" if ov["avg_score"] is not None else "—")

if ov["total"]:
    with st.expander("🕒 Recent activity", expanded=False):
        for _, row in ov["recent"].iterrows():
            st.markdown(f"**{row['domain_title']}** · {row['score']:.0f} · {row['risk'].title()} risk · "
                        f"{row['created_at'].strftime('%b %d, %H:%M')}")

st.markdown("### 🧭 Forecasting Domains")
for start in range(0, len(DOMAINS), 3):
    cols = st.columns(3)
    for col, d in zip(cols, DOMAINS[start:start + 3]):
        with col:
            st.markdown(
                f'''<div class="glass-card domain-card"><div class="dc-icon">{d.icon}</div>
                <div class="dc-title">{d.title}</div><div class="dc-desc">{d.blurb}</div></div>''',
                unsafe_allow_html=True,
            )
            if st.button("Open", key=f"open_{d.key}", use_container_width=True):
                st.switch_page(d.page)
st.markdown("---")

today_date = datetime.now().date().isoformat()
today_row = reports_df[reports_df["date"].dt.date.astype(str) == today_date] if not reports_df.empty else reports_df

# ---------------------------------------------------------------------------
# Today's Overview
# ---------------------------------------------------------------------------
st.markdown("### 📊 Today's Overview")

if not today_row.empty:
    r = today_row.iloc[-1]

    st.markdown("#### Focus Snapshot")
    render_orb(
        score=r["focus_score"], label="Focus", height=260,
        theme=st.session_state.get("theme", "dark"), key="home_orb",
    )

    comparison = analytics.history_comparison(
        reports_df[reports_df["date"].dt.date.astype(str) != today_date],
        {
            "focus_score": r["focus_score"],
            "stress_score": r["stress_score"],
            "sleep_hours": r["sleep_hours"],
            "productivity_score": r["productivity_score"],
        },
    )
    if comparison:
        st.markdown("##### Compared to your recent average")
        cc1, cc2, cc3 = st.columns(3)
        cc1.markdown(
            f"**Focus** — Today {comparison['focus']['today']:.0f} vs avg {comparison['focus']['avg']:.0f} "
            f"({comparison['focus']['delta_pct']:+.1f}%)"
        )
        cc2.markdown(
            f"**Stress** — Today {comparison['stress']['today']:.0f} vs avg {comparison['stress']['avg']:.0f} "
            f"({comparison['stress']['delta_pct']:+.1f}%)"
        )
        cc3.markdown(
            f"**Sleep** — Today {comparison['sleep']['today']:.1f}h vs avg {comparison['sleep']['avg']:.1f}h "
            f"({comparison['sleep']['delta_min']:+d} min)"
        )
else:
    st.info(
        "No report saved for today yet. Head to **Prediction** to run today's analysis, "
        "then save it here to start building your history."
    )
    if st.button("🔮 Run Today's Prediction →"):
        st.switch_page("pages/1_Prediction.py")

st.markdown("---")

# ---------------------------------------------------------------------------
# Smart Alerts
# ---------------------------------------------------------------------------
alerts = analytics.smart_alerts(reports_df)
if alerts:
    st.markdown("### 🔔 Smart Alerts")
    for a in alerts:
        st.markdown(f"{a['icon']} {a['message']}")
    st.markdown("---")

# ---------------------------------------------------------------------------
# Recent History + Quick Actions
# ---------------------------------------------------------------------------
col_left, col_right = st.columns([1.5, 1])

with col_left:
    st.markdown("### 🕘 Recent Reports")
    if reports_df.empty:
        st.markdown(
            "No reports yet. Complete your first prediction and save it to start building your personal performance history."
        )
    else:
        recent = reports_df.sort_values("date", ascending=False).head(5)
        for _, row in recent.iterrows():
            st.markdown(
                f"""
                <div class="glass-card" style="margin-bottom:10px; padding:14px 18px;">
                    <b>{row['date'].strftime('%b %d')}</b> &nbsp;|&nbsp;
                    Focus {row['focus_score']:.0f} &nbsp;·&nbsp;
                    Stress {row['stress_score']:.0f} &nbsp;·&nbsp;
                    Prediction: {row['prediction']}
                </div>
                """,
                unsafe_allow_html=True,
            )
        if st.button("View Full History →"):
            st.switch_page("pages/2_History.py")

with col_right:
    st.markdown("### ⚡ Quick Actions")
    if st.button("🔮 Run Prediction", use_container_width=True):
        st.switch_page("pages/1_Prediction.py")
    if st.button("📅 Log This Week", use_container_width=True):
        st.switch_page("pages/9_Weekly_Log.py")
    if st.button("🧠 Take Focus Test", use_container_width=True):
        st.switch_page("pages/4_Focus_Lab.py")
    if st.button("😌 Relax for 5 Minutes", use_container_width=True):
        st.switch_page("pages/5_Stress_Relief.py")
    if st.button("📊 View Analytics", use_container_width=True):
        st.switch_page("pages/3_Analytics.py")

    streaks = analytics.compute_streaks(reports_df)
    if streaks["report_streak"] > 0 or streaks["best_report_streak"] > 0:
        st.markdown("##### 🔥 Streaks")
        st.markdown(
            f'<span class="streak-pill">🔥 {streaks["report_streak"]} Day Streak</span>'
            f'<span class="streak-pill">🏆 Best: {streaks["best_report_streak"]} Days</span>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# AI Insights preview
# ---------------------------------------------------------------------------
st.markdown("### 💡 AI Insights")
insights = analytics.generate_insights(reports_df)
for ins in insights[:3]:
    st.markdown(f"**{ins['type']}** — {ins['message']}")

st.markdown(
    '<p style="text-align:center; color:var(--text-sub); font-size:0.8rem; margin-top:24px;">'
    "FutureForge · Personal Performance Intelligence · Hybrid ML + Behavioral Analytics</p>",
    unsafe_allow_html=True,
)
