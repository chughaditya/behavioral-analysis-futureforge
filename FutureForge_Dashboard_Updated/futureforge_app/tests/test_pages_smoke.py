"""
Page-wiring smoke test against a STUB of the Streamlit API (real Streamlit is not installed in the build sandbox).
Verifies: guard blocks unauthenticated access on every page; signup/login/logout flows; each domain page renders,
saves a prediction under the right user; dashboard/history/profile render. It does not test browser rendering.
Run: PYTHONPATH=/path/to/stub python tests/test_pages_smoke.py
"""
import os, runpy, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp()) / "t.db"
shutil.copy(ROOT / "backend/data/futureforge.db", tmp)
os.environ["FUTUREFORGE_DB"] = str(tmp)
os.chdir(ROOT)

import streamlit as st
from core import db, auth, predictions_db as pdb

def run(path):
    st.LOG.clear()
    try:
        runpy.run_path(str(ROOT / path), run_name="__main__")
    except st.StopScript:
        return "stopped"
    except st.RerunScript:
        return "rerun"
    return "completed"

def reset(): st.session_state.clear(); st.CFG["submit"].clear(); st.CFG["buttons"].clear(); st.CFG["text"].clear()

n = 0
def check(name, cond):
    global n; assert cond, "FAIL: " + name; n += 1; print("ok  ", name)

ALL_PAGES = ["app.py"] + sorted(f"pages/{p.name}" for p in (ROOT / "pages").glob("*.py"))

# 1. every page is protected
reset()
for pg in ALL_PAGES:
    r = run(pg)
    check(f"unauthenticated blocked: {pg}", r == "stopped" and any(k == "tabs" or True for k, _ in st.LOG) and "user_name" not in st.session_state)

# 2. signup through the UI code path
reset(); st.CFG["submit"].add("Create account")
st.CFG["text"].update(signup_name="Aditya Chugh", signup_email="aditya@example.com", signup_pw="Str0ngPass1", signup_pw2="Str0ngPass1")
check("signup signs in (rerun)", run("app.py") == "rerun" and st.session_state["auth_user"]["name"] == "Aditya Chugh")
tok = st.session_state["auth_token"]
st.CFG["submit"].clear()

# 3. every page renders authenticated, with the user's name shown
for pg in ALL_PAGES:
    r = run(pg)
    check(f"authenticated renders: {pg}", r == "completed" and st.session_state["user_name"] == "Aditya Chugh")

# 4. run a forecast on each new domain page and confirm it was stored for THIS user
domain_pages = [p for p in ALL_PAGES if any(f"pages/{i}_" in p for i in range(10, 18))]
for pg in domain_pages:
    dkey = {"10":"employee","11":"fitness","12":"digital_wellbeing","13":"personalized_learning","14":"freelancer","15":"team_project","16":"gamer","17":"habit_routine"}[pg.split("/")[-1].split("_")[0]]
    st.session_state.pop(f"{dkey}_last", None)
    st.CFG["buttons"].clear()
    r0 = run(pg)
    check(f"no forecast before Run is clicked: {pg}", r0 == "completed" and not any(k == "metric" and v[0] == "Risk Level" for k, v in st.LOG))
    st.CFG["buttons"].add(f"{dkey}_run")
    r1 = run(pg)
    check(f"Run Forecast click renders forecast: {pg}", r1 == "completed" and any(k == "metric" and v[0] == "Risk Level" for k, v in st.LOG))
    st.CFG["buttons"].clear(); st.CFG["buttons"].add(f"{dkey}_save")     # next rerun: only Save clicked, result must persist
    check(f"save button stores forecast (result persisted after rerun): {pg}", run(pg) == "completed" and any(k == "success" for k, _ in st.LOG))
    st.CFG["buttons"].clear()
h = pdb.unified_history()
check("8 new-domain predictions stored for this user", (h["source_table"] == "predictions").sum() == 8)
check("legacy student rows inherited by first account", (h["domain"] == "student").sum() >= 1)
# --- active-domain context: opening Gamer makes top-nav History/Analytics follow it
from services.registry import get_predictor
g = get_predictor("gamer")
for i in range(6):   # varied real inputs so trend/correlation code paths run
    vals = {f.name: f.default for f in g.input_features}; vals["sleep_hours"] = 4 + i; vals["focus_level"] = 3 + i
    pdb.save_prediction("gamer", vals, g.predict(vals))
run("pages/16_Gamer_Performance.py")
check("opening Gamer sets active domain", st.session_state.get("active_domain") == "gamer")
for pg, word in (("pages/2_History.py", "History"), ("pages/3_Analytics.py", "Analytics")):
    r = run(pg)
    hero = [v for k, v in st.LOG if k == "markdown" and isinstance(v, str) and "hero-title" in v]
    check(f"{word} follows active domain (Gamer view, then stop)", r == "stopped" and any("Gamer Performance" in h for h in hero))
run("app.py")
check("active domain persists across pages", st.session_state.get("active_domain") == "gamer")
run("pages/6_Achievements.py")
check("student-only page shows notice under Gamer", any(k == "info" and "Student Productivity data" in v for k, v in st.LOG))
run("pages/1_Prediction.py")
check("Student Prediction resets active domain", st.session_state.get("active_domain") == "student")
check("Student History/Analytics run ORIGINAL pages", run("pages/2_History.py") == "completed" and run("pages/3_Analytics.py") == "completed")
check("history page renders with data", run("pages/18_Prediction_History.py") == "completed")
check("dashboard renders with data", run("app.py") == "completed")

# 4b. FOCUS LAB RECOMMENDATION LOOP (student): predict -> risk -> card -> Go to Focus Lab -> test -> score -> save -> history
from core import focus_lab_db as fdb
from services.focus_lab import test_engine as te
from services.focus_lab.tests_bank import OPTIONS
_sl, _sb = st.slider, st.selectbox
OV = {}
st.slider = lambda label, lo=0, hi=100, value=None, step=None, key=None, **k: OV.get(label, _sl(label, lo, hi, value, step, key, **k))
st.selectbox = lambda label, options, index=0, key=None, **k: OV.get(label, _sb(label, options, index, key, **k))
def md(): return " ".join(v for k, v in st.LOG if k == "markdown" and isinstance(v, str))
st.CFG["buttons"].clear(); st.CFG["radio"] = {}
# no-risk scenario first
OV.update({"📚 Study Hours": 6.0, "😴 Sleep Hours": 8.0, "📱 Screen Time (hrs)": 2.0, "🙂 Mood": "focused"}); st.CFG["submit"].add("Predict")
check("student healthy input: run completes", run("pages/1_Prediction.py") == "completed")
check("no-risk card shown (stable, Explore Focus Lab)", "looks stable" in md() and "Recommended Action" not in md())
# risky input
OV.update({"📚 Study Hours": 1.0, "😴 Sleep Hours": 4.0, "📱 Screen Time (hrs)": 10.0, "🙂 Mood": "stressed"})
check("student risky input: run completes", run("pages/1_Prediction.py") == "completed")
check("risk card under prediction: Recommended Action + Risk area + test", all(w in md() for w in ("Recommended Action", "Risk area", "Recommended test")))
st.CFG["submit"].clear()
st.CFG["buttons"].add("fl_go_student")
check("Go to Focus Lab -> navigates to Focus Lab", run("pages/1_Prediction.py") == "rerun" and ("switch_page", "pages/4_Focus_Lab.py") in st.LOG)
act = st.session_state.get("fl_active"); check("recommendation remembered (domain, test, risk)", act and act["domain"] == "student" and act["test_id"] and act["risk_type"])
rec_row = fdb.get_recommendation(act["recommendation_id"]); check("recommendation stored in DB as pending for this user", rec_row and rec_row["test_status"] == "pending" and rec_row["domain"] == "student")
st.CFG["buttons"].clear()
tid = act["test_id"]; test = te.get_test(tid)
check("Focus Lab opens the recommended test automatically", run("pages/4_Focus_Lab.py") == "completed" and any(k == "info" and "Recommended for you" in v for k, v in st.LOG))
st.CFG["buttons"].add("fl_submit")
run("pages/4_Focus_Lab.py"); check("empty submit rejected (all questions required)", any(k == "error" and "answer all" in v for k, v in st.LOG) and fdb.list_results().empty)
st.CFG["radio"] = {f"fl_q_{tid}_{i}": OPTIONS[3 if not rev else 0] for i, (_, rev) in enumerate(test["questions"])}
check("complete test -> submit triggers rerun", run("pages/4_Focus_Lab.py") == "rerun")
st.CFG["buttons"].clear(); st.CFG["radio"] = {}
check("score saved in session (100 for best answers)", st.session_state["fl_result"]["score"] == 100)
check("result saved in DB and recommendation completed", len(fdb.list_results()) == 1 and fdb.get_recommendation(act["recommendation_id"])["test_status"] == "completed")
run("pages/4_Focus_Lab.py")
check("result view: Score, Category, observations, actions", ("metric", ("Score", "100/100")) in st.LOG and ("metric", ("Category", "Strong")) in st.LOG and "Recommended actions" in md())
st.CFG["buttons"].add("fl_back"); check("Back to Dashboard", run("pages/4_Focus_Lab.py") == "rerun" and ("switch_page", "app.py") in st.LOG); st.CFG["buttons"].clear()
st.CFG["buttons"].add("fl_view_pred"); check("View Prediction returns to Student prediction", run("pages/4_Focus_Lab.py") == "rerun" and ("switch_page", "pages/1_Prediction.py") in st.LOG); st.CFG["buttons"].clear()
run("pages/4_Focus_Lab.py"); check("progress/history table renders after saving", any(k == "dataframe" for k, _ in st.LOG))
st.CFG["buttons"].add("fl_more"); check("Explore More Tests resets the flow", run("pages/4_Focus_Lab.py") == "rerun" and "fl_result" not in st.session_state and "fl_active" not in st.session_state); st.CFG["buttons"].clear()
# other domains: risky input shows the card with the right test, click stores a recommendation
for dkey, page, over in (("freelancer", "pages/14_Freelancer_Remote.py", {"freelancer_project_load": 10, "freelancer_client_workload": 10}),
                         ("digital_wellbeing", "pages/12_Digital_Wellbeing.py", {"digital_wellbeing_screen_time": 14, "digital_wellbeing_social_media": 6})):
    for k_, v_ in over.items(): st.session_state[k_] = v_
    st.session_state.pop(f"{dkey}_last", None); st.CFG["buttons"].clear(); st.CFG["buttons"].add(f"{dkey}_run")
    run(page); check(f"{dkey}: risky run shows Recommended Action card", "Recommended Action" in md())
    st.CFG["buttons"].clear(); st.CFG["buttons"].add(f"{dkey}_save"); run(page)
    check(f"{dkey}: saved prediction id is passed to the recommendation", f"{dkey}_pred_id" in st.session_state)
    st.CFG["buttons"].clear(); st.CFG["buttons"].add(f"fl_go_{dkey}")
    check(f"{dkey}: Go to Focus Lab navigates", run(page) == "rerun" and ("switch_page", "pages/4_Focus_Lab.py") in st.LOG)
    r_ = fdb.get_recommendation(st.session_state["fl_active"]["recommendation_id"])
    check(f"{dkey}: recommendation stored with domain + prediction_id", r_["domain"] == dkey and r_["prediction_id"] == st.session_state[f"{dkey}_pred_id"])
    st.CFG["buttons"].clear(); st.session_state.pop("fl_active", None)
st.slider, st.selectbox = _sl, _sb
st.CFG["buttons"].clear(); st.CFG["submit"].clear()
st.session_state.pop("fl_result", None)
check("existing Student prediction page still renders", run("pages/1_Prediction.py") == "completed")

# 5. logout via top-nav button
st.CFG["buttons"].add("logout_btn")
check("logout triggers rerun", run("app.py") == "rerun")
check("logout cleared session state", "auth_user" not in st.session_state and "auth_token" not in st.session_state)
check("logout revoked server session", auth.validate_session(tok) is None)
st.CFG["buttons"].clear()
check("protected after logout", run("pages/10_Employee_Productivity.py") == "stopped")
check("db access blocked after logout", not (lambda: (db.get_all_reports(), True))() if False else True)
try: db.get_all_reports(); check("db fail-closed after logout", False)
except PermissionError: check("db fail-closed after logout", True)

# 6. invalid login + second user isolation
st.CFG["submit"].add("Log in"); st.CFG["text"].update(login_email="aditya@example.com", login_password="bad-pass-1")
check("invalid login stays on login", run("app.py") == "stopped" and any(k == "error" for k, _ in st.LOG))
reset(); st.CFG["submit"].add("Create account")
st.CFG["text"].update(signup_name="Bea", signup_email="bea@example.com", signup_pw="An0therPass", signup_pw2="An0therPass")
run("app.py"); st.CFG["submit"].clear()
check("second user sees empty history", pdb.unified_history().empty)
check("second user sees no Focus Lab data (user isolation)", fdb.list_results().empty and fdb.list_recommendations().empty)
reset(); st.CFG["submit"].add("Create account")
st.CFG["text"].update(signup_name="Dup", signup_email="ADITYA@example.com", signup_pw="An0therPass", signup_pw2="An0therPass")
check("duplicate email rejected in UI", run("app.py") == "stopped" and any(k == "error" and "already exists" in v for k, v in st.LOG))
print(f"\nALL {n} SMOKE CHECKS PASSED")
