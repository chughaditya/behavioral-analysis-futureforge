"""Backend tests: migration, auth, sessions, isolation, prediction storage. Run: python tests/test_backend.py"""
import os, shutil, sqlite3, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp()) / "test.db"
shutil.copy(ROOT / "backend/data/futureforge.db", tmp)          # real legacy DB, copied — original untouched
os.environ["FUTUREFORGE_DB"] = str(tmp)

from core import db, auth, predictions_db as pdb           # noqa: E402
from services.registry import get_predictor, DOMAINS       # noqa: E402

CUR = {"uid": None}
db.set_user_resolver(lambda: CUR["uid"])
passed = 0
def check(name, cond):
    global passed
    assert cond, f"FAIL: {name}"
    passed += 1
    print("ok  ", name)

legacy = sqlite3.connect(tmp).execute("SELECT COUNT(*) FROM daily_reports").fetchone()[0]
db.init_db(); db.init_db()                                      # idempotent
tables = {r[0] for r in sqlite3.connect(tmp).execute("select name from sqlite_master where type='table'")}
check("new tables exist", {"users", "user_sessions", "predictions", "user_preferences", "focus_sessions"} <= tables)
check("legacy rows preserved by migration", sqlite3.connect(tmp).execute("SELECT COUNT(*) FROM daily_reports").fetchone()[0] == legacy)
try: db.get_all_reports(); check("fail-closed without user", False)
except PermissionError: check("fail-closed without user (PermissionError)", True)

# --- signup validation
for args, frag in [(("", "a@b.co", "Passw0rdx", "Passw0rdx"), "fill in"), (("A", "not-an-email", "Passw0rdx", "Passw0rdx"), "valid email"),
                   (("A", "a@b.co", "Passw0rdx", "Different1"), "do not match"), (("A", "a@b.co", "short1", "short1"), "8 characters"),
                   (("A", "a@b.co", "onlyletters", "onlyletters"), "letter and one number")]:
    u, e = auth.register_user(*args); check(f"reject: {frag}", u is None and frag in e)
a, e = auth.register_user("Aditya Chugh", "Aditya@Example.com", "Str0ngPass1", "Str0ngPass1"); check("signup A", a and not e)
dup, e = auth.register_user("X", "aditya@example.COM", "Str0ngPass1", "Str0ngPass1"); check("duplicate email (case-insens.)", dup is None and "already exists" in e)
raw = sqlite3.connect(tmp).execute("SELECT password_hash FROM users").fetchone()[0]
check("password stored hashed, not raw", "Str0ngPass1" not in raw and raw.startswith("scrypt$"))
check("hash salted (same pw, different hash)", auth.hash_password("Str0ngPass1") != auth.hash_password("Str0ngPass1"))
bad, e = auth.authenticate("aditya@example.com", "wrongpass1"); check("invalid login rejected", bad is None and "Incorrect" in e)
nobody, e2 = auth.authenticate("nobody@example.com", "whatever1"); check("unknown email same message", e2 == e)
ok, _ = auth.authenticate("ADITYA@example.com", "Str0ngPass1"); check("valid login", ok and ok["id"] == a["id"])

# --- legacy claim: first account inherits pre-accounts data; second account sees none of it
CUR["uid"] = a["id"]
check("first user inherits legacy reports", len(db.get_all_reports()) == legacy and legacy > 0)
b, _ = auth.register_user("Bea", "bea@example.com", "An0therPass", "An0therPass"); check("signup B", b is not None)
CUR["uid"] = b["id"]
check("B sees none of A's reports", db.get_all_reports().empty)
check("B sees none of A's test results", db.get_all_test_results().empty)

# --- isolation of every data type
def payload():
    return {"date": "2026-09-30", "day": "Wednesday", "month": "September", "year": 2026, "name": "Bea", "study_hours": 5, "sleep_hours": 7,
            "screen_time": 3, "mood": "focused", "focus_score": 80, "stress_score": 20, "mood_score": 9, "sleep_display": "7h 0m",
            "productivity_score": 82, "prediction": "High Focus Potential", "prediction_confidence": 90, "prediction_explanation": "", "recommendations": "", "cluster": 1}
db.insert_report(payload()); db.insert_test_result("Reaction Time", 70)
db.create_focus_session("student", "", 25, "B session"); db.set_focus_daily_target("student", "", 45)
check("B focus session is B's", db.get_open_focus_session("student", "")["label"] == "B session")
check("B focus target is B's", db.get_focus_daily_target("student", "") == 45)
CUR["uid"] = a["id"]
check("A cannot see B's report", (db.get_all_reports()["name"] != "Bea").all())
check("A cannot see B's focus session", db.get_open_focus_session("student", "") is None)
check("A focus target unaffected", db.get_focus_daily_target("student", "") == db.DEFAULT_DAILY_TARGET_MINUTES)
bid = sqlite3.connect(tmp).execute("SELECT id FROM daily_reports WHERE user_id=?", (b["id"],)).fetchone()[0]
db.delete_report(bid); CUR["uid"] = b["id"]
check("A cannot delete B's report by id", len(db.get_all_reports()) == 1)
check("A cannot read B's report by id", (CUR.__setitem__("uid", a["id"]) or db.get_report_by_id(bid)) is None)
CUR["uid"] = a["id"]; db.clear_all_reports(); CUR["uid"] = b["id"]
check("A clearing data leaves B's intact", len(db.get_all_reports()) == 1)

# --- predictions per domain, storage, history, isolation
CUR["uid"] = a["id"]
for d in DOMAINS[1:]:
    p = get_predictor(d.key); vals = {f.name: f.default for f in p.input_features}
    r = p.predict(vals); pdb.save_prediction(d.key, vals, r)
    check(f"{d.key}: stored + honest (rule_based, no confidence)", r.source == "rule_based" and r.confidence is None and 0 <= r.score <= 100)
h = pdb.unified_history()
check("A unified history has 8 new-domain rows", (h["source_table"] == "predictions").sum() == 8)
check("A domain history is domain-only", len(pdb.domain_history("gamer")) == 1)
CUR["uid"] = b["id"]
h = pdb.unified_history()
check("B unified history excludes A's predictions", (h["source_table"] == "predictions").sum() == 0)
check("B sees own student report in unified history", (h["domain"] == "student").sum() == 1)
try: get_predictor("employee").predict({"working_hours": 99}); check("input validation", False)
except ValueError: check("out-of-range / missing input rejected", True)

# --- sessions
tok = auth.create_session(a["id"]); check("session valid", auth.validate_session(tok)["id"] == a["id"])
check("token stored only as hash", sqlite3.connect(tmp).execute("SELECT COUNT(*) FROM user_sessions WHERE token_hash=?", (tok,)).fetchone()[0] == 0)
auth.revoke_session(tok); check("logout revokes session server-side", auth.validate_session(tok) is None)
check("garbage token rejected", auth.validate_session("nope") is None and auth.validate_session(None) is None)
sqlite3.connect(tmp).execute("select 1")
c = sqlite3.connect(tmp); t2 = auth.create_session(a["id"]); c.execute("UPDATE user_sessions SET expires_at='2000-01-01T00:00:00'"); c.commit(); c.close()
check("expired session rejected", auth.validate_session(t2) is None)

# --- lockout & password change
for _ in range(5): auth.authenticate("bea@example.com", "wrong-pass1")
_, msg = auth.authenticate("bea@example.com", "An0therPass"); check("lockout after 5 failures", "Too many" in msg)
auth._failures.clear()
check("change password wrong current", auth.change_password(b["id"], "nope", "N3wPassword", "N3wPassword") is not None)
check("change password ok", auth.change_password(b["id"], "An0therPass", "N3wPassword", "N3wPassword") is None)
check("old password no longer works", auth.authenticate("bea@example.com", "An0therPass")[0] is None)
check("integrity: SQLite integrity_check ok", sqlite3.connect(tmp).execute("PRAGMA integrity_check").fetchone()[0] == "ok")
print(f"\nALL {passed} CHECKS PASSED")
