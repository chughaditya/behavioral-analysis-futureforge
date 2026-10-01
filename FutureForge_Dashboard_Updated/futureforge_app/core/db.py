"""
FutureForge — Persistence Layer
Real SQLite storage (not frontend/session state). Survives app restarts.
"""

import os
import sqlite3
from datetime import datetime, date as date_cls
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# FUTUREFORGE_DB lets tests / deployments point at another file; default is the original DB.
DB_PATH = Path(os.environ.get("FUTUREFORGE_DB") or (Path(__file__).parent.parent / "backend" / "data" / "futureforge.db"))


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Per-user scoping
#   Every query on user-owned tables (daily_reports, test_results, focus_sessions,
#   focus_settings, predictions, user_preferences) is filtered by the id returned
#   here. The resolver is registered by core.auth_ui and reads the authenticated
#   user from the Streamlit session. With no user bound, this FAILS CLOSED.
# ---------------------------------------------------------------------------
_user_resolver = None


def set_user_resolver(fn) -> None:
    global _user_resolver
    _user_resolver = fn


def current_user_id() -> int:
    uid = _user_resolver() if _user_resolver else None
    if uid is None:
        raise PermissionError("Not authenticated: no user is bound to this request.")
    return int(uid)


_FOCUS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_type TEXT NOT NULL,
    profile_key TEXT NOT NULL DEFAULT '',
    label TEXT,
    planned_seconds INTEGER NOT NULL,
    elapsed_seconds REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL,              -- running | paused | completed | ended | reset
    date TEXT NOT NULL,                -- local date the session started (YYYY-MM-DD)
    started_at TEXT NOT NULL,
    last_resumed_at TEXT,              -- set only while status = 'running'
    ended_at TEXT,
    created_at TEXT NOT NULL,
    pause_count INTEGER NOT NULL DEFAULT 0
)
"""
_FOCUS_SETTINGS_SQL = """
CREATE TABLE IF NOT EXISTS focus_settings (
    profile_type TEXT NOT NULL,
    profile_key TEXT NOT NULL DEFAULT '',
    daily_target_minutes INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (profile_type, profile_key)
)
"""
_FOCUS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_focus_profile_status
ON focus_sessions (profile_type, profile_key, status)
"""


def init_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            day TEXT NOT NULL,
            month TEXT NOT NULL,
            year INTEGER NOT NULL,
            name TEXT,
            study_hours REAL,
            sleep_hours REAL,
            screen_time REAL,
            mood TEXT,
            focus_score REAL,
            stress_score REAL,
            mood_score REAL,
            sleep_display TEXT,
            productivity_score REAL,
            prediction TEXT,
            prediction_confidence REAL,
            prediction_explanation TEXT,
            recommendations TEXT,
            cluster INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            test_type TEXT NOT NULL,
            score REAL,
            accuracy REAL,
            reaction_time_ms REAL,
            duration_s REAL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(_FOCUS_TABLE_SQL)
    cols = {r[1] for r in cur.execute("PRAGMA table_info(focus_sessions)").fetchall()}
    if "pause_count" not in cols:  # tables created before pause tracking existed
        cur.execute("ALTER TABLE focus_sessions ADD COLUMN pause_count INTEGER NOT NULL DEFAULT 0")
    cur.execute(_FOCUS_INDEX_SQL)
    cur.execute(_FOCUS_SETTINGS_SQL)
    _migrate_multi_user(cur)
    conn.commit()
    conn.close()


def _add_column_if_missing(cur, table: str, column: str, ddl: str) -> None:
    cols = {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _migrate_multi_user(cur) -> None:
    """Additive, idempotent migration. Never drops or rewrites existing rows:
    legacy rows keep user_id = NULL until the first account claims them."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            domain TEXT NOT NULL,
            input_data TEXT NOT NULL,          -- JSON of the submitted inputs
            prediction REAL,                   -- headline score (ML forecast if a model ran, else rule-based indicator)
            risk TEXT,
            confidence REAL,                   -- NULL unless a trained model produced one
            behavioral_pattern TEXT,
            source TEXT NOT NULL,              -- 'ml_model' | 'rule_based'
            details TEXT,                      -- JSON: extra scores, insights, recommendations
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pred_user_domain ON predictions (user_id, domain, created_at)")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            pref_key TEXT NOT NULL,
            pref_value TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, pref_key)
        )
        """
    )

    # Ownership columns on the pre-existing tables (NULL = legacy / unclaimed).
    for table in ("daily_reports", "test_results", "focus_sessions"):
        _add_column_if_missing(cur, table, "user_id", "INTEGER REFERENCES users(id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_daily_user_date ON daily_reports (user_id, date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tests_user ON test_results (user_id, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_focus_user_profile ON focus_sessions (user_id, profile_type, profile_key, status)")

    # focus_settings had PRIMARY KEY (profile_type, profile_key): rebuild it once so the
    # target is per user. Existing rows are copied over unchanged (user_id NULL).
    fs_cols = {r[1] for r in cur.execute("PRAGMA table_info(focus_settings)").fetchall()}
    if "user_id" not in fs_cols:
        cur.execute(
            """
            CREATE TABLE focus_settings_v2 (
                user_id INTEGER REFERENCES users(id),
                profile_type TEXT NOT NULL,
                profile_key TEXT NOT NULL DEFAULT '',
                daily_target_minutes INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            "INSERT INTO focus_settings_v2 (user_id, profile_type, profile_key, daily_target_minutes, updated_at) "
            "SELECT NULL, profile_type, profile_key, daily_target_minutes, updated_at FROM focus_settings"
        )
        cur.execute("DROP TABLE focus_settings")
        cur.execute("ALTER TABLE focus_settings_v2 RENAME TO focus_settings")
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_focus_settings_user ON focus_settings (user_id, profile_type, profile_key)"
    )


def claim_legacy_rows(conn: sqlite3.Connection, user_id: int) -> dict:
    """Assign pre-accounts data (user_id IS NULL) to `user_id`. Called once, for the very
    first account, so the original single-user history is preserved rather than orphaned."""
    counts = {}
    for table in ("daily_reports", "test_results", "focus_sessions", "focus_settings"):
        cur = conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL", (user_id,))
        counts[table] = cur.rowcount
    return counts


# ---------------------------------------------------------------------------
# Daily reports
# ---------------------------------------------------------------------------
def insert_report(payload: dict[str, Any], force_new: bool = False) -> int:
    """Insert a daily report. Overwrites today's existing entry unless force_new=True
    (matches the "prevent accidental duplicate saves" / "Save as New Entry" spec)."""
    uid = current_user_id()
    conn = _connect()
    cur = conn.cursor()

    if not force_new:
        cur.execute("DELETE FROM daily_reports WHERE date = ? AND user_id = ?", (payload["date"], uid))

    cur.execute(
        """
        INSERT INTO daily_reports
        (user_id, date, day, month, year, name, study_hours, sleep_hours, screen_time, mood,
         focus_score, stress_score, mood_score, sleep_display, productivity_score,
         prediction, prediction_confidence, prediction_explanation, recommendations,
         cluster, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            uid,
            payload["date"],
            payload["day"],
            payload["month"],
            payload["year"],
            payload.get("name", ""),
            payload["study_hours"],
            payload["sleep_hours"],
            payload["screen_time"],
            payload["mood"],
            payload["focus_score"],
            payload["stress_score"],
            payload["mood_score"],
            payload["sleep_display"],
            payload["productivity_score"],
            payload["prediction"],
            payload["prediction_confidence"],
            payload["prediction_explanation"],
            payload["recommendations"],
            payload.get("cluster", -1),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def report_exists_for_date(date_str: str) -> bool:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM daily_reports WHERE date = ? AND user_id = ? LIMIT 1", (date_str, current_user_id()))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def get_all_reports() -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT * FROM daily_reports WHERE user_id = ? ORDER BY date ASC", conn, params=(current_user_id(),)
    )
    conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_report_by_id(report_id: int) -> Optional[dict]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_reports WHERE id = ? AND user_id = ?", (report_id, current_user_id()))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_report(report_id: int) -> None:
    conn = _connect()
    conn.execute("DELETE FROM daily_reports WHERE id = ? AND user_id = ?", (report_id, current_user_id()))
    conn.commit()
    conn.close()


def clear_all_reports() -> None:
    conn = _connect()
    conn.execute("DELETE FROM daily_reports WHERE user_id = ?", (current_user_id(),))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Test results (Focus Lab)
# ---------------------------------------------------------------------------
def insert_test_result(
    test_type: str,
    score: float,
    accuracy: Optional[float] = None,
    reaction_time_ms: Optional[float] = None,
    duration_s: Optional[float] = None,
) -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO test_results (user_id, date, test_type, score, accuracy, reaction_time_ms, duration_s, created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            current_user_id(),
            date_cls.today().isoformat(),
            test_type,
            score,
            accuracy,
            reaction_time_ms,
            duration_s,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_all_test_results() -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT * FROM test_results WHERE user_id = ? ORDER BY created_at DESC", conn, params=(current_user_id(),)
    )
    conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def clear_all_tests() -> None:
    conn = _connect()
    conn.execute("DELETE FROM test_results WHERE user_id = ?", (current_user_id(),))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Data Import (Settings > Data Management)
# ---------------------------------------------------------------------------
REPORT_COLUMNS = [
    "date", "day", "month", "year", "name", "study_hours", "sleep_hours", "screen_time", "mood",
    "focus_score", "stress_score", "mood_score", "sleep_display", "productivity_score",
    "prediction", "prediction_confidence", "prediction_explanation", "recommendations", "cluster",
]

TEST_COLUMNS = ["date", "test_type", "score", "accuracy", "reaction_time_ms", "duration_s"]


def bulk_import_reports(rows: list[dict], overwrite_existing: bool = True) -> dict:
    """Imports a list of report dicts (already matching REPORT_COLUMNS, missing
    keys are filled with sensible defaults). Returns {"inserted": n, "skipped": n}."""
    inserted, skipped = 0, 0
    uid = current_user_id()
    conn = _connect()
    cur = conn.cursor()
    for row in rows:
        date_str = str(row.get("date", "")).strip()
        if not date_str:
            skipped += 1
            continue
        try:
            dt = pd.to_datetime(date_str)
        except Exception:
            skipped += 1
            continue

        if not overwrite_existing:
            cur.execute("SELECT 1 FROM daily_reports WHERE date = ? AND user_id = ? LIMIT 1", (dt.date().isoformat(), uid))
            if cur.fetchone():
                skipped += 1
                continue
        else:
            cur.execute("DELETE FROM daily_reports WHERE date = ? AND user_id = ?", (dt.date().isoformat(), uid))

        payload = {
            "date": dt.date().isoformat(),
            "day": row.get("day") or dt.strftime("%A"),
            "month": row.get("month") or dt.strftime("%B"),
            "year": int(row.get("year") or dt.year),
            "name": row.get("name", "") or "",
            "study_hours": float(row.get("study_hours", 0) or 0),
            "sleep_hours": float(row.get("sleep_hours", 0) or 0),
            "screen_time": float(row.get("screen_time", 0) or 0),
            "mood": row.get("mood", "balanced") or "balanced",
            "focus_score": float(row.get("focus_score", 0) or 0),
            "stress_score": float(row.get("stress_score", 0) or 0),
            "mood_score": float(row.get("mood_score", 0) or 0),
            "sleep_display": row.get("sleep_display") or f"{float(row.get('sleep_hours', 0) or 0):.1f}h",
            "productivity_score": float(row.get("productivity_score", 0) or 0),
            "prediction": row.get("prediction", "") or "",
            "prediction_confidence": float(row.get("prediction_confidence", 0) or 0),
            "prediction_explanation": row.get("prediction_explanation", "") or "",
            "recommendations": row.get("recommendations", "") or "",
            "cluster": int(row.get("cluster", -1) or -1),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        cur.execute(
            """
            INSERT INTO daily_reports
            (user_id, date, day, month, year, name, study_hours, sleep_hours, screen_time, mood,
             focus_score, stress_score, mood_score, sleep_display, productivity_score,
             prediction, prediction_confidence, prediction_explanation, recommendations,
             cluster, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (uid, *(payload[c] for c in REPORT_COLUMNS + ["created_at"])),
        )
        inserted += 1

    conn.commit()
    conn.close()
    return {"inserted": inserted, "skipped": skipped}


def bulk_import_test_results(rows: list[dict]) -> dict:
    inserted, skipped = 0, 0
    uid = current_user_id()
    conn = _connect()
    cur = conn.cursor()
    for row in rows:
        test_type = row.get("test_type")
        if not test_type:
            skipped += 1
            continue
        try:
            dt = pd.to_datetime(row.get("date")) if row.get("date") else datetime.now()
        except Exception:
            dt = datetime.now()
        cur.execute(
            """
            INSERT INTO test_results (user_id, date, test_type, score, accuracy, reaction_time_ms, duration_s, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                uid,
                dt.date().isoformat() if hasattr(dt, "date") else str(dt),
                test_type,
                float(row.get("score", 0) or 0),
                float(row["accuracy"]) if row.get("accuracy") not in (None, "") else None,
                float(row["reaction_time_ms"]) if row.get("reaction_time_ms") not in (None, "") else None,
                float(row["duration_s"]) if row.get("duration_s") not in (None, "") else None,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return {"inserted": inserted, "skipped": skipped}


# ---------------------------------------------------------------------------
# Focus Mode sessions
#   status: running -> paused -> running ... -> completed | ended | reset
#   Only ONE open (running/paused) session per (profile_type, profile_key).
#   Elapsed time is stored in the DB, so a Streamlit rerun/refresh recovers it.
# ---------------------------------------------------------------------------
_OPEN_STATES = ("running", "paused")
_FOCUS_UPDATABLE = {"label", "planned_seconds"}


def _now() -> datetime:
    return datetime.now()


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _norm_profile(profile_type, profile_key) -> tuple[str, str]:
    ptype = str(profile_type).strip() if profile_type is not None else ""
    if not ptype:
        raise ValueError("profile_type is required for Focus Mode")
    pkey = "" if profile_key is None else str(profile_key).strip()
    return ptype, pkey


def _live_elapsed(row: sqlite3.Row) -> float:
    """Stored elapsed + time since last resume (only while running)."""
    elapsed = float(row["elapsed_seconds"] or 0)
    if row["status"] == "running" and row["last_resumed_at"]:
        try:
            delta = (_now() - datetime.fromisoformat(row["last_resumed_at"])).total_seconds()
            elapsed += max(0.0, delta)
        except ValueError:
            pass
    return elapsed


def _focus_row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if row is None:
        return None
    d = dict(row)
    elapsed = _live_elapsed(row)
    planned = int(d["planned_seconds"])
    d["elapsed_seconds"] = min(elapsed, float(planned)) if d["status"] in _OPEN_STATES else float(d["elapsed_seconds"] or 0)
    d["remaining_seconds"] = max(0, int(round(planned - elapsed))) if d["status"] in _OPEN_STATES else 0
    return d


def _fetch_open_row(conn: sqlite3.Connection, uid: int, ptype: str, pkey: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM focus_sessions
        WHERE user_id = ? AND profile_type = ? AND profile_key = ? AND status IN ('running','paused')
        ORDER BY id DESC LIMIT 1
        """,
        (uid, ptype, pkey),
    ).fetchone()


def _close_row(conn: sqlite3.Connection, row: sqlite3.Row, status: str) -> None:
    elapsed = _live_elapsed(row)
    if status == "completed":
        elapsed = float(row["planned_seconds"])
    conn.execute(
        """
        UPDATE focus_sessions
        SET status = ?, elapsed_seconds = ?, last_resumed_at = NULL, ended_at = ?
        WHERE id = ?
        """,
        (status, elapsed, _iso(_now()), row["id"]),
    )


def get_open_focus_session(profile_type: str, profile_key: Optional[str] = "") -> Optional[dict]:
    """Return the active (running/paused) session for this profile, or None.

    A running session whose time has run out is auto-completed and None is
    returned, so the UI never shows a stuck 00:00 timer after a refresh."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    conn = _connect()
    try:
        row = _fetch_open_row(conn, uid, ptype, pkey)
        if row is None:
            return None
        if row["status"] == "running" and _live_elapsed(row) >= float(row["planned_seconds"]):
            _close_row(conn, row, "completed")
            conn.commit()
            return None
        return _focus_row_to_dict(row)
    finally:
        conn.close()


def create_focus_session(
    profile_type: str,
    profile_key: Optional[str] = "",
    duration_minutes: float = 25,
    label: Optional[str] = None,
) -> dict:
    """Start a session. If one is already open for this profile it is returned
    as-is (no duplicates on rerun / double-click)."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    planned = int(round(float(duration_minutes) * 60))
    if planned <= 0:
        raise ValueError("duration_minutes must be greater than 0")
    existing = get_open_focus_session(ptype, pkey)
    if existing is not None:
        return existing
    now = _now()
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO focus_sessions
              (user_id, profile_type, profile_key, label, planned_seconds, elapsed_seconds, status,
               date, started_at, last_resumed_at, created_at)
            VALUES (?,?,?,?,?,0,'running',?,?,?,?)
            """,
            (uid, ptype, pkey, label, planned, now.date().isoformat(), _iso(now), now.isoformat(), _iso(now)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM focus_sessions WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _focus_row_to_dict(row)
    finally:
        conn.close()


def pause_focus_session(profile_type: str, profile_key: Optional[str] = "") -> Optional[dict]:
    """Freeze elapsed time. No-op (returns current state) if not running."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    conn = _connect()
    try:
        row = _fetch_open_row(conn, uid, ptype, pkey)
        if row is None:
            return None
        if row["status"] == "running":
            conn.execute(
                "UPDATE focus_sessions SET status='paused', elapsed_seconds=?, last_resumed_at=NULL, "
                "pause_count = pause_count + 1 WHERE id=? AND user_id=?",
                (_live_elapsed(row), row["id"], uid),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM focus_sessions WHERE id = ?", (row["id"],)).fetchone()
        return _focus_row_to_dict(row)
    finally:
        conn.close()


def resume_focus_session(profile_type: str, profile_key: Optional[str] = "") -> Optional[dict]:
    """Continue a paused session. No-op (returns current state) if already running."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    conn = _connect()
    try:
        row = _fetch_open_row(conn, uid, ptype, pkey)
        if row is None:
            return None
        if row["status"] == "paused":
            conn.execute(
                "UPDATE focus_sessions SET status='running', last_resumed_at=? WHERE id=? AND user_id=?",
                (_now().isoformat(), row["id"], uid),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM focus_sessions WHERE id = ?", (row["id"],)).fetchone()
        return _focus_row_to_dict(row)
    finally:
        conn.close()


def complete_focus_session(profile_type: str, profile_key: Optional[str] = "") -> Optional[dict]:
    """Timer finished: mark completed (counts fully toward stats and streak)."""
    return _finish_open_session(profile_type, profile_key, "completed")


def end_focus_session(profile_type: str, profile_key: Optional[str] = "") -> Optional[dict]:
    """User stopped early: keep the time actually focused, status 'ended'."""
    return _finish_open_session(profile_type, profile_key, "ended")


def reset_focus_session(profile_type: str, profile_key: Optional[str] = "") -> Optional[dict]:
    """Discard the open session (status 'reset'); it is excluded from stats/history."""
    return _finish_open_session(profile_type, profile_key, "reset")


def _finish_open_session(profile_type, profile_key, status: str) -> Optional[dict]:
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    conn = _connect()
    try:
        row = _fetch_open_row(conn, uid, ptype, pkey)
        if row is None:
            return None  # already completed / nothing open: safe no-op
        _close_row(conn, row, status)
        conn.commit()
        return dict(conn.execute("SELECT * FROM focus_sessions WHERE id = ?", (row["id"],)).fetchone())
    finally:
        conn.close()


def update_focus_session(session_id: int, **fields: Any) -> bool:
    """Update editable metadata (label, planned_seconds) of an OPEN session."""
    data = {k: v for k, v in fields.items() if k in _FOCUS_UPDATABLE}
    if not data:
        return False
    if "planned_seconds" in data and int(data["planned_seconds"]) <= 0:
        raise ValueError("planned_seconds must be greater than 0")
    sets = ", ".join(f"{k} = ?" for k in data)
    conn = _connect()
    try:
        cur = conn.execute(
            f"UPDATE focus_sessions SET {sets} WHERE id = ? AND user_id = ? AND status IN ('running','paused')",
            (*data.values(), int(session_id), current_user_id()),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_focus_history(profile_type: str, profile_key: Optional[str] = "", limit: int = 50) -> pd.DataFrame:
    """Finished sessions (completed/ended), newest first. Empty DataFrame if none."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    conn = _connect()
    try:
        df = pd.read_sql_query(
            """
            SELECT * FROM focus_sessions
            WHERE user_id = ? AND profile_type = ? AND profile_key = ? AND status IN ('completed','ended')
            ORDER BY started_at DESC LIMIT ?
            """,
            conn,
            params=(uid, ptype, pkey, int(limit)),
        )
    finally:
        conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df["focused_minutes"] = (df["elapsed_seconds"] / 60.0).round(1)
    return df


def get_daily_focus_stats(profile_type: str, profile_key: Optional[str] = "", days: int = 30) -> pd.DataFrame:
    """Per-day totals: date, sessions, completed, focused_minutes."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    since = (_now().date().toordinal() - int(days) + 1)
    since_iso = date_cls.fromordinal(since).isoformat()
    conn = _connect()
    try:
        df = pd.read_sql_query(
            """
            SELECT date,
                   COUNT(*) AS sessions,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                   ROUND(SUM(elapsed_seconds) / 60.0, 1) AS focused_minutes
            FROM focus_sessions
            WHERE user_id = ? AND profile_type = ? AND profile_key = ?
              AND status IN ('completed','ended') AND date >= ?
            GROUP BY date ORDER BY date
            """,
            conn,
            params=(uid, ptype, pkey, since_iso),
        )
    finally:
        conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_focus_streak(profile_type: str, profile_key: Optional[str] = "") -> int:
    """Consecutive days with >=1 COMPLETED session, ending today (or yesterday,
    so the streak isn't shown as broken before today's first session)."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT date FROM focus_sessions
            WHERE user_id = ? AND profile_type = ? AND profile_key = ? AND status = 'completed'
            """,
            (uid, ptype, pkey),
        ).fetchall()
    finally:
        conn.close()
    days = set()
    for r in rows:
        try:
            days.add(date_cls.fromisoformat(r["date"]).toordinal())
        except (ValueError, TypeError):
            continue
    if not days:
        return 0
    cursor = _now().date().toordinal()
    if cursor not in days:
        cursor -= 1
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= 1
    return streak


DEFAULT_DAILY_TARGET_MINUTES = 120  # used only until the user saves their own target


def get_focus_daily_target(profile_type: str, profile_key: Optional[str] = "") -> int:
    """Saved daily focus target in minutes (default 120 until the user sets one)."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT daily_target_minutes FROM focus_settings WHERE user_id = ? AND profile_type = ? AND profile_key = ?",
            (uid, ptype, pkey),
        ).fetchone()
    finally:
        conn.close()
    return int(row["daily_target_minutes"]) if row else DEFAULT_DAILY_TARGET_MINUTES


def set_focus_daily_target(profile_type: str, profile_key: Optional[str], minutes: int) -> int:
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    minutes = int(minutes)
    if not 1 <= minutes <= 24 * 60:
        raise ValueError("daily target must be between 1 minute and 24 hours")
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO focus_settings (user_id, profile_type, profile_key, daily_target_minutes, updated_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(user_id, profile_type, profile_key)
            DO UPDATE SET daily_target_minutes=excluded.daily_target_minutes, updated_at=excluded.updated_at
            """,
            (uid, ptype, pkey, minutes, _iso(_now())),
        )
        conn.commit()
    finally:
        conn.close()
    return minutes


def get_focus_day_summary(profile_type: str, profile_key: Optional[str] = "", day: Optional[str] = None) -> dict:
    """Target / focused / remaining / progress for one day (default: today).
    Focused time = real elapsed time of finished (completed + ended) sessions."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    day = day or _now().date().isoformat()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(elapsed_seconds), 0) AS secs,
                   COALESCE(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END), 0) AS completed,
                   COUNT(*) AS finished
            FROM focus_sessions
            WHERE user_id = ? AND profile_type = ? AND profile_key = ? AND status IN ('completed','ended') AND date=?
            """,
            (uid, ptype, pkey, day),
        ).fetchone()
    finally:
        conn.close()
    target = get_focus_daily_target(ptype, pkey)
    focused = int(round(float(row["secs"]) / 60.0))
    return {
        "date": day,
        "target_minutes": target,
        "focused_minutes": focused,
        "remaining_minutes": max(0, target - focused),
        "progress_pct": round(100.0 * focused / target, 1) if target else 0.0,
        "sessions_completed": int(row["completed"]),
        "sessions_finished": int(row["finished"]),
    }


def focus_session_quality(planned_seconds, elapsed_seconds, status: str, pause_count: int = 0) -> int:
    """0-100 quality of ONE session: 70 pts for the share of the planned time
    actually focused, +15 if it ran to completion, +15 minus 5 per pause (min 0)."""
    planned = float(planned_seconds or 0)
    ratio = min(1.0, float(elapsed_seconds or 0) / planned) if planned > 0 else 0.0
    points = 70 * ratio + (15 if status == "completed" else 0) + max(0, 15 - 5 * int(pause_count or 0))
    return int(round(points))


def get_focus_score(profile_type: str, profile_key: Optional[str] = "", days: int = 7) -> dict:
    """Deterministic Focus Score (0-100) from real sessions in the last `days` days:
       Volume       40  focused time vs (daily target x days)
       Completion   30  completed sessions / finished sessions
       Steadiness   15  fewer pauses per session is better (3+ average = 0)
       Consistency  15  current focus streak, capped at 7 days
    Returns 0 with sessions=0 when there is no data yet."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    since_iso = date_cls.fromordinal(_now().date().toordinal() - int(days) + 1).isoformat()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS finished,
                   COALESCE(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END), 0) AS completed,
                   COALESCE(SUM(elapsed_seconds), 0) AS secs,
                   COALESCE(AVG(pause_count), 0) AS avg_pauses
            FROM focus_sessions
            WHERE user_id = ? AND profile_type = ? AND profile_key = ? AND status IN ('completed','ended') AND date>=?
            """,
            (uid, ptype, pkey, since_iso),
        ).fetchone()
    finally:
        conn.close()
    finished = int(row["finished"])
    streak = get_focus_streak(ptype, pkey)
    result = {"score": 0, "volume": 0.0, "completion": 0.0, "steadiness": 0.0, "consistency": 0.0,
              "sessions": finished, "completed": int(row["completed"]), "streak": streak, "days": int(days)}
    if finished == 0:
        return result
    target = get_focus_daily_target(ptype, pkey)
    focused_min = float(row["secs"]) / 60.0
    result["volume"] = round(40 * min(1.0, focused_min / (target * days)), 1)
    result["completion"] = round(30 * int(row["completed"]) / finished, 1)
    result["steadiness"] = round(15 * (1 - min(1.0, float(row["avg_pauses"]) / 3.0)), 1)
    result["consistency"] = round(15 * min(streak, 7) / 7.0, 1)
    result["score"] = int(round(result["volume"] + result["completion"] + result["steadiness"] + result["consistency"]))
    return result


def get_last_finished_focus_session(profile_type: str, profile_key: Optional[str] = "") -> Optional[dict]:
    """Most recently finished (completed/ended) session, or None. Used for the break banner."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT * FROM focus_sessions
            WHERE user_id = ? AND profile_type = ? AND profile_key = ? AND status IN ('completed','ended')
            ORDER BY ended_at DESC, id DESC LIMIT 1
            """,
            (uid, ptype, pkey),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_focus_totals(profile_type: str, profile_key: Optional[str] = "") -> dict:
    """All-time totals over finished sessions (for the Focus History summary)."""
    ptype, pkey = _norm_profile(profile_type, profile_key)
    uid = current_user_id()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS finished,
                   COALESCE(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END), 0) AS completed,
                   COALESCE(SUM(elapsed_seconds), 0) AS secs
            FROM focus_sessions
            WHERE user_id = ? AND profile_type = ? AND profile_key = ? AND status IN ('completed','ended')
            """,
            (uid, ptype, pkey),
        ).fetchone()
    finally:
        conn.close()
    finished = int(row["finished"])
    total_min = float(row["secs"]) / 60.0
    return {
        "finished": finished,
        "completed": int(row["completed"]),
        "total_minutes": round(total_min, 1),
        "avg_minutes": round(total_min / finished, 1) if finished else 0.0,
    }


init_db()
