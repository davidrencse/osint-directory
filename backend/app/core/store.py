"""Tiny SQLite store for the TTL cache, audit log and scope allowlist.

sqlite3 is synchronous; calls are small and wrapped with asyncio.to_thread by callers
that sit on hot async paths.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.config import DATA_DIR

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expires REAL);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, target TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS scope (entry TEXT PRIMARY KEY);
"""

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_writes_since_purge = 0
_PURGE_EVERY = 50  # cache writes between sweeps of expired rows


def _open(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(_SCHEMA)
    # Expired rows are otherwise never removed, so the file grows with every distinct target.
    conn.execute("DELETE FROM cache WHERE expires < ?", (time.time(),))
    conn.commit()
    return conn


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conn = _open(DATA_DIR / "osint.db")
    return _conn


def use_database(path: Path) -> None:
    """Point the store at a different file (used by tests)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = _open(path)


# --- cache -------------------------------------------------------------------

def cache_get(key: str) -> Any | None:
    with _lock:
        row = _db().execute("SELECT value, expires FROM cache WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    value, expires = row
    if expires < time.time():
        return None
    return json.loads(value)


def cache_set(key: str, value: Any, ttl_s: float) -> None:
    global _writes_since_purge
    now = time.time()
    with _lock:
        db = _db()
        db.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires) VALUES (?, ?, ?)",
            (key, json.dumps(value, default=str), now + ttl_s),
        )
        _writes_since_purge += 1
        if _writes_since_purge >= _PURGE_EVERY:
            db.execute("DELETE FROM cache WHERE expires < ?", (now,))
            _writes_since_purge = 0
        db.commit()


def cache_clear() -> int:
    with _lock:
        n = _db().execute("DELETE FROM cache").rowcount
        _db().commit()
    return n


# --- audit -------------------------------------------------------------------

def audit(kind: str, target: str, detail: dict | None = None) -> None:
    with _lock:
        _db().execute(
            "INSERT INTO audit (ts, kind, target, detail) VALUES (?, ?, ?, ?)",
            (time.time(), kind, target, json.dumps(detail or {})),
        )
        _db().commit()


def audit_list(limit: int = 200) -> list[dict]:
    with _lock:
        rows = _db().execute(
            "SELECT ts, kind, target, detail FROM audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"ts": ts, "kind": k, "target": t, "detail": json.loads(d)} for ts, k, t, d in rows]


# --- scope allowlist -----------------------------------------------------------

def scope_list() -> list[str]:
    with _lock:
        return [r[0] for r in _db().execute("SELECT entry FROM scope ORDER BY entry").fetchall()]


def scope_replace(entries: list[str]) -> list[str]:
    cleaned = sorted({e.strip().lower() for e in entries if e.strip()})
    with _lock:
        db = _db()
        db.execute("DELETE FROM scope")
        db.executemany("INSERT INTO scope (entry) VALUES (?)", [(e,) for e in cleaned])
        db.commit()
    return cleaned
