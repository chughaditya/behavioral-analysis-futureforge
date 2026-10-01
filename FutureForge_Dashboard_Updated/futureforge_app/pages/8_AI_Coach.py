import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, ai_coach
from core.theme import inject_theme, render_top_nav

st.set_page_config(page_title="FutureForge | AI Coach", page_icon="🤖", layout="wide")
inject_theme()
render_top_nav("AI Coach")

st.markdown('<div class="hero-title">🤖 AI Coach</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">A real, conversational coach grounded in your own saved history — '
    "not a fixed Q&A lookup.</div>",
    unsafe_allow_html=True,
)

api_key = st.session_state.get("anthropic_api_key", "")
if api_key:
    st.markdown('<span class="coach-mode-badge coach-mode-generative">✨ Generative mode — live Claude API</span>', unsafe_allow_html=True)
else:
    st.markdown(
        '<span class="coach-mode-badge coach-mode-local">💡 Local smart-assist mode</span> '
        '<span style="font-size:0.8rem; color:var(--text-sub);">Add an Anthropic API key in Settings for fully open-ended conversation.</span>',
        unsafe_allow_html=True,
    )

reports_df = db.get_all_reports()
tests_df = db.get_all_test_results()

if "coach_messages" not in st.session_state:
    st.session_state.coach_messages = [
        {
            "role": "assistant",
            "content": (
                f"Hey{', ' + st.session_state.get('user_name', '') if st.session_state.get('user_name') else ''}! "
                "I'm your FutureForge AI Coach. Ask me about your focus trends, what's driving your stress, "
                "how your sleep is tracking, or how to improve — I'll answer using your real saved data."
            ),
        }
    ]

for msg in st.session_state.coach_messages:
    with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else None):
        st.markdown(msg["content"])

suggestion_cols = st.columns(4)
suggestions = [
    "What's my best day?",
    "How's my stress trending?",
    "What improves my focus?",
    "How's my sleep?",
]
clicked_suggestion = None
for i, s in enumerate(suggestions):
    if suggestion_cols[i].button(s, use_container_width=True, key=f"coach_sugg_{i}"):
        clicked_suggestion = s

user_input = st.chat_input("Ask your AI Coach anything about your data or productivity...")
final_input = clicked_suggestion or user_input

if final_input:
    st.session_state.coach_messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"):
        st.markdown(final_input)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            reply, mode = ai_coach.get_coach_reply(
                st.session_state.coach_messages,
                reports_df,
                tests_df,
                user_name=st.session_state.get("user_name", ""),
                api_key=api_key or None,
            )
        st.markdown(reply)

    st.session_state.coach_messages.append({"role": "assistant", "content": reply})
    st.rerun()

if len(st.session_state.coach_messages) > 1:
    if st.button("🗑️ Clear conversation"):
        st.session_state.coach_messages = st.session_state.coach_messages[:1]
        st.rerun()
