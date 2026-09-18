"""SQLite-backed usage counters for the guest preview budgets.

Guest accounts can call the LLM-backed routes, so each guest gets a fixed
per-session budget per action and all guests share a daily budget. Counters
live in a small table so they hold across gunicorn workers and restarts
without a new dependency.

Only guests are metered; registered users are unchanged.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from config import ensure_dotenv_loaded

ensure_dotenv_loaded()

# Per guest session (24 h). The explain budget is the largest because the
# exercise page requests a brief explanation automatically after every miss.
GUEST_ACTION_LIMITS: dict[str, int] = {
    "submit": 200,
    "explain": 40,
    "explain_detailed": 15,
    "chat": 30,
    "daily_review": 3,
    "translate": 80,
    "tts": 40,
    "video_comprehension": 5,
    "video_comprehension_check": 20,
}

# Actions that reach a paid API and therefore count against the shared budget.
LLM_ACTIONS = frozenset(GUEST_ACTION_LIMITS) - {"submit"}

GUEST_DAILY_BUDGET = int(os.getenv("SHIORI_GUEST_DAILY_BUDGET", "1500"))
GUEST_CREATES_PER_IP_PER_HOUR = int(os.getenv("SHIORI_GUEST_CREATES_PER_IP_PER_HOUR", "10"))
GUEST_MAX_ACTIVE = int(os.getenv("SHIORI_GUEST_MAX_ACTIVE", "300"))

SESSION_WINDOW = "session"


def ensure_usage_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_counters (
            subject TEXT NOT NULL,
            action TEXT NOT NULL,
            window_start TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (subject, action, window_start)
        )
        """
    )
    conn.commit()


def window_key(kind: str, now: datetime | None = None) -> str:
    """Bucket key for a time window: ``hour``, ``day`` or ``session`` (no expiry)."""
    if kind == SESSION_WINDOW:
        return SESSION_WINDOW
    moment = now or datetime.now()
    if kind == "hour":
        return moment.strftime("%Y-%m-%dT%H")
    if kind == "day":
        return moment.strftime("%Y-%m-%d")
    raise ValueError(f"Unknown window kind: {kind}")


def consume(conn: sqlite3.Connection, subject: str, action: str, limit: int, window_start: str) -> tuple[bool, int]:
    """Count one use and report whether it stayed within ``limit``.

    The increment always happens (an over-limit call is still recorded), so
    the returned count is the total including this call.
    """
    conn.execute(
        "INSERT OR IGNORE INTO usage_counters (subject, action, window_start, count) VALUES (?, ?, ?, 0)",
        (subject, action, window_start),
    )
    conn.execute(
        "UPDATE usage_counters SET count = count + 1 WHERE subject = ? AND action = ? AND window_start = ?",
        (subject, action, window_start),
    )
    row = conn.execute(
        "SELECT count FROM usage_counters WHERE subject = ? AND action = ? AND window_start = ?",
        (subject, action, window_start),
    ).fetchone()
    conn.commit()
    count = int(row[0]) if row else 0
    return count <= limit, count


def guest_creation_limits() -> tuple[int, int]:
    """(guest sessions per IP per hour, maximum concurrently active guests)."""
    return GUEST_CREATES_PER_IP_PER_HOUR, GUEST_MAX_ACTIVE


def check_guest_action(conn: sqlite3.Connection, user_id: str, action: str, now: datetime | None = None) -> str | None:
    """Meter one guest action. Returns ``None`` when allowed, else an error code.

    ``preview_limit``: this guest used up the per-session budget for ``action``.
    ``preview_busy``: the shared daily budget across all guests is exhausted.
    """
    limit = GUEST_ACTION_LIMITS.get(action)
    if limit is not None:
        allowed, _ = consume(conn, f"guest:{user_id}", action, limit, SESSION_WINDOW)
        if not allowed:
            return "preview_limit"

    if action in LLM_ACTIONS:
        allowed, _ = consume(conn, "guests:all", "llm", GUEST_DAILY_BUDGET, window_key("day", now))
        if not allowed:
            return "preview_busy"

    return None
