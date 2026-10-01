"""
FutureForge — prediction storage & unified history (every query is scoped to the logged-in user).

New domains write to `predictions`. Student Productivity keeps using the existing `daily_reports` table
(untouched save flow); the unified history simply reads BOTH, so nothing is duplicated or migrated.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import pandas as pd

from core import db
from services.base import PredictionResult, risk_from_score
from services.registry import BY_KEY

_STUDENT_RISK = {"High Focus Potential": "low", "Moderate Focus Potential": "medium", "Focus At Risk": "high"}
COLUMNS = ["id", "source_table", "created_at", "domain", "domain_title", "score", "risk", "confidence", "pattern", "source"]


def save_prediction(domain: str, inputs: dict, result: PredictionResult) -> int:
    if domain not in BY_KEY or domain == "student":
        raise ValueError(f"Unknown or non-stored domain: {domain}")
    details = {"extras": result.extras, "insights": result.insights, "recommendations": result.recommendations,
               "suitability": result.suitability, "model_version": result.model_version}
    conn = db._connect()
    try:
        cur = conn.execute(
            """INSERT INTO predictions
               (user_id, domain, input_data, prediction, risk, confidence, behavioral_pattern, source, details, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (db.current_user_id(), domain, json.dumps(inputs), result.score, result.risk, result.confidence,
             result.pattern, result.source, json.dumps(details), datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _domain_frame(domain: str) -> pd.DataFrame:
    conn = db._connect()
    try:
        df = pd.read_sql_query(
            """SELECT id, created_at, domain, prediction AS score, risk, confidence,
                      behavioral_pattern AS pattern, source, input_data, details
               FROM predictions WHERE user_id = ? AND domain = ? ORDER BY created_at ASC, id ASC""",
            conn, params=(db.current_user_id(), domain))
    finally:
        conn.close()
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["details"] = df["details"].map(lambda x: json.loads(x) if x else {})
        df["input_data"] = df["input_data"].map(lambda x: json.loads(x) if x else {})
    return df


def domain_history(domain: str) -> pd.DataFrame:
    """Oldest -> newest history for one domain, for the current user."""
    if domain == "student":
        conn = db._connect()
        try:
            df = pd.read_sql_query(
                """SELECT id, created_at, focus_score AS score, prediction, prediction_confidence AS confidence, cluster
                   FROM daily_reports WHERE user_id = ? ORDER BY created_at ASC, id ASC""",
                conn, params=(db.current_user_id(),))
        finally:
            conn.close()
        if df.empty:
            return df
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["domain"] = "student"
        df["risk"] = [_STUDENT_RISK.get(p, risk_from_score(sc)) for p, sc in zip(df["prediction"], df["score"])]
        df["pattern"] = df["cluster"].map(lambda c: f"Behavioral cluster #{int(c)}" if pd.notna(c) and int(c) >= 0 else "—")
        df["source"] = "ml_model"
        return df.drop(columns=["prediction", "cluster"])
    return _domain_frame(domain)


def unified_history(limit: Optional[int] = None) -> pd.DataFrame:
    """All predictions across all domains for the current user, newest first."""
    frames = []
    for key in BY_KEY:
        df = domain_history(key)
        if df.empty:
            continue
        df = df.copy()
        df["domain"] = key
        df["domain_title"] = BY_KEY[key].title
        df["source_table"] = "daily_reports" if key == "student" else "predictions"
        frames.append(df[["id", "source_table", "created_at", "domain", "domain_title", "score", "risk",
                          "confidence", "pattern", "source"]])
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    out = pd.concat(frames, ignore_index=True).sort_values("created_at", ascending=False)
    return out.head(limit) if limit else out


def delete_prediction(pred_id: int) -> bool:
    conn = db._connect()
    try:
        cur = conn.execute("DELETE FROM predictions WHERE id = ? AND user_id = ?", (int(pred_id), db.current_user_id()))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def overview_stats() -> dict:
    h = unified_history()
    if h.empty:
        return {"total": 0, "latest": None, "avg_score": None, "current_risk": None, "active_domain": None, "recent": h}
    latest = h.iloc[0]
    return {"total": int(len(h)), "latest": latest.to_dict(), "avg_score": round(float(h["score"].mean()), 1),
            "current_risk": latest["risk"], "active_domain": latest["domain_title"], "recent": h.head(6)}


def linear_trend(scores: list[float], min_points: int = 3) -> Optional[dict]:
    """Direction of the user's own recent scores (least-squares slope). None if too little history.
    A description of past data, not a model forecast."""
    if len(scores) < min_points:
        return None
    import numpy as np
    y = np.array(scores[-10:], dtype=float)
    slope = float(np.polyfit(np.arange(len(y)), y, 1)[0])
    direction = "improving" if slope > 0.5 else "declining" if slope < -0.5 else "stable"
    return {"slope": round(slope, 2), "direction": direction, "n": len(y)}


# ---- per-user preferences ---------------------------------------------------
def set_pref(key: str, value: str) -> None:
    conn = db._connect()
    try:
        conn.execute(
            """INSERT INTO user_preferences (user_id, pref_key, pref_value, updated_at) VALUES (?,?,?,?)
               ON CONFLICT(user_id, pref_key) DO UPDATE SET pref_value=excluded.pref_value, updated_at=excluded.updated_at""",
            (db.current_user_id(), key, value, datetime.now().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()


def get_pref(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = db._connect()
    try:
        row = conn.execute("SELECT pref_value FROM user_preferences WHERE user_id=? AND pref_key=?",
                           (db.current_user_id(), key)).fetchone()
    finally:
        conn.close()
    return row["pref_value"] if row else default
