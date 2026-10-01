"""
FutureForge — Authentication core (framework-independent, no Streamlit import).

* Passwords: salted scrypt (stdlib hashlib) — no raw passwords are ever stored or logged.
  Hash format:  scrypt$<n>$<r>$<p>$<salt_hex>$<hash_hex>   (parameters are stored per hash,
  so they can be raised later without invalidating existing accounts).
* Sessions: an opaque random token is handed to the browser session; only its SHA-256 is stored
  in `user_sessions`, with an expiry. Logout revokes it server-side.
* Brute force: 5 consecutive failures for an e-mail lock that e-mail for 60 seconds.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from core import db

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1
SESSION_HOURS = 12
MAX_FAILURES, LOCKOUT_SECONDS = 5, 60

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_fail_lock = threading.Lock()
_failures: dict[str, tuple[int, float]] = {}   # email -> (count, first_failure_ts)


# --------------------------------------------------------------------------- hashing
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32,
                        maxmem=64 * 1024 * 1024)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p),
                            dklen=len(bytes.fromhex(hash_hex)), maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(dk, bytes.fromhex(hash_hex))
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


# --------------------------------------------------------------------------- validation
def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_password(password: str) -> Optional[str]:
    """Return an error message, or None if the password is acceptable."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    if password.lower() in {"password1", "12345678a", "qwerty123", "password123", "abcd1234"}:
        return "That password is too common — please choose a stronger one."
    return None


def validate_signup(name: str, email: str, password: str, confirm: str) -> Optional[str]:
    if not (name or "").strip() or not (email or "").strip() or not password or not confirm:
        return "Please fill in all fields."
    if len(name.strip()) > 80:
        return "Name is too long (max 80 characters)."
    if not _EMAIL_RE.match(normalize_email(email)):
        return "Please enter a valid email address."
    if password != confirm:
        return "Passwords do not match."
    return validate_password(password)


# --------------------------------------------------------------------------- accounts
def register_user(name: str, email: str, password: str, confirm: str) -> tuple[Optional[dict], Optional[str]]:
    """Create an account. Returns (user, None) or (None, error message)."""
    err = validate_signup(name, email, password, confirm)
    if err:
        return None, err
    email_n = normalize_email(email)
    conn = db._connect()
    try:
        is_first = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?,?,?,?)",
                (name.strip(), email_n, hash_password(password), datetime.now().isoformat(timespec="seconds")),
            )
        except sqlite3.IntegrityError:
            return None, "An account with this email already exists."
        uid = cur.lastrowid
        if is_first:  # keep the pre-accounts single-user history: the first account inherits it
            db.claim_legacy_rows(conn, uid)
        conn.commit()
        return {"id": uid, "name": name.strip(), "email": email_n}, None
    finally:
        conn.close()


def _locked(email: str) -> int:
    """Seconds remaining on a lockout, else 0."""
    with _fail_lock:
        count, first = _failures.get(email, (0, 0.0))
        if count >= MAX_FAILURES:
            remaining = int(LOCKOUT_SECONDS - (time.time() - first))
            if remaining > 0:
                return remaining
            _failures.pop(email, None)
    return 0


def _record_failure(email: str) -> None:
    with _fail_lock:
        count, first = _failures.get(email, (0, time.time()))
        _failures[email] = (count + 1, first if count else time.time())


def authenticate(email: str, password: str) -> tuple[Optional[dict], Optional[str]]:
    email_n = normalize_email(email)
    if not email_n or not password:
        return None, "Please enter your email and password."
    wait = _locked(email_n)
    if wait:
        return None, f"Too many failed attempts. Try again in {wait} seconds."
    conn = db._connect()
    try:
        row = conn.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?", (email_n,)).fetchone()
        ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)
        if not row or not ok:
            _record_failure(email_n)
            return None, "Incorrect email or password."
        with _fail_lock:
            _failures.pop(email_n, None)
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?",
                     (datetime.now().isoformat(timespec="seconds"), row["id"]))
        conn.commit()
        return {"id": row["id"], "name": row["name"], "email": row["email"]}, None
    finally:
        conn.close()


# --------------------------------------------------------------------------- sessions
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    conn = db._connect()
    try:
        conn.execute(
            "INSERT INTO user_sessions (user_id, token_hash, created_at, expires_at) VALUES (?,?,?,?)",
            (user_id, _token_hash(token), now.isoformat(timespec="seconds"),
             (now + timedelta(hours=SESSION_HOURS)).isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def validate_session(token: Optional[str]) -> Optional[dict]:
    """Return the user for a live (unexpired, unrevoked) session token, else None."""
    if not token:
        return None
    conn = db._connect()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.name, u.email, u.created_at
            FROM user_sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
            """,
            (_token_hash(token), datetime.now().isoformat(timespec="seconds")),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def revoke_session(token: Optional[str]) -> None:
    if not token:
        return
    conn = db._connect()
    try:
        conn.execute("UPDATE user_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                     (datetime.now().isoformat(timespec="seconds"), _token_hash(token)))
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- profile
def update_name(user_id: int, name: str) -> Optional[str]:
    name = (name or "").strip()
    if not name:
        return "Name cannot be empty."
    if len(name) > 80:
        return "Name is too long (max 80 characters)."
    conn = db._connect()
    try:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))
        conn.commit()
    finally:
        conn.close()
    return None


def change_password(user_id: int, current: str, new: str, confirm: str) -> Optional[str]:
    conn = db._connect()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row or not verify_password(current, row["password_hash"]):
            return "Current password is incorrect."
        if new != confirm:
            return "New passwords do not match."
        err = validate_password(new)
        if err:
            return err
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user_id))
        conn.commit()
    finally:
        conn.close()
    return None
