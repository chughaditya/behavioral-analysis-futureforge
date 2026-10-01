"""FutureForge — Streamlit glue for authentication: login/signup screen, page guard, logout."""

from __future__ import annotations

import streamlit as st

from core import auth, db


def _session_user_id():
    user = st.session_state.get("auth_user")
    return user["id"] if user else None


# Every DB query on user-owned tables is scoped through this resolver (fails closed when None).
db.set_user_resolver(_session_user_id)


def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def _sign_in(user: dict) -> None:
    st.session_state.auth_token = auth.create_session(user["id"])
    st.session_state.auth_user = user
    st.session_state.user_name = user["name"]
    st.rerun()


def logout() -> None:
    """Revoke the server-side session and wipe ALL per-user state held in this browser session."""
    auth.revoke_session(st.session_state.get("auth_token"))
    theme = st.session_state.get("theme")
    st.session_state.clear()
    if theme:
        st.session_state.theme = theme


def render_auth_page() -> None:
    st.markdown(
        '<div style="text-align:center; margin:6vh 0 1.2rem;">'
        '<span class="brand-mark" style="width:44px;height:44px;font-size:1.2rem;border-radius:14px;">F</span>'
        '<div class="brand-text" style="font-size:2.3rem; margin-top:.5rem;">FutureForge</div>'
        '<div style="color:var(--text-sub); margin-top:.3rem;">Behavioral forecasting platform — sign in to continue</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        login_tab, signup_tab = st.tabs(["🔐 Log in", "✨ Sign up"])

        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Log in", use_container_width=True)
            if submitted:
                user, err = auth.authenticate(email, password)
                if err:
                    st.error(err)
                else:
                    _sign_in(user)

        with signup_tab:
            with st.form("signup_form"):
                name = st.text_input("Full name", key="signup_name")
                s_email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
                s_pw = st.text_input("Password", type="password", key="signup_pw",
                                     help="At least 8 characters, with a letter and a number.")
                s_pw2 = st.text_input("Confirm password", type="password", key="signup_pw2")
                created = st.form_submit_button("Create account", use_container_width=True)
            if created:
                user, err = auth.register_user(name, s_email, s_pw, s_pw2)
                if err:
                    st.error(err)
                else:
                    _sign_in(user)


def require_login() -> dict:
    """Guard for every protected page. Unauthenticated / expired / revoked => login screen and st.stop()."""
    token = st.session_state.get("auth_token")
    user = auth.validate_session(token)
    if user is None:
        for k in ("auth_token", "auth_user", "user_name", "last_prediction"):
            st.session_state.pop(k, None)
        render_auth_page()
        st.stop()
    st.session_state.auth_user = user
    st.session_state.user_name = user["name"]
    return user
