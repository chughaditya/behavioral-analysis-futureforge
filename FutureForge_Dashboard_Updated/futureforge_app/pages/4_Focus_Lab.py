import random
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, focus_ui, recommender_ui, focus_lab_ui
from core.theme import inject_theme, render_top_nav

st.set_page_config(page_title="FutureForge | Focus Lab", page_icon="🧠", layout="wide")
inject_theme()

# Focus Mode > Distraction-Free: show only the essential focus screen (dashboard is untouched, just not rendered).
if focus_ui.is_distraction_free():
    focus_ui.render_distraction_free()
    st.stop()

render_top_nav("Focus Lab")

st.markdown('<div class="hero-title">🧠 Focus Lab</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Quick interactive tests to measure attention and reaction speed.</div>', unsafe_allow_html=True)

focus_lab_ui.render_assessments()
recommender_ui.render_smart_recommendation()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["⚡ Reaction Time", "🎨 Stroop Test", "🎯 Attention Grid", "🧩 Memory Sequence", "📊 Test History", "🎯 Focus Mode"]
)

# ---------------------------------------------------------------------------
# Reaction Time Test
# ---------------------------------------------------------------------------
with tab1:
    st.markdown("Click **Start**, wait for the box to turn green, then click **Tap!** as fast as you can.")

    if "rt_state" not in st.session_state:
        st.session_state.rt_state = "idle"  # idle -> waiting -> ready -> done

    colA, colB = st.columns([1, 2])
    with colA:
        if st.session_state.rt_state == "idle":
            if st.button("▶️ Start Test", use_container_width=True):
                st.session_state.rt_state = "waiting"
                st.session_state.rt_delay = random.uniform(1.5, 4.0)
                st.session_state.rt_start_time = time.time()
                st.rerun()

        elif st.session_state.rt_state == "waiting":
            elapsed = time.time() - st.session_state.rt_start_time
            if elapsed >= st.session_state.rt_delay:
                st.session_state.rt_state = "ready"
                st.session_state.rt_ready_time = time.time()
                st.rerun()
            else:
                st.markdown('<div class="glass-card" style="background:#3b1f1f; text-align:center;">⏳ Wait...</div>', unsafe_allow_html=True)
                if st.button("Tap! (too early)", use_container_width=True, key="early_tap"):
                    st.warning("Too early! Wait for green.")
                    st.session_state.rt_state = "idle"
                time.sleep(0.15)
                st.rerun()

        elif st.session_state.rt_state == "ready":
            st.markdown('<div class="glass-card" style="background:#14532d; text-align:center;">🟢 TAP NOW!</div>', unsafe_allow_html=True)
            if st.button("Tap!", use_container_width=True, key="real_tap"):
                reaction_ms = (time.time() - st.session_state.rt_ready_time) * 1000
                st.session_state.rt_last_result = reaction_ms
                st.session_state.rt_state = "done"
                db.insert_test_result("Reaction Time", score=max(0, 100 - reaction_ms / 5), reaction_time_ms=reaction_ms)
                st.rerun()

        elif st.session_state.rt_state == "done":
            st.success(f"⚡ Reaction time: {st.session_state.rt_last_result:.0f} ms — saved to history")
            if st.button("🔁 Try Again", use_container_width=True):
                st.session_state.rt_state = "idle"
                st.rerun()

    with colB:
        rt_history = db.get_all_test_results()
        rt_only = rt_history[rt_history["test_type"] == "Reaction Time"] if not rt_history.empty else rt_history
        if not rt_only.empty:
            best = rt_only["reaction_time_ms"].min()
            avg = rt_only["reaction_time_ms"].mean()
            m1, m2 = st.columns(2)
            m1.metric("Best", f"{best:.0f} ms")
            m2.metric("Average", f"{avg:.0f} ms")
        else:
            st.caption("No reaction time results yet.")

# ---------------------------------------------------------------------------
# Stroop Test
# ---------------------------------------------------------------------------
with tab2:
    st.markdown("Select the **display color** of the word — not the word itself.")

    COLORS = {"RED": "#f87171", "GREEN": "#34d399", "BLUE": "#60a5fa", "YELLOW": "#fbbf24"}

    if "stroop_round" not in st.session_state:
        st.session_state.stroop_round = 0
        st.session_state.stroop_correct = 0
        st.session_state.stroop_total = 0
        st.session_state.stroop_word = None
        st.session_state.stroop_color = None
        st.session_state.stroop_times = []

    def new_stroop_round():
        word = random.choice(list(COLORS.keys()))
        color = random.choice([c for c in COLORS.keys() if c != word] + [word])
        st.session_state.stroop_word = word
        st.session_state.stroop_color = color
        st.session_state.stroop_shown_at = time.time()

    scol1, scol2 = st.columns([1, 1])
    with scol1:
        if st.session_state.stroop_word is None:
            if st.button("▶️ Start Stroop Test (10 rounds)"):
                st.session_state.stroop_round = 1
                st.session_state.stroop_correct = 0
                st.session_state.stroop_total = 0
                st.session_state.stroop_times = []
                new_stroop_round()
                st.rerun()
        elif st.session_state.stroop_round <= 10:
            st.markdown(
                f'<div style="font-size:3rem; font-weight:800; text-align:center; color:{COLORS[st.session_state.stroop_color]};">'
                f"{st.session_state.stroop_word}</div>",
                unsafe_allow_html=True,
            )
            st.caption(f"Round {st.session_state.stroop_round}/10")
            btn_cols = st.columns(4)
            for i, c in enumerate(COLORS.keys()):
                if btn_cols[i].button(c, key=f"stroop_{c}_{st.session_state.stroop_round}"):
                    correct = c == st.session_state.stroop_color
                    st.session_state.stroop_total += 1
                    if correct:
                        st.session_state.stroop_correct += 1
                    st.session_state.stroop_times.append((time.time() - st.session_state.stroop_shown_at) * 1000)
                    st.session_state.stroop_round += 1
                    if st.session_state.stroop_round <= 10:
                        new_stroop_round()
                    st.rerun()
        else:
            accuracy = (st.session_state.stroop_correct / max(1, st.session_state.stroop_total)) * 100
            avg_rt = sum(st.session_state.stroop_times) / max(1, len(st.session_state.stroop_times))
            st.success(f"Done! Accuracy: {accuracy:.0f}% · Avg reaction: {avg_rt:.0f} ms — saved to history")
            db.insert_test_result("Stroop Test", score=accuracy, accuracy=accuracy, reaction_time_ms=avg_rt)
            if st.button("🔁 Try Again", key="stroop_retry"):
                st.session_state.stroop_word = None
                st.session_state.stroop_round = 0
                st.rerun()

    with scol2:
        stroop_history = db.get_all_test_results()
        stroop_only = stroop_history[stroop_history["test_type"] == "Stroop Test"] if not stroop_history.empty else stroop_history
        if not stroop_only.empty:
            m1, m2 = st.columns(2)
            m1.metric("Best Accuracy", f"{stroop_only['accuracy'].max():.0f}%")
            m2.metric("Avg Reaction", f"{stroop_only['reaction_time_ms'].mean():.0f} ms")
        else:
            st.caption("No Stroop test results yet.")

# ---------------------------------------------------------------------------
# Attention Grid — sustained-attention / vigilance test
# ---------------------------------------------------------------------------
with tab3:
    st.markdown(
        "A cell will light up **green** somewhere in the grid — click it as fast as you can. "
        "Miss it or click the wrong cell and it counts against your accuracy. 10 rounds."
    )

    AG_SIZE = 4  # 4x4 grid
    AG_ROUNDS = 10
    AG_TIMEOUT_S = 2.2

    if "ag_state" not in st.session_state:
        st.session_state.ag_state = "idle"  # idle -> waiting -> active -> round_end -> done

    def _ag_new_round():
        st.session_state.ag_target = random.randint(0, AG_SIZE * AG_SIZE - 1)
        st.session_state.ag_delay = random.uniform(0.6, 1.8)
        st.session_state.ag_wait_start = time.time()
        st.session_state.ag_state = "waiting"
        st.session_state.ag_last_feedback = None

    agcol1, agcol2 = st.columns([2, 1])
    with agcol1:
        if st.session_state.ag_state == "idle":
            if st.button("▶️ Start Attention Grid", use_container_width=True, key="ag_start"):
                st.session_state.ag_round = 1
                st.session_state.ag_hits = 0
                st.session_state.ag_total = 0
                st.session_state.ag_times = []
                _ag_new_round()
                st.rerun()

        elif st.session_state.ag_state in ("waiting", "active"):
            st.caption(f"Round {st.session_state.ag_round}/{AG_ROUNDS}")

            if st.session_state.ag_state == "waiting":
                elapsed = time.time() - st.session_state.ag_wait_start
                if elapsed >= st.session_state.ag_delay:
                    st.session_state.ag_state = "active"
                    st.session_state.ag_active_since = time.time()
                    st.rerun()

            active = st.session_state.ag_state == "active"
            if active:
                elapsed_active = time.time() - st.session_state.ag_active_since
                if elapsed_active >= AG_TIMEOUT_S:
                    st.session_state.ag_total += 1
                    st.session_state.ag_last_feedback = "⏱️ Too slow — missed it!"
                    st.session_state.ag_round += 1
                    if st.session_state.ag_round > AG_ROUNDS:
                        st.session_state.ag_state = "done"
                    else:
                        _ag_new_round()
                    st.rerun()

            for row_i in range(AG_SIZE):
                cols = st.columns(AG_SIZE)
                for col_i in range(AG_SIZE):
                    idx = row_i * AG_SIZE + col_i
                    is_target = active and idx == st.session_state.ag_target
                    cell_label = "🟢" if is_target else "⬛"
                    if cols[col_i].button(
                        cell_label, key=f"ag_cell_{st.session_state.ag_round}_{idx}", use_container_width=True
                    ):
                        if not active:
                            st.session_state.ag_last_feedback = "🙈 Too early — wait for green!"
                        else:
                            rt = (time.time() - st.session_state.ag_active_since) * 1000
                            st.session_state.ag_total += 1
                            if idx == st.session_state.ag_target:
                                st.session_state.ag_hits += 1
                                st.session_state.ag_times.append(rt)
                                st.session_state.ag_last_feedback = f"✅ Hit! {rt:.0f} ms"
                            else:
                                st.session_state.ag_last_feedback = "❌ Wrong cell"
                            st.session_state.ag_round += 1
                            if st.session_state.ag_round > AG_ROUNDS:
                                st.session_state.ag_state = "done"
                            else:
                                _ag_new_round()
                        st.rerun()

            if st.session_state.ag_last_feedback:
                st.caption(st.session_state.ag_last_feedback)

            if st.session_state.ag_state in ("waiting", "active"):
                time.sleep(0.08)
                st.rerun()

        elif st.session_state.ag_state == "done":
            accuracy = (st.session_state.ag_hits / max(1, st.session_state.ag_total)) * 100
            avg_rt = sum(st.session_state.ag_times) / max(1, len(st.session_state.ag_times)) if st.session_state.ag_times else 0
            st.success(f"Done! Accuracy: {accuracy:.0f}% · Avg reaction: {avg_rt:.0f} ms — saved to history")
            db.insert_test_result("Attention Grid", score=accuracy, accuracy=accuracy, reaction_time_ms=avg_rt or None)
            if st.button("🔁 Try Again", key="ag_retry", use_container_width=True):
                st.session_state.ag_state = "idle"
                st.rerun()

    with agcol2:
        ag_history = db.get_all_test_results()
        ag_only = ag_history[ag_history["test_type"] == "Attention Grid"] if not ag_history.empty else ag_history
        if not ag_only.empty:
            m1, m2 = st.columns(2)
            m1.metric("Best Accuracy", f"{ag_only['accuracy'].max():.0f}%")
            m2.metric("Avg Reaction", f"{ag_only['reaction_time_ms'].mean():.0f} ms")
        else:
            st.caption("No Attention Grid results yet.")

# ---------------------------------------------------------------------------
# Memory Sequence — Simon-style working memory test
# ---------------------------------------------------------------------------
with tab4:
    st.markdown(
        "Watch the sequence of highlighted tiles, then repeat it back **in the same order**. "
        "Each round the sequence gets one tile longer — how far can you go?"
    )

    MS_SIZE = 3  # 3x3 grid
    MS_SHOW_MS = 620
    MS_GAP_MS = 260
    MS_MAX_LEVEL = 12

    if "ms_state" not in st.session_state:
        st.session_state.ms_state = "idle"  # idle -> showing -> input -> done

    def _ms_start_level(level: int):
        length = level + 2
        st.session_state.ms_level = level
        st.session_state.ms_sequence = [random.randint(0, MS_SIZE * MS_SIZE - 1) for _ in range(length)]
        st.session_state.ms_show_index = 0
        st.session_state.ms_show_phase = "on"  # on -> off, alternating per step
        st.session_state.ms_step_started = time.time()
        st.session_state.ms_state = "showing"
        st.session_state.ms_input = []
        st.session_state.ms_feedback = None

    mscol1, mscol2 = st.columns([2, 1])
    with mscol1:
        if st.session_state.ms_state == "idle":
            if st.button("▶️ Start Memory Sequence", use_container_width=True, key="ms_start"):
                st.session_state.ms_started_at = time.time()
                _ms_start_level(1)
                st.rerun()

        elif st.session_state.ms_state == "showing":
            st.caption(f"Level {st.session_state.ms_level} · watch closely...")
            seq = st.session_state.ms_sequence
            show_idx = st.session_state.ms_show_index
            phase = st.session_state.ms_show_phase
            elapsed_ms = (time.time() - st.session_state.ms_step_started) * 1000
            duration = MS_SHOW_MS if phase == "on" else MS_GAP_MS

            if elapsed_ms >= duration:
                if phase == "on":
                    st.session_state.ms_show_phase = "off"
                else:
                    st.session_state.ms_show_index += 1
                    st.session_state.ms_show_phase = "on"
                st.session_state.ms_step_started = time.time()
                if st.session_state.ms_show_index >= len(seq):
                    st.session_state.ms_state = "input"
                st.rerun()

            active_idx = seq[show_idx] if phase == "on" and show_idx < len(seq) else -1
            for row_i in range(MS_SIZE):
                cols = st.columns(MS_SIZE)
                for col_i in range(MS_SIZE):
                    idx = row_i * MS_SIZE + col_i
                    label = "🟣" if idx == active_idx else "⬜"
                    cols[col_i].button(label, key=f"ms_show_{st.session_state.ms_level}_{idx}", disabled=True, use_container_width=True)

            time.sleep(0.05)
            st.rerun()

        elif st.session_state.ms_state == "input":
            seq = st.session_state.ms_sequence
            progress = len(st.session_state.ms_input)
            st.caption(f"Level {st.session_state.ms_level} · your turn — tile {progress + 1}/{len(seq)}")

            for row_i in range(MS_SIZE):
                cols = st.columns(MS_SIZE)
                for col_i in range(MS_SIZE):
                    idx = row_i * MS_SIZE + col_i
                    if cols[col_i].button("⬜", key=f"ms_in_{st.session_state.ms_level}_{progress}_{idx}", use_container_width=True):
                        st.session_state.ms_input.append(idx)
                        pos = len(st.session_state.ms_input) - 1
                        if idx != seq[pos]:
                            total_time = time.time() - st.session_state.ms_started_at
                            level_reached = st.session_state.ms_level
                            score = min(100, (level_reached - 1) / MS_MAX_LEVEL * 100 + 8)
                            st.session_state.ms_result = {
                                "level": level_reached, "score": score, "duration": total_time,
                            }
                            db.insert_test_result("Memory Sequence", score=score, duration_s=total_time)
                            st.session_state.ms_state = "done"
                        elif len(st.session_state.ms_input) == len(seq):
                            if st.session_state.ms_level >= MS_MAX_LEVEL:
                                total_time = time.time() - st.session_state.ms_started_at
                                score = 100.0
                                st.session_state.ms_result = {
                                    "level": MS_MAX_LEVEL, "score": score, "duration": total_time,
                                }
                                db.insert_test_result("Memory Sequence", score=score, duration_s=total_time)
                                st.session_state.ms_state = "done"
                            else:
                                _ms_start_level(st.session_state.ms_level + 1)
                        st.rerun()

        elif st.session_state.ms_state == "done":
            res = st.session_state.ms_result
            st.success(
                f"Reached level {res['level']} (sequence length {res['level'] + 1}) — "
                f"score {res['score']:.0f}/100 — saved to history"
            )
            if st.button("🔁 Try Again", key="ms_retry", use_container_width=True):
                st.session_state.ms_state = "idle"
                st.rerun()

    with mscol2:
        ms_history = db.get_all_test_results()
        ms_only = ms_history[ms_history["test_type"] == "Memory Sequence"] if not ms_history.empty else ms_history
        if not ms_only.empty:
            m1, m2 = st.columns(2)
            m1.metric("Best Score", f"{ms_only['score'].max():.0f}")
            m2.metric("Attempts", f"{len(ms_only)}")
        else:
            st.caption("No Memory Sequence results yet.")

# ---------------------------------------------------------------------------
# Test History
# ---------------------------------------------------------------------------
with tab5:
    tests_df = db.get_all_test_results()
    if tests_df.empty:
        st.info("No test results yet. Try the Reaction Time or Stroop test above.")
    else:
        view = tests_df.copy()
        view["date"] = view["date"].dt.strftime("%b %d")
        view = view[["date", "test_type", "score", "accuracy", "reaction_time_ms", "duration_s"]].rename(
            columns={
                "date": "Date", "test_type": "Test", "score": "Score", "accuracy": "Accuracy %",
                "reaction_time_ms": "Reaction Time (ms)", "duration_s": "Duration (s)",
            }
        )
        st.dataframe(view, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Focus Mode (sessions, timer, daily target, streak, score, history)
# ---------------------------------------------------------------------------
with tab6:
    focus_ui.render_focus_mode()
