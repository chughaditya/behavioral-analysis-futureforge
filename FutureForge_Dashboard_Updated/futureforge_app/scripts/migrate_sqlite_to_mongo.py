"""
One-way, idempotent copy of the FutureForge SQLite database into MongoDB.

  Windows PowerShell:
      pip install -r requirements-mongo.txt
      $env:MONGODB_URI = "mongodb+srv://<user>:<password>@<cluster>/"     # from Atlas -> Connect -> Drivers
      python scripts/migrate_sqlite_to_mongo.py            # add --dry-run to only print what would be copied

Rules:
  * The connection string is read ONLY from the MONGODB_URI environment variable (never a CLI arg / never stored in code).
  * App-login passwords are copied exactly as stored (scrypt hashes). The script REFUSES to run if any users.password_hash
    is not a scrypt hash, so a plaintext password can never be pushed to MongoDB. Real Gmail passwords are never collected.
  * user_sessions (ephemeral login tokens) are not copied. Re-running is safe: documents are upserted by primary key.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE = os.environ.get("FUTUREFORGE_DB") or str(ROOT / "backend" / "data" / "futureforge.db")
SKIP_TABLES = {"sqlite_sequence", "user_sessions"}
JSON_COLUMNS = {"input_data", "details", "answers", "recommendations"}


def _pk_columns(conn, table: str) -> list[str]:
    cols = [r for r in conn.execute(f'PRAGMA table_info("{table}")') if r[5] > 0]
    return [r[1] for r in sorted(cols, key=lambda r: r[5])]


def _doc(row: sqlite3.Row, pk: list[str]) -> dict:
    d = dict(row)
    for c in JSON_COLUMNS & d.keys():
        if isinstance(d[c], str):
            try:
                d[c] = json.loads(d[c])
            except ValueError:
                pass
    d["_id"] = d[pk[0]] if len(pk) == 1 else "|".join(str(d[c]) for c in pk) if pk else None
    return d


def migrate(sqlite_path: str, mongo_db, dry_run: bool = False) -> dict[str, int]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if r[0] not in SKIP_TABLES]

    if "users" in tables:                                   # safety gate: hashes only, never plaintext
        bad = [r["id"] for r in conn.execute("SELECT id, password_hash FROM users") if not str(r["password_hash"] or "").startswith("scrypt$")]
        if bad:
            raise SystemExit(f"Refusing to migrate: users {bad} have a password that is not a scrypt hash.")

    counts: dict[str, int] = {}
    for t in tables:
        pk = _pk_columns(conn, t)
        rows = conn.execute(f'SELECT * FROM "{t}"').fetchall()
        counts[t] = len(rows)
        if dry_run or not rows:
            continue
        docs = [_doc(r, pk) for r in rows]
        for d in docs:
            if d["_id"] is None:
                d.pop("_id")
                mongo_db[t].insert_one(d)
            else:
                mongo_db[t].replace_one({"_id": d["_id"]}, d, upsert=True)
    if not dry_run:
        if "users" in tables:
            mongo_db["users"].create_index("email", unique=True)
        for t in tables:
            if t != "users" and any(c[1] == "user_id" for c in conn.execute(f'PRAGMA table_info("{t}")')):
                mongo_db[t].create_index("user_id")
        for t, n in counts.items():                         # verify
            got = mongo_db[t].count_documents({})
            if got < n:
                raise SystemExit(f"Verification failed for {t}: SQLite {n} rows, MongoDB {got} documents.")
    conn.close()
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sqlite", default=DEFAULT_SQLITE)
    ap.add_argument("--db-name", default=os.environ.get("MONGODB_DB", "futureforge"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        sys.exit("Set the MONGODB_URI environment variable first (see the top of this file).")
    from pymongo import MongoClient
    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    counts = migrate(a.sqlite, client[a.db_name], a.dry_run)
    print(("DRY RUN — would copy" if a.dry_run else "Copied") + " into database '%s':" % a.db_name)
    for t, n in counts.items():
        print(f"  {t:28s} {n} rows")


if __name__ == "__main__":
    main()
