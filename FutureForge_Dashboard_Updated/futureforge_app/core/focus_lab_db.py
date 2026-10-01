"""
Focus Lab storage — same SQLite database as the rest of FutureForge (no second DB), additive tables only.

  focus_lab_recommendations   one row per "risk detected -> test recommended" (status: pending | completed)
  focus_lab_results           one row per completed test (answers as option indices, score, category, actions)

Every query is scoped to the logged-in user via db.current_user_id() and FAILS CLOSED when nobody is logged in.
Answers are stored only as option indices (0-3); no free text, no personal data.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import pandas as pd

from core import db

_SQL = (
    """CREATE TABLE IF NOT EXISTS focus_lab_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        domain TEXT NOT NULL,
        prediction_id INTEGER,              -- predictions.id (domains) / daily_reports.id (student); NULL if not saved
        risk_type TEXT NOT NULL,
        risk_level TEXT,
        recommended_test TEXT NOT NULL,
        test_status TEXT NOT NULL DEFAULT 'pending',
        test_score REAL,
        created_at TEXT NOT NULL,
        completed_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS focus_lab_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        recommendation_id INTEGER REFERENCES focus_lab_recommendations(id) ON DELETE SET NULL,
        test_id TEXT NOT NULL,
        domain TEXT,
        prediction_id INTEGER,
        answers TEXT NOT NULL,
        score REAL NOT NULL,
        category TEXT NOT NULL,
        recommendations TEXT,
        created_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_fl_rec_user ON focus_lab_recommendations (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_fl_res_user ON focus_lab_results (user_id, test_id, created_at)",
)


def _conn():
    conn = db._connect()
    for stmt in _SQL:
        conn.execute(stmt)
    return conn


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_recommendation(domain: str, prediction_id: Optional[int], risk_type: str, risk_level: str, test_id: str) -> int:
    """Store a recommendation. Re-uses an existing PENDING row for the same user/domain/prediction/risk/test."""
    uid = db.current_user_id()
    conn = _conn()
    try:
        row = conn.execute(
            """SELECT id FROM focus_lab_recommendations WHERE user_id=? AND domain=? AND recommended_test=? AND risk_type=?
               AND test_status='pending' AND COALESCE(prediction_id,-1)=COALESCE(?,-1) ORDER BY id DESC LIMIT 1""",
            (uid, domain, test_id, risk_type, prediction_id)).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            """INSERT INTO focus_lab_recommendations (user_id, domain, prediction_id, risk_type, risk_level, recommended_test, created_at)
               VALUES (?,?,?,?,?,?,?)""", (uid, domain, prediction_id, risk_type, risk_level, test_id, _now()))
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def get_recommendation(rec_id: int) -> Optional[dict]:
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM focus_lab_recommendations WHERE id=? AND user_id=?", (rec_id, db.current_user_id())).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_result(result: dict, *, domain: Optional[str] = None, prediction_id: Optional[int] = None,
                recommendation_id: Optional[int] = None) -> int:
    """Persist a scored test (dict from services.focus_lab.test_engine.submit). Completes the linked recommendation."""
    uid = db.current_user_id()
    conn = _conn()
    try:
        if recommendation_id is not None:       # only link a recommendation that belongs to this user AND is for this test
            row = conn.execute("SELECT recommended_test FROM focus_lab_recommendations WHERE id=? AND user_id=?",
                               (recommendation_id, uid)).fetchone()
            if not row or row["recommended_test"] != result["test_id"]:
                recommendation_id = None
        cur = conn.execute(
            """INSERT INTO focus_lab_results (user_id, recommendation_id, test_id, domain, prediction_id, answers, score, category,
               recommendations, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (uid, recommendation_id, result["test_id"], domain, prediction_id, json.dumps(result["answers"]), result["score"],
             result["category"], json.dumps(result["actions"]), _now()))
        if recommendation_id is not None:
            conn.execute("UPDATE focus_lab_recommendations SET test_status='completed', test_score=?, completed_at=? WHERE id=? AND user_id=?",
                         (result["score"], _now(), recommendation_id, uid))
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_results(limit: Optional[int] = None) -> pd.DataFrame:
    conn = _conn()
    try:
        sql = "SELECT * FROM focus_lab_results WHERE user_id=? ORDER BY created_at DESC, id DESC" + (f" LIMIT {int(limit)}" if limit else "")
        return pd.read_sql_query(sql, conn, params=(db.current_user_id(),))
    finally:
        conn.close()


def list_recommendations(limit: Optional[int] = None) -> pd.DataFrame:
    conn = _conn()
    try:
        sql = "SELECT * FROM focus_lab_recommendations WHERE user_id=? ORDER BY created_at DESC, id DESC" + (f" LIMIT {int(limit)}" if limit else "")
        return pd.read_sql_query(sql, conn, params=(db.current_user_id(),))
    finally:
        conn.close()
