"""FutureForge — shared UI for the forecasting domains: sidebar, domain switcher, generic domain page."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import focus_lab_ui
from core import predictions_db as pdb
from services.focus_lab import recommendation_engine as fle
from services.registry import BY_KEY, DOMAINS, get_predictor

HISTORY_PAGE = "pages/18_Prediction_History.py"

_SIDEBAR_CSS = """
<style>
/* Re-enable the sidebar (the global theme hides it) and use it only for Forecasting Domains */
section[data-testid="stSidebar"] { display: block !important; width: 15rem !important; min-width: 15rem !important;
    background: var(--sidebar-bg) !important; border-right: 1px solid var(--divider); }
[data-testid="stSidebarNav"] { display: none !important; }
header[data-testid="stHeader"] { display: block !important; background: transparent !important; height: 2.4rem !important; }
header[data-testid="stHeader"] [data-testid="stToolbar"], header[data-testid="stHeader"] [data-testid="stDecoration"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: flex !important; z-index: 1100; }
.brand-text { font-size: 1.35rem !important; }
.top-nav-item, div[data-testid="stMain"] a[data-testid="stPageLink-NavLink"] p { white-space: nowrap !important; font-size: .84rem !important; }
.dom-label { font-size: .68rem; letter-spacing: .14em; font-weight: 700; color: var(--text-sub); margin: .4rem 0 .6rem .2rem; }
.dom-active { display:flex; align-items:center; gap:.5rem; padding:.55rem .8rem; margin:.15rem 0; border-radius:12px; font-weight:600;
    font-size:.92rem; color:#fff; background: linear-gradient(135deg, rgba(139,92,246,.95), rgba(59,130,246,.9));
    box-shadow: 0 8px 20px rgba(124,58,237,.30); }
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] { border-radius: 12px; padding: .5rem .8rem; transition: background .15s ease; }
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover { background: var(--card-bg-soft); }
.domain-card { min-height: 112px; }
.domain-card .dc-icon { font-size: 1.6rem; }
.domain-card .dc-title { font-weight: 700; margin-top: .25rem; }
.domain-card .dc-desc { color: var(--text-sub); font-size: .82rem; margin-top: .2rem; }
.src-badge { display:inline-block; padding:.2rem .7rem; border-radius:999px; font-size:.78rem; border:1px solid var(--card-border); background: var(--card-bg-soft); }
</style>
"""


def render_domain_sidebar(active_key: str | None = None) -> None:
    st.markdown(_SIDEBAR_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="dom-label">FORECASTING DOMAINS</div>', unsafe_allow_html=True)
        for d in DOMAINS:
            if d.key == active_key:
                st.markdown(f'<div class="dom-active">{d.icon} {d.title}</div>', unsafe_allow_html=True)
            else:
                st.page_link(d.page, label=f"{d.icon} {d.title}")
        st.markdown('<div class="dom-label" style="margin-top:1.2rem;">OVERVIEW</div>', unsafe_allow_html=True)
        st.page_link(HISTORY_PAGE, label="🕘 Prediction History")


def domain_switcher(active_key: str) -> None:
    """In-page domain menu — works even where the sidebar toggle is unavailable (small screens)."""
    with st.popover("🧭 Forecasting Domains"):
        for d in DOMAINS:
            if d.key != active_key:
                st.page_link(d.page, label=f"{d.icon} {d.title}")


# ------------------------------------------------------------------ helpers
def _fmt(v):
    return f"{v:.1f}" if isinstance(v, float) else str(v)


def _gauge(score: float, title: str) -> go.Figure:
    color = "#34d399" if score >= 75 else "#fbbf24" if score >= 55 else "#f87171"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, title={"text": title, "font": {"size": 14}},
        number={"suffix": " / 100", "font": {"size": 30, "family": "Space Grotesk"}},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": color, "thickness": 0.28}, "bgcolor": "rgba(0,0,0,0)",
               "steps": [{"range": [0, 55], "color": "rgba(248,113,113,0.15)"},
                         {"range": [55, 75], "color": "rgba(251,191,36,0.15)"},
                         {"range": [75, 100], "color": "rgba(52,211,153,0.15)"}]}))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def _trend_fig(hist: pd.DataFrame, extra_cols: dict[str, list]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["created_at"], y=hist["score"], mode="lines+markers", name="Score",
                             line=dict(color="#8b5cf6", width=3)))
    for name, ys in extra_cols.items():
        fig.add_trace(go.Scatter(x=hist["created_at"], y=ys, mode="lines+markers", name=name, line=dict(dash="dot")))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100], title="0–100"),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h"))
    return fig


def _input_widget(f, key: str):
    is_int = all(float(x).is_integer() for x in (f.lo, f.hi, f.default, f.step))
    cast = int if is_int else float
    return st.slider(f"{f.label}", cast(f.lo), cast(f.hi), cast(f.default), cast(f.step), key=key)


# ------------------------------------------------------------------ generic domain page
def render_domain_page(key: str) -> None:
    d, pred = BY_KEY[key], get_predictor(key)
    st.markdown(f'<div class="hero-title">{d.icon} {d.title}</div>', unsafe_allow_html=True)
    if pred.has_trained_model:
        st.markdown(f'<span class="src-badge">🟢 Trained model v{pred.status()["model_version"]}</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="src-badge">🟡 Model-ready · no trained model installed yet</span>', unsafe_allow_html=True)
        st.caption("Scores below are a transparent rule-based behavioural indicator (how close each input is to a healthy range) — "
                   "not a machine-learning forecast, and no confidence value is claimed. "
                   f"Install a trained model in `models/{key}/` to switch this page to ML output automatically.")
    domain_switcher(key)

    tab_forecast, tab_hist = st.tabs(["🔮 Forecast", "📈 History & Trend"])

    with tab_forecast:
        left, right = st.columns([1, 1.35], gap="large")

        # Inputs are plain widgets (no form): every change reruns the page and the forecast below updates live.
        with left:
            st.markdown("##### 🎛️ Your inputs")
            values = {f.name: _input_widget(f, f"{key}_{f.name}") for f in pred.input_features}
            run = st.button("🚀 Run Forecast", key=f"{key}_run", type="primary", use_container_width=True)

        # Prediction happens ONLY when Run Forecast is clicked; the result is kept in session so Save keeps working.
        skey, ekey = f"{key}_last", f"{key}_last_err"
        if run:
            try:
                st.session_state[skey] = {"values": dict(values), "result": pred.predict(values)}
                st.session_state.pop(f"{key}_pred_id", None)      # new run -> not saved yet
                st.session_state.pop(ekey, None)
            except ValueError as exc:
                st.session_state.pop(skey, None)
                st.session_state[ekey] = str(exc)
        last = st.session_state.get(skey)

        with right:
            r = last["result"] if last else None
            if st.session_state.get(ekey):
                st.error(st.session_state[ekey])
            elif last is None:
                st.info("Set your inputs on the left, then click **🚀 Run Forecast** to see the result.")
            elif last["values"] != values:
                st.warning("Inputs changed since the last run — click **🚀 Run Forecast** to update the result.")

            if r is not None:
                st.plotly_chart(_gauge(r.score, pred.score_name), use_container_width=True)
                m1, m2, m3 = st.columns(3)
                m1.metric("Risk Level", r.risk.upper())
                m2.metric("Confidence", f"{r.confidence:.0f}%" if r.confidence is not None else "N/A")
                m3.metric("Pattern", r.pattern)
                if r.confidence is None:
                    st.caption("Confidence is shown only when a trained model provides one.")
                if r.extras:
                    for c, (k, v) in zip(st.columns(len(r.extras)), r.extras.items()):
                        c.metric(k, _fmt(v))

                st.markdown("##### 🔍 Key Insights")
                for t in r.insights:
                    st.markdown(f"- {t}")
                st.markdown("##### ✅ Recommendations")
                for t in r.recommendations:
                    st.markdown(f"- {t}")
                with st.expander("How each input scored (0–100 closeness to a healthy range)"):
                    labels = {f.name: f.label for f in pred.features}
                    items = sorted(r.suitability.items(), key=lambda kv: kv[1])
                    fig = go.Figure(go.Bar(x=[v for _, v in items], y=[labels[k] for k, _ in items], orientation="h",
                                           marker_color="#8b5cf6"))
                    fig.update_layout(height=max(220, 34 * len(items)), margin=dict(l=10, r=10, t=10, b=10),
                                      xaxis=dict(range=[0, 100]), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                if st.button("💾 Save this forecast to history", key=f"{key}_save", use_container_width=True):
                    st.session_state[f"{key}_pred_id"] = pdb.save_prediction(key, last["values"], r)
                    st.success("✓ Saved to your history (see the History & Trend tab).")

                # Focus Lab recommendation: risk detected from THIS prediction -> recommended test (services/focus_lab)
                focus_lab_ui.render_risk_card(key, fle.analyze_result(key, last["values"], r), st.session_state.get(f"{key}_pred_id"))

    with tab_hist:
        render_domain_history(key)


# ------------------------------------------------------------------ shared views (domain page tab + top-nav History/Analytics)
def render_domain_history(key: str, allow_delete: bool = False) -> None:
    hist = pdb.domain_history(key)
    if hist.empty:
        st.info("No forecasts saved for this domain yet. Run one in the Forecast tab and press **Save**.")
        return
    trend = pdb.linear_trend(hist["score"].tolist())
    t1, t2, t3 = st.columns(3)
    t1.metric("Saved forecasts", len(hist))
    t2.metric("Average score", f"{hist['score'].mean():.1f}")
    t3.metric("Trend" if trend is None else f"Trend (last {trend['n']})",
              "Need 3+ entries" if trend is None else f"{trend['direction'].title()} ({trend['slope']:+.1f}/entry)")
    extra_series: dict[str, list] = {}
    names = {k for det in hist["details"] for k, v in det.get("extras", {}).items() if isinstance(v, (int, float))}
    for n in sorted(names):
        extra_series[n] = [det.get("extras", {}).get(n) for det in hist["details"]]
    st.plotly_chart(_trend_fig(hist, extra_series), use_container_width=True)
    view = hist.sort_values("created_at", ascending=False)[["id", "created_at", "score", "risk", "confidence", "pattern", "source"]].copy()
    view["confidence"] = view["confidence"].map(lambda c: f"{c:.0f}%" if pd.notna(c) else "—")
    view["source"] = view["source"].map({"ml_model": "ML model", "rule_based": "Rule-based"})
    view.columns = ["ID", "Date", "Score", "Risk", "Confidence", "Behavioral pattern", "Basis"]
    st.dataframe(view, use_container_width=True, hide_index=True)
    if allow_delete:
        ids = view["ID"].tolist()
        c1, c2 = st.columns([3, 1])
        pick = c1.selectbox("Delete an entry (by ID)", ids, key=f"del_pick_{key}")
        if c2.button("🗑️ Delete", key=f"del_btn_{key}", use_container_width=True):
            pdb.delete_prediction(int(pick))
            st.rerun()


_PERIOD_DAYS = {"7D": 7, "30D": 30, "90D": 90, "1Y": 365, "All": None}


def render_domain_analytics(key: str) -> None:
    pred = get_predictor(key)
    hist = pdb.domain_history(key)
    if hist.empty:
        st.info("No saved forecasts for this domain yet — analytics appear after you save your first one.")
        return
    period = st.radio("Period", list(_PERIOD_DAYS), index=4, horizontal=True, key=f"an_period_{key}")
    days = _PERIOD_DAYS[period]
    if days:
        hist = hist[hist["created_at"] >= pd.Timestamp.now() - pd.Timedelta(days=days)]
    if hist.empty:
        st.info(f"No forecasts in the last {period}.")
        return

    trend = pdb.linear_trend(hist["score"].tolist())
    m = st.columns(4)
    m[0].metric("Forecasts", len(hist))
    m[1].metric("Average", f"{hist['score'].mean():.1f}")
    m[2].metric("Best / Worst", f"{hist['score'].max():.0f} / {hist['score'].min():.0f}")
    m[3].metric("Trend", "Need 3+" if trend is None else trend["direction"].title())

    st.markdown("### 📈 Trends")
    extra_series = {}
    names = {k for det in hist["details"] for k, v in det.get("extras", {}).items() if isinstance(v, (int, float))}
    for n in sorted(names):
        extra_series[n] = [det.get("extras", {}).get(n) for det in hist["details"]]
    st.plotly_chart(_trend_fig(hist, extra_series), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Risk distribution")
        counts = hist["risk"].value_counts().reindex(["low", "medium", "high"], fill_value=0)
        fig = go.Figure(go.Bar(x=[x.title() for x in counts.index], y=counts.values,
                               marker_color=["#34d399", "#fbbf24", "#f87171"]))
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("##### Average input closeness (weakest first)")
        labels = {f.name: f.label for f in pred.features}
        suit = pd.DataFrame([d.get("suitability", {}) for d in hist["details"]]).mean().dropna().sort_values()
        fig = go.Figure(go.Bar(x=suit.values, y=[labels.get(k, k) for k in suit.index], orientation="h", marker_color="#8b5cf6"))
        fig.update_layout(height=max(260, 30 * len(suit)), margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(range=[0, 100]),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🔗 What moves your score")
    inputs = pd.DataFrame(list(hist["input_data"])).reset_index(drop=True)
    if len(hist) < 5:
        st.caption("Correlations need at least 5 saved forecasts.")
    else:
        import numpy as np
        with np.errstate(divide="ignore", invalid="ignore"):   # constant inputs have no correlation
            corr = inputs.corrwith(hist["score"].reset_index(drop=True)).dropna().sort_values()
        if corr.empty:
            st.caption("Your inputs haven't varied enough yet to show correlations.")
        else:
            labels = {f.name: f.label for f in pred.features}
            fig = go.Figure(go.Bar(x=corr.values, y=[labels.get(k, k) for k in corr.index], orientation="h", marker_color="#3b82f6"))
            fig.update_layout(height=max(240, 30 * len(corr)), margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(range=[-1, 1]),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Based on {len(hist)} of your saved forecasts. Correlation is not causation, and small samples are noisy.")


# ------------------------------------------------------------------ active-domain context
def active_domain() -> str:
    return st.session_state.get("active_domain", "student")


def set_active_domain(key: str) -> None:
    st.session_state["active_domain"] = key


def maybe_render_domain_view(view: str) -> None:
    """Called at the top of the global History / Analytics pages. If a non-Student domain is active, show THAT
    domain's history/analytics and stop; for Student the original page continues untouched."""
    key = active_domain()
    if key == "student" or key not in BY_KEY:
        return
    d = BY_KEY[key]
    title = "History" if view == "history" else "Analytics"
    st.markdown(f'<div class="hero-title">{d.icon} {d.title} — {title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-sub">Showing your saved {d.title} forecasts. Switch domain from the sidebar '
                f'to see another section.</div>', unsafe_allow_html=True)
    if view == "history":
        render_domain_history(key, allow_delete=True)
    else:
        render_domain_analytics(key)
    st.stop()


def student_only_notice() -> None:
    """Weekly Log / Achievements are built on Student Productivity data — say so when another domain is active."""
    key = active_domain()
    if key != "student" and key in BY_KEY:
        st.info(f"You're in {BY_KEY[key].icon} {BY_KEY[key].title}. This page is based on Student Productivity data.")
