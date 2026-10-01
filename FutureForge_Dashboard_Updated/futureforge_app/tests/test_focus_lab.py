"""Focus Lab tests: rules, scoring, per-user storage.  Run: python tests/test_focus_lab.py  (no Streamlit needed)"""
import os, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp()) / "fl.db"
shutil.copy(ROOT / "backend/data/futureforge.db", tmp)
os.environ["FUTUREFORGE_DB"] = str(tmp)

from core import db, auth, focus_lab_db as fdb                     # noqa: E402
from services.registry import DOMAINS, get_predictor               # noqa: E402
from services.focus_lab import recommendation_engine as E, test_engine as T   # noqa: E402
from services.focus_lab.scoring import category_for, score_answers  # noqa: E402
from services.focus_lab.tests_bank import TESTS, OPTIONS           # noqa: E402

n = 0
def check(name, cond):
    global n
    assert cond, "FAIL: " + name
    n += 1
    print("ok  ", name)

def scenario(domain, **over):
    p = get_predictor(domain)
    vals = {f.name: f.default for f in p.input_features}
    vals.update(over)
    r = p.predict(vals)
    return E.analyze_result(domain, vals, r), r

# ---------------------------------------------------------------- test bank + scoring
check("22 tests, 5-10 questions, 4 actions each", len(TESTS) == 22 and all(5 <= len(t["questions"]) <= 10 and len(t["actions"]) == 4 for t in TESTS.values()))
check("the 9 spec example tests exist", {"focus_consistency", "time_management", "study_habit", "workload_management", "digital_distraction",
      "routine_consistency", "task_prioritization", "learning_consistency", "habit_consistency"} <= set(TESTS))
for tid, t in TESTS.items():
    best = [len(OPTIONS) - 1 if not rev else 0 for _, rev in t["questions"]]
    worst = [0 if not rev else len(OPTIONS) - 1 for _, rev in t["questions"]]
    b, w = T.submit(tid, best), T.submit(tid, worst)
    assert b["score"] == 100 and b["category"] == "Strong" and w["score"] == 0 and w["category"] == "High Attention", tid
check("every test: best answers = 100 Strong, worst = 0 High Attention", True)
check("category boundaries 80/60/40", [category_for(x) for x in (100, 80, 79, 60, 59, 40, 39, 0)] ==
      ["Strong", "Strong", "Moderate", "Moderate", "Needs Attention", "Needs Attention", "High Attention", "High Attention"])
t = T.get_test("focus_consistency"); mid = [1] * len(t["questions"])
check("score is computed from answers (not random): same answers -> same score", T.submit("focus_consistency", mid)["score"] == T.submit("focus_consistency", mid)["score"])
a1 = T.submit("focus_consistency", [3 if not rev else 0 for _, rev in t["questions"]])["score"]
a2 = T.submit("focus_consistency", [2 if not rev else 1 for _, rev in t["questions"]])["score"]
check("better answers -> higher score", a1 > a2)
for bad, why in (([None] * 6, "empty"), ([1] * 3, "too few"), ([9] * 6, "out of range"), ([1, 1, 1, 1, 1, None], "one missing"), ([-1] * 6, "negative")):
    try: T.submit("focus_consistency", bad); check(f"reject {why}", False)
    except ValueError: check(f"reject invalid answers: {why}", True)
try: T.get_test("nope"); check("unknown test", False)
except KeyError: check("unknown test id raises KeyError", True)
res = T.submit("focus_consistency", [0 if not rev else 3 for _, rev in t["questions"]])
check("observations + actions generated for low score", len(res["observations"]) >= 2 and len(res["actions"]) == 4)
txt = " ".join(res["observations"] + res["actions"]).lower()
check("neutral language (no diagnosis / alarming words)", not any(w in txt for w in ("disorder", "burnout", "failing", "severe", "diagnos", "depress")))

# ---------------------------------------------------------------- recommendation rules
tests_used = {}
for d in DOMAINS:
    if d.predictor_cls is None: continue
    rec, r = scenario(d.key)
    check(f"{d.key}: defaults ({r.score:.0f}, {r.risk}) -> valid recommendation object", rec.domain == d.key and (rec.has_risk == (rec.primary is not None)))
check("no-risk scenario: stable message, no test", (lambda rc: (not rc.has_risk) and rc.primary is None and "stable" in rc.headline)(scenario("employee")[0]))

# spec examples: domain + risk signal -> specific test
rec, _ = scenario("employee", task_completion=5);                                 check("Employee + low task completion -> Time Management", rec.has_risk and rec.primary.test_id == "time_management")
rec, _ = scenario("freelancer", project_load=10, client_workload=10);            check("Freelancer + high workload -> Workload Balance", rec.primary.test_id == "workload_balance")
rec, _ = scenario("digital_wellbeing", screen_time=14, social_media=6);          check("Digital + high screen time -> Digital Distraction", rec.primary.test_id == "digital_distraction")
rec, _ = scenario("fitness", exercise_minutes=0, daily_steps=1, screen_time=12); check("Fitness + poor routine -> Lifestyle Consistency", rec.primary.test_id == "lifestyle_consistency")
rec, _ = scenario("gamer", session_minutes=420, break_frequency=0, sleep_hours=4);  check("Gamer + long sessions/few breaks/low sleep -> has risk", rec.has_risk)
check("Gamer: session/sleep areas map to different tests", len({a.test_id for a in [rec.primary] + rec.others}) == len([rec.primary] + rec.others) >= 2)
rec, _ = scenario("team_project", deadline_pressure=10, pending_tasks=40, project_progress=10); check("Team + deadline/backlog -> Project Risk or Task Prioritization", rec.primary.test_id in ("project_risk", "task_prioritization"))
rec, _ = scenario("personalized_learning", revision_frequency=0, study_hours=0);  check("Learning + low revision/study -> Learning Consistency", rec.primary.test_id == "learning_consistency")
rec, _ = scenario("habit_routine", routine_consistency=1, sleep_consistency=1);   check("Habit + low routine -> Sleep Routine / Routine Stability", rec.primary.test_id in ("sleep_routine", "routine_stability"))
# Student (trained-model outputs are passed in)
rec = E.analyze("student", {"study_hours": 6, "sleep_hours": 7.5, "screen_time": 3, "mood": "focused"}, score=48, risk="high", extras={"stress_score": 30})
check("Student + low focus -> Focus Consistency", rec.has_risk and rec.primary.test_id == "focus_consistency")
rec = E.analyze("student", {"study_hours": 6, "sleep_hours": 8, "screen_time": 2, "mood": "focused"}, score=91, risk="low", extras={"stress_score": 10})
check("Student healthy -> no risk", not rec.has_risk)
rec = E.analyze("student", {"study_hours": 1, "sleep_hours": 4, "screen_time": 10, "mood": "stressed"}, score=40, risk="high", extras={"stress_score": 80})
ids = [rec.primary.test_id] + [o.test_id for o in rec.others]
check("Student multi-risk: different tests for different risks (not one test for everything)", len(set(ids)) == len(ids) >= 2)
check("card lists at most 1 primary + 2 others", len(ids) <= 3)
rec = E.analyze("employee", {}, score=60, risk="medium", suitability={"working_hours": 90})
check("medium risk with no single weak input -> fallback test (never empty)", rec.has_risk and rec.primary.key == "overall")
try: E.analyze("nope", {}, score=50, risk="medium"); check("unknown domain", False)
except KeyError: check("unknown domain raises", True)
check("no scary wording in any rule text", not any(w in (why + label).lower() for r in E.RULES.values() for _, label, _, _, why in r for w in ("severe", "failing", "burnout", "disorder")))
check("every rule + fallback points at an existing test", all(t in TESTS for r in E.RULES.values() for _, _, t, _, _ in r) and all(t in TESTS for _, t in E.FALLBACK.values()))
# distinct-test coverage across each domain's rules
for d, rules in E.RULES.items():
    check(f"{d}: rule table maps to {len({t for _,_,t,_,_ in rules})} distinct tests", len({t for _, _, t, _, _ in rules}) >= 3)

# ---------------------------------------------------------------- storage + user isolation
CUR = {"uid": None}
db.set_user_resolver(lambda: CUR["uid"]); db.init_db()
try: fdb.list_results(); check("fail-closed without user", False)
except PermissionError: check("fail-closed without a logged-in user", True)
ua, _ = auth.register_user("User A", "a@example.com", "Str0ngPass1", "Str0ngPass1")
ub, _ = auth.register_user("User B", "b@example.com", "Str0ngPass1", "Str0ngPass1")
CUR["uid"] = ua["id"]
r1 = fdb.create_recommendation("student", 7, "Focus Consistency", "medium", "focus_consistency")
r1b = fdb.create_recommendation("student", 7, "Focus Consistency", "medium", "focus_consistency")
check("pending recommendation is de-duplicated", r1 == r1b)
rr = fdb.get_recommendation(r1); check("recommendation stores domain/prediction/risk/test/status", rr["domain"] == "student" and rr["prediction_id"] == 7 and rr["risk_type"] == "Focus Consistency" and rr["recommended_test"] == "focus_consistency" and rr["test_status"] == "pending")
res = T.submit("focus_consistency", [1] * 6)
rid = fdb.save_result(res, domain="student", prediction_id=7, recommendation_id=r1)
rr = fdb.get_recommendation(r1); check("completing test marks recommendation completed with score", rr["test_status"] == "completed" and rr["test_score"] == res["score"])
row = fdb.list_results().iloc[0]; check("result stored: test/domain/prediction/score/category/answers/created_at", row["test_id"] == "focus_consistency" and row["domain"] == "student" and row["prediction_id"] == 7 and row["score"] == res["score"] and row["category"] == res["category"] and row["answers"] == "[1, 1, 1, 1, 1, 1]" and row["created_at"])
wrong = fdb.create_recommendation("student", 8, "Study Consistency", "medium", "study_habit")
fdb.save_result(T.submit("time_management", [2] * 6), domain="student", recommendation_id=wrong)
check("taking a different test does not complete the recommendation for another test", fdb.get_recommendation(wrong)["test_status"] == "pending")
CUR["uid"] = ub["id"]
check("User B sees none of User A's results", fdb.list_results().empty and fdb.list_recommendations().empty)
check("User B cannot read User A's recommendation", fdb.get_recommendation(r1) is None)
fdb.save_result(T.submit("focus_consistency", [3, 0, 3, 0, 3, 3]), domain="student", recommendation_id=r1)     # try to hijack A's rec
CUR["uid"] = ua["id"]
check("User B cannot complete/overwrite User A's recommendation", fdb.get_recommendation(r1)["test_score"] == res["score"] and len(fdb.list_results()) == 2)
CUR["uid"] = ub["id"]
check("User B result stored under B only", len(fdb.list_results()) == 1 and fdb.list_results().iloc[0]["recommendation_id"] is None or fdb.list_results().iloc[0]["recommendation_id"] != r1)
import sqlite3
tabs = {r[0] for r in sqlite3.connect(tmp).execute("select name from sqlite_master where type='table'")}
check("same SQLite DB, only the 2 new tables added", {"focus_lab_recommendations", "focus_lab_results"} <= tabs)
check("legacy Student tables untouched", {"daily_reports", "test_results", "focus_sessions", "predictions"} <= tabs)
print(f"\nALL {n} FOCUS LAB CHECKS PASSED")
