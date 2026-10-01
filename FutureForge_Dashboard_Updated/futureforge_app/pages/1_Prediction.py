import sys
import time
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, scoring, analytics
from core.theme import inject_theme, render_top_nav, load_predictor
from core.orb import render_orb
from core import recommender_ui, focus_lab_ui
from services.focus_lab import recommendation_engine as fle

st.set_page_config(page_title="FutureForge | Prediction", page_icon="🔮", layout="wide")
inject_theme()
render_top_nav("Prediction")

predictor = load_predictor()
reports_df = db.get_all_reports()

st.markdown('<div class="hero-title">🔮 Run a Prediction</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Hybrid ML engine — KMeans clustering · LSTM sequence model (or statistical fallback) · Random Forest regression</div>',
    unsafe_allow_html=True,
)


def gauge_chart(score: float) -> go.Figure:
    color = "#34d399" if score >= 75 else "#fbbf24" if score >= 55 else "#f87171"
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": " / 100", "font": {"size": 32, "family": "Space Grotesk"}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color, "thickness": 0.28},
                "bgcolor": "rgba(0,0,0,0)",
                "steps": [
                    {"range": [0, 55], "color": "rgba(248,113,113,0.15)"},
                    {"range": [55, 75], "color": "rgba(251,191,36,0.15)"},
                    {"range": [75, 100], "color": "rgba(52,211,153,0.15)"},
                ],
            },
        )
    )
    fig.update_layout(height=240, margin=dict(l=20, r=20, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def build_action_plan(payload: dict, metrics: dict) -> dict[str, str]:
    score = metrics["focus_score"]
    sleep = payload["sleep_hours"]
    screen = payload["screen_time"]
    mood = payload["mood"]

    if score >= 80:
        focus_action = "Keep the current routine and protect one uninterrupted deep-work block in your best focus window."
    elif score >= 60:
        focus_action = "Break your study work into two 25–35 minute sessions with a 5-minute reset in between."
    else:
        focus_action = "Start with the easiest task first, then move to the hardest task only after 15 minutes of warm-up."

    if mood in {"stressed", "tired"}:
        recovery = "Take a 5-minute walk, do 3 rounds of box breathing, and avoid late-night screen scrolling."
    elif sleep < 6.5:
        recovery = "Prioritize sleep first: set a 10:30 PM cutoff and reduce stimulation for the next 90 minutes."
    else:
        recovery = "Keep the same routine and stay consistent with hydration, breaks, and a short reset before work."

    if sleep < 6.5:
        workout = "Light mobility + 10-minute walk; keep it easy and avoid heavy training today."
    elif screen > 5:
        workout = "20-minute brisk walk or cycling session, then do 10 minutes of stretching."
    elif mood == "focused":
        workout = "30-minute strength or cardio session after your study block to maintain momentum."
    else:
        workout = "15–20 minute movement session: walk, mobility, or bodyweight circuit."

    best_window = payload.get("focus_window", "Morning")
    return {
        "focus_action": focus_action,
        "recovery": recovery,
        "workout": workout,
        "best_window": best_window,
    }


def build_next_steps(payload: dict, metrics: dict) -> list[str]:
    suggestions: list[str] = []
    model_actions = [item.get("action", "") for item in metrics.get("feedback", [])[:3] if item.get("action")]
    suggestions.extend(model_actions)

    if payload["sleep_hours"] < 7:
        suggestions.append("Aim for 7.5–8.5 hours of sleep tonight and stop screens 60–90 minutes before bed.")
    if payload["screen_time"] > 4.5:
        suggestions.append("Cut evening screen time by 1–2 hours and keep your phone out of reach during deep work.")
    if payload["mood"] in {"tired", "stressed"}:
        suggestions.append("Do a 5-minute walk or 3-minute breathing reset before starting your next study block.")
    if payload["study_hours"] < 4:
        suggestions.append("Schedule one focused 30–45 minute session in your best focus window instead of a long tiring block.")
    if payload["sleep_hours"] >= 7 and payload["screen_time"] <= 4 and payload["mood"] in {"focused", "balanced"}:
        suggestions.append("Repeat this routine: protect a single deep-work block and keep the same sleep timing tomorrow.")

    seen = set()
    ordered: list[str] = []
    for item in suggestions:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            ordered.append(item)
    return ordered[:5]


st.markdown("### 🧠 Daily Check-In")

with st.form("prediction_form", clear_on_submit=False):
    c1, c2 = st.columns(2)
    with c1:
        study_hours = st.slider("📚 Study Hours", 0.0, 12.0, 6.5, 0.1)
        sleep_hours = st.slider("😴 Sleep Hours", 0.0, 12.0, 7.5, 0.1)
        screen_time = st.slider("📱 Screen Time (hrs)", 0.0, 12.0, 3.2, 0.1)
    with c2:
        mood = st.selectbox("🙂 Mood", ["focused", "balanced", "tired", "stressed"], index=0)
        focus_window = st.selectbox("⏰ Best Focus Time", ["Morning", "Afternoon", "Evening", "Late Night"], index=0)
        stress_level = st.slider("⚠️ Stress Level (0-10)", 0, 10, 5)

    run = st.form_submit_button("🚀 Predict & Suggest Next Steps", use_container_width=True)
    save_checkin = st.form_submit_button("💾 Save Check-In", use_container_width=True)

if run or save_checkin:
    payload = {"study_hours": study_hours, "sleep_hours": sleep_hours, "screen_time": screen_time, "mood": mood}
    start = time.time()
    result = predictor.predict(payload)
    latency_ms = (time.time() - start) * 1000
    metrics = scoring.compute_scores(payload, result)
    metrics["name"] = st.session_state.get("user_name", "")
    metrics["focus_window"] = focus_window
    metrics["stress_level"] = stress_level
    metrics["action_plan"] = build_action_plan(payload, metrics)
    metrics["next_steps"] = build_next_steps(payload, metrics)
    st.session_state.last_prediction = metrics
    st.session_state.pop("last_report_id", None)   # new prediction -> not saved yet

    if save_checkin:
        st.session_state["last_report_id"] = db.insert_report(metrics, force_new=False)
        st.success("✓ Check-in saved to your history.")

if "last_prediction" in st.session_state:
    m = st.session_state.last_prediction
    col1, col2 = st.columns([1, 1.4])

    with col1:
        with st.container():
            st.markdown("#### 🧠 Neural Focus Orb")
            render_orb(
                score=m["focus_score"],
                label="Focus",
                height=320,
                theme=st.session_state.get("theme", "dark"),
                key="pred_orb",
            )
            with st.expander("📈 Classic gauge view"):
                st.plotly_chart(gauge_chart(m["focus_score"]), use_container_width=True)
            risk_class = m["risk"]
            st.markdown(f"Risk: **{risk_class.upper()}**  ·  Cluster #{m['cluster']}")

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Stress", f"{m['stress_score']:.0f}/100")
        mc2.metric("Mood", f"{m['mood_score']:.1f}/10")
        mc3.metric("Confidence", f"{m['prediction_confidence']:.0f}%")

        st.markdown("#### 🔮 AI Prediction")
        with st.container():
            st.markdown(f"**Prediction:** {m['prediction']}")
            st.markdown(f"**Confidence:** {m['prediction_confidence']:.0f}%")
            st.markdown(f"**Key Factors:** {', '.join(m['key_factors']) if m['key_factors'] else '—'}")
            st.markdown(f"**Why:** {m['prediction_explanation'] or '—'}")

        comparison = analytics.history_comparison(reports_df, m)
        if comparison:
            st.markdown(f"##### 📊 Based on your last {comparison['n_days']} days")
            st.markdown(
                f"Focus: today **{comparison['focus']['today']:.0f}** vs avg **{comparison['focus']['avg']:.0f}** "
                f"({comparison['focus']['delta_pct']:+.1f}%)"
            )
            st.markdown(
                f"Stress: today **{comparison['stress']['today']:.0f}** vs avg **{comparison['stress']['avg']:.0f}** "
                f"({comparison['stress']['delta_pct']:+.1f}%)"
            )

        already_saved = db.report_exists_for_date(m["date"])
        save_col1, save_col2 = st.columns(2)
        if already_saved:
            st.warning("A report already exists for today.")
            if save_col1.button("🔁 Overwrite Today's Report", use_container_width=True):
                st.session_state["last_report_id"] = db.insert_report(m, force_new=False)
                st.success("✓ Prediction saved to history")
            if save_col2.button("➕ Save as New Entry", use_container_width=True):
                st.session_state["last_report_id"] = db.insert_report(m, force_new=True)
                st.success("✓ Prediction saved to history")
        else:
            if st.button("💾 Save to History", use_container_width=True):
                st.session_state["last_report_id"] = db.insert_report(m, force_new=False)
                st.success("✓ Prediction saved to history")
                st.balloons()

    with col2:
        st.markdown("#### 🤖 AI Action Plan")
        plan = m.get("action_plan") or {}
        st.markdown(
            f"""
            <div class="glass-card">
                <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 12px;">🎯 Best move for today</div>
                <div style="margin-bottom: 10px;"><b>Focus action:</b> {plan.get('focus_action', 'Keep a consistent study block and avoid overload.')}</div>
                <div style="margin-bottom: 10px;"><b>Recovery:</b> {plan.get('recovery', 'Take a short reset and protect your sleep window.')}</div>
                <div style="margin-bottom: 10px;"><b>Workout:</b> {plan.get('workout', 'Light movement session to improve recovery.')}</div>
                <div><b>Best window:</b> {plan.get('best_window', 'Morning')} · keep the first high-focus block there.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if m.get("next_steps"):
            st.markdown("##### ✅ Recommended Next Steps")
            for step in m["next_steps"]:
                st.markdown(f"- {step}")
            st.markdown("---")

        recommender_ui.render_prediction_recommendation(
            {k: m[k] for k in ("study_hours", "sleep_hours", "screen_time", "mood")},
            m["focus_score"], m["prediction_confidence"])
        st.markdown("---")

        st.markdown("##### 🔍 Deeper Insights")
        for insight in m["feedback"]:
            st.markdown(f"### {insight['title']} · {insight['priority']}")
            st.markdown(f"Tag: {insight['tag']} | Confidence: {insight['confidence']}%")
            st.markdown(f"**Why:** {insight['why']}")
            st.markdown(f"**Impact:** {insight['impact']}")
            st.markdown(f"**Action:** {insight['action']}")
            st.markdown(f"**Outcome:** {insight['outcome']}")
            st.markdown("---")
    # Focus Lab recommendation under the prediction: risk detected from THIS prediction -> recommended test
    st.markdown("---")
    focus_lab_ui.render_risk_card(
        "student", fle.analyze_student({k: m[k] for k in ("study_hours", "sleep_hours", "screen_time", "mood")}, m),
        st.session_state.get("last_report_id"))
else:
    st.info("Set your inputs in the sidebar and click **Run Prediction** to get started.")

st.markdown("---")
st.markdown("#### 📋 Prediction History")
if not reports_df.empty:
    hist_view = reports_df.sort_values("date", ascending=False)[
        ["date", "prediction", "prediction_confidence", "focus_score", "stress_score", "mood_score"]
    ].rename(
        columns={
            "date": "Date",
            "prediction": "Prediction",
            "prediction_confidence": "Confidence %",
            "focus_score": "Focus",
            "stress_score": "Stress",
            "mood_score": "Mood",
        }
    )
    st.dataframe(hist_view, use_container_width=True, hide_index=True)
else:
    st.caption("No predictions saved yet.")
