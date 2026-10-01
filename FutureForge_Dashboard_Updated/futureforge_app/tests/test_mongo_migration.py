"""Migration test with mongomock (no real MongoDB needed).  python tests/test_mongo_migration.py"""
import os, shutil, sqlite3, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp()) / "m.db"; shutil.copy(ROOT / "backend/data/futureforge.db", tmp)
os.environ["FUTUREFORGE_DB"] = str(tmp)
import mongomock
from core import db, auth, focus_lab_db as fdb
from services.focus_lab import test_engine as te
from scripts.migrate_sqlite_to_mongo import migrate
CUR = {"uid": None}; db.set_user_resolver(lambda: CUR["uid"]); db.init_db()
u, _ = auth.register_user("Aditya", "a@example.com", "Str0ngPass1", "Str0ngPass1"); CUR["uid"] = u["id"]
rid = fdb.create_recommendation("student", 1, "Focus Consistency", "medium", "focus_consistency")
fdb.save_result(te.submit("focus_consistency", [1] * 6), domain="student", recommendation_id=rid)
n = 0
def check(name, cond):
    global n; assert cond, "FAIL: " + name; n += 1; print("ok  ", name)
m = mongomock.MongoClient()["ff"]
dry = migrate(str(tmp), m, dry_run=True); check("dry run copies nothing", all(m[t].count_documents({}) == 0 for t in dry))
c = migrate(str(tmp), m)
check("row counts match for every table", all(m[t].count_documents({}) == k for t, k in c.items()))
check("legacy reports migrated (14)", m["daily_reports"].count_documents({}) == 14)
usr = m["users"].find_one({"email": "a@example.com"})
check("password stays a scrypt hash, no plaintext anywhere", usr["password_hash"].startswith("scrypt$") and "Str0ngPass1" not in str(list(m["users"].find())))
check("Focus Lab result stored with answers as a real array", m["focus_lab_results"].find_one()["answers"] == [1] * 6)
check("user_sessions not copied", "user_sessions" not in c)
migrate(str(tmp), m); check("idempotent: re-run creates no duplicates", all(m[t].count_documents({}) == k for t, k in c.items()))
c2 = sqlite3.connect(tmp); c2.execute("UPDATE users SET password_hash='plaintext123'"); c2.commit()
try: migrate(str(tmp), mongomock.MongoClient()["x"]); check("plaintext guard", False)
except SystemExit as e: check("refuses to migrate a non-hashed password", "scrypt" in str(e))
print(f"\nALL {n} MIGRATION CHECKS PASSED")
