"""FutureForge — Smart Recommendation panel (Focus Lab): user enters inputs -> model score -> suggested test + focus plan."""
from __future__ import annotations

import streamlit as st

from core import db, recommender
from core.domain_ui import _input_widget
from services.registry import DOMAINS, get_predictor

_TEST_TAB = {"Reaction Time": "⚡ Reaction Time", "Stroop Test": "🎨 Stroop Test",
             "Attention Grid": "🎯 Attention Grid", "Memory Sequence": "🧩 Memory Sequence"}


def _apply_plan(minutes: int) -> None:
    """Button callback: preload the Focus Mode duration (25 / 50 preset, otherwise Custom)."""
    if minutes in (25, 50):
        st.session_state["fm_dur_choice"] = f"{minutes} min"
    else:
        st.session_state["fm_dur_choice"] = "Custom"
        st.session_state["fm_dur_custom"] = int(minutes)


def _student_inputs() -> dict:
    c1, c2 = st.columns(2)
    with c1:
        study = st.slider("📚 Study Hours", 0.0, 12.0, 6.5, 0.1, key="sr_study")
        sleep = st.slider("😴 Sleep Hours", 0.0, 12.0, 7.5, 0.1, key="sr_sleep")
    with c2:
        screen = st.slider("📱 Screen Time (hrs)", 0.0, 12.0, 3.2, 0.1, key="sr_screen")
        mood = st.selectbox("🙂 Mood", ["focused", "balanced", "tired", "stressed"], key="sr_mood")
    return {"study_hours": study, "sleep_hours": sleep, "screen_time": screen, "mood": mood}


def render_test_ranking(rec) -> None:
    """All 4 Focus Lab tests, best fit first (1st = do this now)."""
    st.markdown("##### 🧪 Focus Lab tests for you (best fit first)")
    for i, (t, why) in enumerate(rec.ranking, 1):
        st.markdown(f"{'⭐ ' if i == 1 else ''}**{i}. {_TEST_TAB[t]}** — {why}")
    st.caption("Open the matching tab in Focus Lab to take the test.")


def render_prediction_recommendation(payload: dict, focus_score: float, confidence) -> None:
    """Prediction page: recommendation from the just-computed Student model score."""
    rec = recommender.recommend(focus_score, payload, source="ml_model", confidence=confidence,
                                tests_df=db.get_all_test_results())
    st.markdown("#### 🧠 Suggested Focus Lab test & focus plan")
    st.markdown(f"**{rec.headline}**")
    render_test_ranking(rec)
    p1, p2, p3 = st.columns(3)
    p1.metric("Session", f"{rec.session_minutes} min")
    p2.metric("Break", f"{rec.break_minutes} min")
    p3.metric("Blocks", f"{rec.blocks}")
    for r in rec.reasons:
        st.markdown(f"- {r}")
    st.button(f"▶️ Use {rec.session_minutes}-min plan in Focus Mode", key="pred_apply", on_click=_apply_plan,
              args=(rec.session_minutes,), use_container_width=True)
    st.page_link("pages/4_Focus_Lab.py", label="Open Focus Lab →")


def render_smart_recommendation() -> None:
    with st.expander("🎯 Smart Recommendation — enter your inputs, get the right test & focus plan", expanded=True):
        titles = {d.key: f"{d.icon} {d.title}" for d in DOMAINS}
        key = st.selectbox("Domain", list(titles), format_func=titles.get, key="sr_domain")
        left, right = st.columns([1, 1.2], gap="large")
        tests_df = db.get_all_test_results()

        with left:
            if key == "student":
                values = _student_inputs()
            else:
                pred = get_predictor(key)
                values = {f.name: _input_widget(f, f"sr_{key}_{f.name}") for f in pred.input_features}

            run = st.button("🚀 Run Recommendation", key="sr_run", type="primary", use_container_width=True)

        with right:
            if run:
                try:
                    if key == "student":
                        from core.theme import load_predictor
                        rec = recommender.from_student(load_predictor(), values, tests_df)
                    else:
                        rec = recommender.from_domain(key, values, tests_df)
                    st.session_state["sr_last"] = {"domain": key, "values": dict(values), "rec": rec}
                except ValueError as exc:
                    st.error(str(exc))
                    return
            last = st.session_state.get("sr_last")
            if not last or last["domain"] != key:
                st.info("Enter your inputs, then click **🚀 Run Recommendation**.")
                return
            rec = last["rec"]
            if last["values"] != values:
                st.warning("Inputs changed — click **🚀 Run Recommendation** to update.")

            badge = ("🟢 Trained ML model" if rec.source == "ml_model" else "🟡 Rule-based indicator (no trained model for this domain yet)")
            st.markdown(f'<span class="src-badge">{badge}</span>', unsafe_allow_html=True)
            st.markdown(f"**{rec.headline}**")
            m1, m2, m3 = st.columns(3)
            m1.metric("Forecast score", f"{rec.score:.0f}/100")
            m2.metric("Confidence", f"{rec.confidence:.0f}%" if rec.confidence is not None else "N/A")
            m3.metric("Band", rec.band.upper())

            render_test_ranking(rec)
            st.markdown("##### ⏱️ Suggested focus plan")
            p1, p2, p3 = st.columns(3)
            p1.metric("Session", f"{rec.session_minutes} min")
            p2.metric("Break", f"{rec.break_minutes} min")
            p3.metric("Blocks", f"{rec.blocks} (≈{rec.total_focus_minutes} min)")
            for r in rec.reasons:
                st.markdown(f"- {r}")
            st.button(f"▶️ Use {rec.session_minutes}-min plan in Focus Mode", key="sr_apply", on_click=_apply_plan,
                      args=(rec.session_minutes,), use_container_width=True)
            if rec.source != "ml_model":
                st.caption("This domain's score is a transparent rule-based indicator, not an ML forecast. "
                           f"Install a trained model in models/{key}/ to switch it to ML automatically.")
