import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db
from core.theme import inject_theme, render_top_nav

st.set_page_config(page_title="FutureForge | Settings", page_icon="⚙️", layout="wide")
inject_theme()
render_top_nav("Settings")

st.markdown('<div class="hero-title">⚙️ Settings</div>', unsafe_allow_html=True)

st.markdown("### 👤 Profile")
st.caption("Your name and password are managed on your account profile.")
st.page_link("pages/19_Profile.py", label="👤 Open Profile & account")

st.markdown("---")
st.markdown("### 🤖 AI Coach")
st.caption(
    "Paste an Anthropic API key to switch the AI Coach into fully generative, open-ended conversation mode. "
    "The key is kept only in this browser session's memory — it is never written to disk or the database."
)
key_input = st.text_input(
    "Anthropic API key", value=st.session_state.get("anthropic_api_key", ""), type="password",
    placeholder="sk-ant-...",
)
kc1, kc2 = st.columns(2)
if kc1.button("Save key for this session", use_container_width=True):
    st.session_state.anthropic_api_key = key_input.strip()
    st.success("Saved for this session. The AI Coach will now use the live Claude API.")
if kc2.button("Clear key", use_container_width=True):
    st.session_state.anthropic_api_key = ""
    st.success("Cleared. AI Coach will use local smart-assist mode.")

st.markdown("---")
st.markdown("### 💾 Data Management")

reports_df = db.get_all_reports()
tests_df = db.get_all_test_results()

c1, c2 = st.columns(2)

with c1:
    st.markdown("#### Export All Data")
    export_payload = {
        "reports": json.loads(reports_df.to_json(orient="records", date_format="iso")) if not reports_df.empty else [],
        "test_results": json.loads(tests_df.to_json(orient="records", date_format="iso")) if not tests_df.empty else [],
    }
    st.download_button(
        "⬇️ Export All Data (JSON)",
        json.dumps(export_payload, indent=2).encode("utf-8"),
        "futureforge_export.json",
        "application/json",
        use_container_width=True,
    )
    if not reports_df.empty:
        st.download_button(
            "⬇️ Export Reports (CSV)",
            reports_df.drop(columns=["feedback"], errors="ignore").to_csv(index=False).encode("utf-8"),
            "futureforge_reports.csv",
            "text/csv",
            use_container_width=True,
        )

with c2:
    st.markdown("#### Danger Zone")
    st.warning("Clearing history permanently deletes all saved reports and test results.")
    confirm = st.checkbox("I understand this cannot be undone")
    if st.button("🗑️ Clear All History", disabled=not confirm, use_container_width=True):
        db.clear_all_reports()
        db.clear_all_tests()
        st.success("All history cleared.")
        st.rerun()

st.markdown("---")
st.markdown("### 📊 Storage Stats")
s1, s2 = st.columns(2)
s1.metric("Saved Daily Reports", len(reports_df))
s2.metric("Saved Test Results", len(tests_df))

st.markdown("---")
st.caption(
    "FutureForge stores your data locally in a SQLite database "
    "(backend/data/futureforge.db) inside this project folder. Nothing is sent externally."
)
