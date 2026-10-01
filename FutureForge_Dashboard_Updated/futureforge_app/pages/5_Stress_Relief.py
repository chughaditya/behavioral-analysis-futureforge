import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.theme import inject_theme, render_top_nav

st.set_page_config(page_title="FutureForge | Stress Relief", page_icon="😌", layout="wide")
inject_theme()
render_top_nav("Stress Relief")

st.markdown('<div class="hero-title">😌 Stress Relief</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Interactive breathing and grounding exercises.</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["🌬️ Breathing", "📦 Box Breathing", "🖐️ Grounding (5-4-3-2-1)", "⏱️ Quick Relax"])


def breathing_widget(cycle_seconds: int, duration_seconds: int, label_in: str, label_hold: str, label_out: str, hold: bool = False):
    total_cycles = max(1, duration_seconds // cycle_seconds)
    half = cycle_seconds / 2
    hold_html = f"{cycle_seconds/3:.0f}s" if hold else ""
    components.html(
        f"""
        <div style="display:flex; flex-direction:column; align-items:center; padding:30px; font-family:Inter,sans-serif;">
            <div id="circle" style="
                width:180px; height:180px; border-radius:50%;
                background: radial-gradient(circle, rgba(139,92,246,0.55), rgba(99,102,241,0.15));
                border: 2px solid rgba(167,139,250,0.6);
                display:flex; align-items:center; justify-content:center;
                color:white; font-size:20px; font-weight:600;
                transition: transform {half}s ease-in-out;
                transform: scale(0.7);
            ">In</div>
            <p id="timer" style="color:#9ca3d4; margin-top:16px; font-size:14px;">Starting...</p>
        </div>
        <script>
        const circle = document.getElementById('circle');
        const timer = document.getElementById('timer');
        let cycles = {total_cycles};
        let phase = 0;
        function tick() {{
            if (cycles <= 0) {{
                timer.innerText = "Done — well done!";
                circle.innerText = "✓";
                return;
            }}
            if (phase === 0) {{
                circle.style.transform = "scale(1.25)";
                circle.innerText = "{label_in}";
                timer.innerText = "Breathe in...";
            }} else if (phase === 1 && {str(hold).lower()}) {{
                circle.innerText = "{label_hold}";
                timer.innerText = "Hold...";
            }} else {{
                circle.style.transform = "scale(0.7)";
                circle.innerText = "{label_out}";
                timer.innerText = "Breathe out...";
            }}
            phase = (phase + 1) % ({3 if hold else 2});
            if (phase === 0) {{ cycles -= 1; }}
            setTimeout(tick, {int(half*1000)});
        }}
        tick();
        </script>
        """,
        height=320,
    )


with tab1:
    st.markdown("#### Simple Breathing")
    dur = st.radio("Session length", ["2 minutes", "5 minutes", "10 minutes"], horizontal=True, key="simple_dur")
    seconds = {"2 minutes": 120, "5 minutes": 300, "10 minutes": 600}[dur]
    if st.button("▶️ Start Breathing Session"):
        breathing_widget(cycle_seconds=8, duration_seconds=seconds, label_in="In", label_hold="", label_out="Out", hold=False)

with tab2:
    st.markdown("#### Box Breathing — 4s inhale · 4s hold · 4s exhale · 4s hold")
    if st.button("▶️ Start Box Breathing (2 min)"):
        breathing_widget(cycle_seconds=12, duration_seconds=120, label_in="In", label_hold="Hold", label_out="Out", hold=True)

with tab3:
    st.markdown("#### 5-4-3-2-1 Grounding Technique")
    st.caption("Check each item off as you notice it.")
    items = [
        ("5 things you can see", 5),
        ("4 things you can touch", 4),
        ("3 things you can hear", 3),
        ("2 things you can smell", 2),
        ("1 thing you can taste", 1),
    ]
    total_checked = 0
    for label, count in items:
        st.markdown(f"**{label}**")
        cols = st.columns(count)
        for i in range(count):
            checked = cols[i].checkbox(" ", key=f"ground_{label}_{i}", label_visibility="collapsed")
            total_checked += int(checked)
    st.progress(total_checked / 15)
    if total_checked == 15:
        st.success("🎉 Grounding exercise complete — well done!")

with tab4:
    st.markdown("#### 60-Second Quick Relaxation")
    if st.button("▶️ Start 60s Relaxation"):
        components.html(
            """
            <div style="text-align:center; font-family:Inter,sans-serif; padding:30px;">
                <div id="msg" style="font-size:22px; color:white; margin-bottom:20px;">Relax your shoulders...</div>
                <div id="count" style="font-size:48px; color:#a78bfa; font-weight:700;">60</div>
            </div>
            <script>
            const messages = [
                "Relax your shoulders...", "Unclench your jaw...", "Soften your hands...",
                "Take a slow deep breath...", "Let your breathing settle...", "Notice the chair supporting you...",
                "Relax your forehead...", "Feel your feet on the ground...", "One more slow breath...",
                "You're doing great — almost done..."
            ];
            let t = 60;
            const countEl = document.getElementById('count');
            const msgEl = document.getElementById('msg');
            const timer = setInterval(() => {
                t -= 1;
                countEl.innerText = t;
                if (t % 6 === 0 && t > 0) {
                    msgEl.innerText = messages[Math.floor(Math.random()*messages.length)];
                }
                if (t <= 0) {
                    clearInterval(timer);
                    msgEl.innerText = "Done. Notice how you feel now.";
                    countEl.innerText = "✓";
                }
            }, 1000);
            </script>
            """,
            height=180,
        )
