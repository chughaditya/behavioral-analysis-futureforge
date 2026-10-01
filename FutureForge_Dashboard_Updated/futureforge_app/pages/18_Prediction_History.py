import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import predictions_db as pdb
from core.theme import inject_theme, render_top_nav

st.set_page_config(page_title="FutureForge | Prediction History", page_icon="🕘", layout="wide")
inject_theme()
render_top_nav("history_all")

st.markdown('<div class="hero-title">🕘 Prediction History</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Every forecast you have saved, across all domains. Only your own records are shown.</div>',
            unsafe_allow_html=True)

hist = pdb.unified_history()
if hist.empty:
    st.info("No predictions yet. Open a forecasting domain from the sidebar and run your first forecast.")
    st.stop()

domains = sorted(hist["domain_title"].unique())
picked = st.multiselect("Filter by domain", domains, default=domains)
view = hist[hist["domain_title"].isin(picked)]

c1, c2, c3 = st.columns(3)
c1.metric("Predictions", len(view))
c2.metric("Average score", f"{view['score'].mean():.1f}" if len(view) else "—")
c3.metric("High-risk entries", int((view["risk"] == "high").sum()))

table = pd.DataFrame({
    "Date": view["created_at"].dt.strftime("%Y-%m-%d %H:%M"),
    "Domain": view["domain_title"],
    "Prediction Score": view["score"].round(1),
    "Risk": view["risk"].str.title(),
    "Confidence": view["confidence"].map(lambda c: f"{c:.0f}%" if pd.notna(c) else "—"),
    "Behavioral Pattern": view["pattern"],
    "Basis": view["source"].map({"ml_model": "ML model", "rule_based": "Rule-based indicator"}),
})
st.dataframe(table, use_container_width=True, hide_index=True)
st.caption("Confidence appears only for ML-model predictions. Rule-based indicators are labelled and carry no confidence value.")
