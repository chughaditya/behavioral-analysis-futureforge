"""
Focus Lab recommendations UI.

  render_risk_card(...)       under every prediction: risk detected -> recommended test -> [Go to Focus Lab →]
  render_assessments()        inside the Focus Lab page: takes the recommended test automatically, scores it, saves it,
                              shows observations/actions and the user's progress.
All decisions live in services/focus_lab/* (no rules in the UI). Self-assessment only — not a diagnosis.
"""
from __future__ import annotations

from html import escape as _e

import streamlit as st

from core import focus_lab_db as fdb
from services.focus_lab import test_engine as te
from services.focus_lab.recommendation_engine import Recommendation
from services.focus_lab.tests_bank import OPTIONS
from services.registry import BY_KEY

FOCUS_LAB_PAGE = "pages/4_Focus_Lab.py"
DISCLAIMER = "Focus Lab results are self-assessments for behavioral and productivity insight — not a medical or psychological assessment."
_CSS = """
<style>
.fl-card { border:1px solid var(--card-border); border-left:5px solid #8b5cf6; border-radius:16px; padding:16px 18px; margin:.6rem 0 .4rem;
    background: linear-gradient(135deg, rgba(139,92,246,.10), rgba(59,130,246,.07)); }
.fl-card.ok { border-left-color:#34d399; background: linear-gradient(135deg, rgba(52,211,153,.10), rgba(59,130,246,.05)); }
.fl-title { font-weight:800; font-size:1.05rem; margin-bottom:.35rem; }
.fl-k { color: var(--text-sub); font-size:.74rem; letter-spacing:.08em; text-transform:uppercase; margin-top:.55rem; }
.fl-v { font-weight:700; font-size:1rem; }
</style>
"""


def _clear_answers(test_id: str | None = None) -> None:
    for k in [k for k in list(st.session_state.keys()) if isinstance(k, str) and k.startswith("fl_q_") and (test_id is None or k.startswith(f"fl_q_{test_id}_"))]:
        del st.session_state[k]


# ------------------------------------------------------------------ card under a prediction
def render_risk_card(domain: str, rec: Recommendation, prediction_id: int | None = None) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    if not rec.has_risk:
        st.markdown('<div class="fl-card ok"><div class="fl-title">✅ Your current behavioral pattern looks stable.</div>'
                    'You can still visit Focus Lab for a self-assessment.</div>', unsafe_allow_html=True)
        if st.button("Explore Focus Lab →", key=f"fl_explore_{domain}", use_container_width=True):
            st.switch_page(FOCUS_LAB_PAGE)
        return

    p = rec.primary
    test = te.get_test(p.test_id)
    st.markdown(
        f'<div class="fl-card"><div class="fl-title">⚠️ Recommended Action</div>{_e(rec.headline)}'
        f'<div class="fl-k">Risk area</div><div class="fl-v">{_e(p.label)}</div>'
        f'<div class="fl-k">Why</div>{_e(p.why)}'
        f'<div class="fl-k">Recommended test</div><div class="fl-v">{test["icon"]} {_e(test["title"])}</div>'
        f'{_e(test["description"])}</div>', unsafe_allow_html=True)
    if rec.others:
        st.caption("Also relevant in Focus Lab: " + ", ".join(f"{te.get_test(o.test_id)['icon']} {te.title_of(o.test_id)}" for o in rec.others))
    st.caption(DISCLAIMER)
    if st.button("Go to Focus Lab →", key=f"fl_go_{domain}", type="primary", use_container_width=True):
        rid = fdb.create_recommendation(domain, prediction_id, p.label, rec.risk_level, p.test_id)
        _clear_answers()
        st.session_state.pop("fl_result", None)
        st.session_state["fl_active"] = {"test_id": p.test_id, "recommendation_id": rid, "domain": domain,
                                         "prediction_id": prediction_id, "risk_type": p.label}
        st.switch_page(FOCUS_LAB_PAGE)


# ------------------------------------------------------------------ Focus Lab page section
def _result_view(res: dict) -> None:
    ctx = st.session_state.get("fl_active") or {}
    st.markdown(f"#### {res['icon']} {res['title']} — result")
    c1, c2 = st.columns(2)
    c1.metric("Score", f"{res['score']}/100")
    c2.metric("Category", res["category"])
    st.progress(res["score"] / 100)
    if ctx.get("risk_type") and ctx.get("test_id") == res["test_id"]:
        st.caption(f"Suggested because of: {ctx['risk_type']} in your {BY_KEY[ctx['domain']].title} forecast.")
    st.markdown("**Key observations**")
    for o in res["observations"]:
        st.markdown(f"- {o}")
    st.markdown("**Recommended actions**")
    for a in res["actions"]:
        st.markdown(f"- {a}")
    st.caption(DISCLAIMER)
    b1, b2, b3 = st.columns(3)
    if b1.button("🏠 Back to Dashboard", key="fl_back", use_container_width=True):
        st.switch_page("app.py")
    dom = ctx.get("domain") or "student"
    if b2.button("🔮 View Prediction", key="fl_view_pred", use_container_width=True):
        st.switch_page(BY_KEY[dom].page)
    if b3.button("🧪 Explore More Tests", key="fl_more", use_container_width=True):
        st.session_state.pop("fl_result", None); st.session_state.pop("fl_active", None); _clear_answers()
        st.rerun()


def _test_form(active: dict | None) -> None:
    tests = te.list_tests()
    ids = [t["id"] for t in tests]
    fmt = {t["id"]: f"{t['icon']} {t['title']}" for t in tests}
    token = active["recommendation_id"] if active else "free"
    default = ids.index(active["test_id"]) if active and active["test_id"] in ids else 0
    tid = st.selectbox("Choose a test", ids, index=default, format_func=fmt.get, key=f"fl_pick_{token}")
    test = te.get_test(tid)
    is_rec = bool(active) and active["test_id"] == tid
    if is_rec:
        st.info(f"⭐ Recommended for you — {active['risk_type']} in your {BY_KEY[active['domain']].title} forecast.")
    st.caption(f"{test['description']}  ·  {len(test['questions'])} questions")

    answers = []
    for i, (text, _rev) in enumerate(test["questions"]):
        pick = st.radio(f"{i + 1}. {text}", OPTIONS, index=None, horizontal=True, key=f"fl_q_{tid}_{i}")
        answers.append(OPTIONS.index(pick) if pick is not None else None)
    done = sum(a is not None for a in answers)
    st.progress(done / len(answers), text=f"{done}/{len(answers)} answered")

    if st.button("Submit test", key="fl_submit", type="primary", use_container_width=True):
        try:
            res = te.submit(tid, answers)
        except ValueError as exc:
            st.error(str(exc))
            return
        fdb.save_result(res, domain=active["domain"] if is_rec else None, prediction_id=active.get("prediction_id") if is_rec else None,
                        recommendation_id=active["recommendation_id"] if is_rec else None)
        st.session_state["fl_result"] = res
        _clear_answers(tid)
        st.rerun()


def _progress_view() -> None:
    res = fdb.list_results()
    if res.empty:
        st.caption("No Focus Lab assessments completed yet.")
        return
    view = res.assign(Test=res["test_id"].map(lambda t: te.title_of(t) if t in te.TESTS_IDS else t))
    st.dataframe(view[["created_at", "Test", "score", "category", "domain"]].rename(
        columns={"created_at": "When", "score": "Score", "category": "Category", "domain": "Domain"}), use_container_width=True, hide_index=True)
    for tid, g in res.groupby("test_id"):
        if len(g) >= 2 and tid in te.TESTS_IDS:
            first, last = g.iloc[-1]["score"], g.iloc[0]["score"]
            st.caption(f"{te.title_of(tid)}: {first:.0f} → {last:.0f} ({last - first:+.0f}) across {len(g)} attempts.")
    recs = fdb.list_recommendations()
    if not recs.empty:
        st.markdown("**Recommended by your forecasts**")
        st.dataframe(recs.assign(Test=recs["recommended_test"].map(lambda t: te.title_of(t) if t in te.TESTS_IDS else t))[
            ["created_at", "domain", "risk_type", "Test", "test_status", "test_score"]].rename(
            columns={"created_at": "When", "domain": "Domain", "risk_type": "Risk area", "test_status": "Status", "test_score": "Score"}),
            use_container_width=True, hide_index=True)


def render_assessments() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    active, result = st.session_state.get("fl_active"), st.session_state.get("fl_result")
    with st.expander("📝 Self-Assessments & Recommendations", expanded=bool(active or result)):
        if result:
            _result_view(result)
        else:
            _test_form(active)
        st.markdown("---")
        st.markdown("##### 📈 Your Focus Lab progress")
        _progress_view()
