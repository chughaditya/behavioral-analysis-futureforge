import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import auth, auth_ui, predictions_db as pdb
from core.theme import inject_theme, render_top_nav

st.set_page_config(page_title="FutureForge | Profile", page_icon="👤", layout="wide")
inject_theme()
render_top_nav("profile")
user = auth_ui.current_user()

st.markdown('<div class="hero-title">👤 Profile & Account</div>', unsafe_allow_html=True)
stats = pdb.overview_stats()
member = str(user.get("created_at", ""))[:10] or "—"

st.markdown(
    f'<div class="glass-card"><b style="font-size:1.25rem;">{user["name"]}</b><br>{user["email"]}<br>'
    f'<span style="color:var(--text-sub)">Member since {member} · {stats["total"]} saved predictions · 🟢 Online</span></div>',
    unsafe_allow_html=True,
)

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### Display name")
    with st.form("name_form"):
        new_name = st.text_input("Full name", value=user["name"])
        if st.form_submit_button("Save name", use_container_width=True):
            err = auth.update_name(user["id"], new_name)
            if err:
                st.error(err)
            else:
                st.success("Name updated.")
                st.rerun()
with c2:
    st.markdown("#### Change password")
    with st.form("pw_form"):
        cur = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password", help="At least 8 characters, with a letter and a number.")
        conf = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Change password", use_container_width=True):
            err = auth.change_password(user["id"], cur, new, conf)
            st.error(err) if err else st.success("Password changed.")

st.markdown("---")
if st.button("🚪 Log out", use_container_width=False):
    auth_ui.logout()
    st.rerun()
