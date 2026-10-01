import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, analytics
from core.theme import inject_theme, render_top_nav

st.set_page_config(page_title="FutureForge | Analytics", page_icon="📊", layout="wide")
inject_theme()
render_top_nav("Analytics")
from core.domain_ui import maybe_render_domain_view
maybe_render_domain_view("analytics")  # non-Student active domain -> that domain's view, then stop

st.markdown('<div class="hero-title">📊 Analytics</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Trends and behavioral correlations from your saved history.</div>', unsafe_allow_html=True)

df = db.get_all_reports()

if df.empty:
    st.info("No data yet. Save at least a few daily reports from the Prediction page to unlock analytics.")
    st.stop()

period = st.radio("Period", ["7D", "30D", "90D", "1Y", "All"], horizontal=True, index=4)
plot_df = analytics.filter_period(df, period) if period != "All" else df
plot_df = plot_df.sort_values("date")

if plot_df.empty:
    st.warning("No data in this period.")
    st.stop()


def line_chart(y_col: str, title: str, color: str):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=plot_df["date"], y=plot_df[y_col], mode="lines+markers", line=dict(color=color, width=3), name=title)
    )
    fig.update_layout(
        title=title,
        height=260,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#eef0ff"},
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
    )
    return fig


st.markdown("### 📈 Trends")
tc1, tc2 = st.columns(2)
tc1.plotly_chart(line_chart("focus_score", "Focus Trend", "#8b5cf6"), use_container_width=True)
tc2.plotly_chart(line_chart("stress_score", "Stress Trend", "#f87171"), use_container_width=True)
tc3, tc4 = st.columns(2)
tc3.plotly_chart(line_chart("mood_score", "Mood Trend", "#34d399"), use_container_width=True)
tc4.plotly_chart(line_chart("sleep_hours", "Sleep Trend (hrs)", "#60a5fa"), use_container_width=True)
st.plotly_chart(line_chart("productivity_score", "Productivity Trend", "#fbbf24"), use_container_width=True)

st.markdown("---")
st.markdown("### 🔗 Correlations")


def scatter_chart(x_col: str, y_col: str, title: str):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df[x_col], y=plot_df[y_col], mode="markers",
            marker=dict(size=10, color=plot_df["focus_score"], colorscale="Viridis", showscale=False),
        )
    )
    fig.update_layout(
        title=title, height=280, margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#eef0ff"},
        xaxis=dict(title=x_col.replace("_", " ").title(), gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(title=y_col.replace("_", " ").title(), gridcolor="rgba(255,255,255,0.08)"),
    )
    return fig


sc1, sc2, sc3 = st.columns(3)
sc1.plotly_chart(scatter_chart("sleep_hours", "focus_score", "Focus vs Sleep"), use_container_width=True)
sc2.plotly_chart(scatter_chart("stress_score", "productivity_score", "Stress vs Productivity"), use_container_width=True)
sc3.plotly_chart(scatter_chart("mood_score", "focus_score", "Mood vs Focus"), use_container_width=True)

st.markdown("---")
st.markdown("### 💡 AI Insights")
for ins in analytics.generate_insights(df):
    st.markdown(f"**{ins['type']}** — {ins['message']}")

best = analytics.best_conditions(df)
if best:
    st.markdown("##### 🎯 Best Performance Conditions")
    st.markdown(
        f"You perform best when: **Sleep > {best['sleep_min']}h**, "
        f"**Stress < {best['stress_max']}**, **Mood > {best['mood_min']}**"
    )

st.markdown("---")
wc1, wc2 = st.columns(2)

with wc1:
    st.markdown("### 📅 Weekly Report")
    weekly = analytics.weekly_report(df)
    if weekly:
        st.markdown(
            f"""
            <div class="glass-card">
                <b>Week of {weekly['range']}</b><br/>
                Average Focus: {weekly['avg_focus']}<br/>
                Average Stress: {weekly['avg_stress']}<br/>
                Average Mood: {weekly['avg_mood']}<br/>
                Average Sleep: {weekly['avg_sleep_hours']:.1f}h<br/>
                Best Day: {weekly['best_day']}<br/>
                Most Challenging Day: {weekly['worst_day']}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.caption("Not enough recent data for a weekly report.")

with wc2:
    st.markdown("### 🗓️ Monthly Report")
    monthly = analytics.monthly_report(df)
    if monthly:
        improvement_txt = f"{monthly['improvement_pct']:+.1f}%" if monthly["improvement_pct"] is not None else "N/A"
        st.markdown(
            f"""
            <div class="glass-card">
                Average Focus: {monthly['avg_focus']}<br/>
                Average Stress: {monthly['avg_stress']}<br/>
                Average Mood: {monthly['avg_mood']}<br/>
                Average Sleep: {monthly['avg_sleep_hours']:.1f}h<br/>
                Average Productivity: {monthly['avg_productivity']}%<br/>
                Best Day: {monthly['best_day']}<br/>
                Worst Day: {monthly['worst_day']}<br/>
                Improvement vs previous month: {improvement_txt}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.caption("Not enough recent data for a monthly report.")

st.markdown("---")
st.markdown("### 🤖 Ask FutureForge")
st.caption("Rule-based Q&A over your saved history — not a generative chatbot.")
question = st.text_input("Ask about your data", placeholder="e.g. What was my best day? How has my stress changed?")
if question:
    q = question.lower()
    if "best day" in q:
        best_row = df.loc[df["focus_score"].idxmax()]
        st.write(f"Your best day was **{best_row['date'].strftime('%B %d')}** with a focus score of {best_row['focus_score']:.0f}.")
    elif "worst" in q or "low" in q:
        worst_row = df.loc[df["focus_score"].idxmin()]
        st.write(f"Your lowest focus day was **{worst_row['date'].strftime('%B %d')}** with a score of {worst_row['focus_score']:.0f}.")
    elif "stress" in q:
        st.write(f"Your average stress over the tracked period is **{df['stress_score'].mean():.0f}/100**.")
    elif "improve" in q or "focus" in q:
        best = analytics.best_conditions(df)
        if best:
            st.write(f"Based on your data, focus improves with sleep > {best['sleep_min']}h and stress < {best['stress_max']}.")
        else:
            st.write("Not enough data yet to determine what improves your focus.")
    elif "sleep" in q:
        st.write(f"Your average sleep is **{df['sleep_hours'].mean():.1f} hours**.")
    else:
        st.write("I can answer questions about your best/worst day, stress trend, sleep average, or what improves focus.")
