import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, analytics
from core.theme import inject_theme, render_top_nav

st.set_page_config(page_title="FutureForge | Achievements", page_icon="🏆", layout="wide")
inject_theme()
render_top_nav("Achievements")

st.markdown('<div class="hero-title">🏆 Achievements</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Unlocked based on your real saved history — not decorative.</div>', unsafe_allow_html=True)

df = db.get_all_reports()
tests_df = db.get_all_test_results()
streaks = analytics.compute_streaks(df)

st.markdown("### 🔥 Streaks")
st.markdown(
    f'<span class="streak-pill">🔥 Report Streak: {streaks["report_streak"]} days</span>'
    f'<span class="streak-pill">🏆 Best Report Streak: {streaks["best_report_streak"]} days</span>'
    f'<span class="streak-pill">🌙 Sleep Streak: {streaks["sleep_streak"]} days</span>'
    f'<span class="streak-pill">🧠 Focus Streak: {streaks["focus_streak"]} days</span>',
    unsafe_allow_html=True,
)

st.markdown("---")
st.markdown("### 🏅 Achievements")

achievements = analytics.compute_achievements(df, tests_df, streaks)
cols = st.columns(4)
for i, a in enumerate(achievements):
    with cols[i % 4]:
        cls = "" if a["unlocked"] else "achievement-locked"
        st.markdown(
            f"""
            <div class="achievement-card {cls}">
                <div class="achievement-icon">{a['icon']}</div>
                <b>{a['title']}</b>
                <p style="font-size:0.8rem; color:var(--text-sub);">{a['desc']}</p>
                <p style="font-size:0.75rem;">{'✅ Unlocked' if a['unlocked'] else '🔒 Locked'}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

unlocked_count = sum(1 for a in achievements if a["unlocked"])
st.markdown("---")
st.progress(unlocked_count / len(achievements))
st.caption(f"{unlocked_count} of {len(achievements)} achievements unlocked")
