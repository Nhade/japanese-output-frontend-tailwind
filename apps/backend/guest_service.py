"""Guest preview sessions.

A guest is a real row in ``users`` flagged ``is_guest = 1``, so every existing
route (answer log, learner profile, statistics, daily review) works unchanged.
What differs from a registered account:

* no usable password — a random secret is hashed, so login can never succeed;
* a short session (``guest_expires_at``), checked on every authenticated call;
* optional sample history, flagged ``answer_log.is_sample = 1`` so the review
  pages have content within seconds of arriving, and dropped again if the
  guest registers;
* automatic purge of guests older than the retention window.

The sample history is curated in ``guest_seed.json``: real exercises from the
bank with plausible wrong answers, grader-style feedback, and timestamps
relative to "now" (a few misses land today so the daily-review agent, which
only reads today's mistakes, has something to write about).
"""
from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from pwdlib import PasswordHash

from learner_service import backfill_learner_profile, get_learner_profile
from usage_limits import ensure_usage_table

logger = logging.getLogger(__name__)

GUEST_SESSION_HOURS = 24
GUEST_RETENTION_DAYS = 7
GUEST_USERNAME_PREFIX = "guest-"
SEED_PATH = Path(__file__).resolve().parent / "guest_seed.json"

_password_hash = PasswordHash.recommended()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def ensure_guest_schema(conn: sqlite3.Connection) -> None:
    """Idempotent startup safety net; ``scripts/migrate_db.py`` (004) is the versioned path."""
    if _table_exists(conn, "users"):
        cols = _columns(conn, "users")
        if "is_guest" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_guest INTEGER NOT NULL DEFAULT 0")
        if "guest_expires_at" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN guest_expires_at TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_guest_created ON users(is_guest, created_timestamp)")
    if _table_exists(conn, "answer_log") and "is_sample" not in _columns(conn, "answer_log"):
        conn.execute("ALTER TABLE answer_log ADD COLUMN is_sample INTEGER NOT NULL DEFAULT 0")
    ensure_usage_table(conn)
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now(now: datetime | None) -> datetime:
    return now or datetime.now()


def guest_session_expired(expires_at: str | None, now: datetime | None = None) -> bool:
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(expires_at) <= _now(now)
    except ValueError:
        return True


def load_seed_entries(path: Path = SEED_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["entries"]


def _seed_timestamp(now: datetime, entry: dict) -> datetime:
    if "minutes_ago" in entry:
        return now - timedelta(minutes=int(entry["minutes_ago"]))
    day = now - timedelta(days=int(entry["days_ago"]))
    moment = day.replace(hour=int(entry.get("hour", 20)), minute=int(entry.get("minute", 0)), second=0, microsecond=0)
    # Never write a timestamp in the future (e.g. a "today, 21:00" entry seeded at 09:00).
    return min(moment, now - timedelta(minutes=1))


# ---------------------------------------------------------------------------
# Sample history
# ---------------------------------------------------------------------------

def seed_sample_history(
    conn: sqlite3.Connection,
    user_id: str,
    *,
    now: datetime | None = None,
    entries: list[dict] | None = None,
) -> int:
    """Insert the curated history for ``user_id``. Returns the number of rows written.

    Entries whose exercise no longer exists are skipped, so the seed can be
    older than the exercise bank without breaking guest creation.
    """
    moment = _now(now)
    rows = entries if entries is not None else load_seed_entries()
    inserted = 0
    for entry in rows:
        exists = conn.execute("SELECT 1 FROM exercise WHERE exercise_id = ?", (entry["exercise_id"],)).fetchone()
        if exists is None:
            continue
        is_correct = bool(entry.get("is_correct", False))
        conn.execute(
            """
            INSERT INTO answer_log
            (log_id, user_id, exercise_id, user_answer, is_correct, answered_timestamp,
             feedback, score, error_type, is_sample)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                str(uuid.uuid4()),
                user_id,
                entry["exercise_id"],
                entry["user_answer"],
                is_correct,
                _seed_timestamp(moment, entry).isoformat(),
                None if is_correct else entry.get("feedback"),
                100 if is_correct else int(entry.get("score", 0)),
                "none" if is_correct else entry.get("error_type", "other"),
            ),
        )
        inserted += 1

    if inserted:
        profile = backfill_learner_profile(conn, user_id)
        _point_focus_at_weakest(conn, user_id, profile, moment)
    conn.commit()
    return inserted


def _point_focus_at_weakest(conn: sqlite3.Connection, user_id: str, profile: dict, now: datetime) -> None:
    """Make the learning focus reflect the seeded weakness instead of the default tag."""
    weak_points = profile.get("weak_points") or []
    if not weak_points:
        return
    profile["current_focus"] = {
        "tag": weak_points[0],
        "progress": 2,
        "target": 5,
        "started_at": (now - timedelta(days=2)).isoformat(),
    }
    conn.execute(
        "UPDATE learner_profiles SET profile_json = ?, updated_at = ? WHERE user_id = ?",
        (json.dumps(profile), now.isoformat(), user_id),
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def create_guest(conn: sqlite3.Connection, *, seed_history: bool = True, now: datetime | None = None) -> dict:
    """Create a guest account and (optionally) its sample history."""
    moment = _now(now)
    purge_expired_guests(conn, now=moment)

    user_id = str(uuid.uuid4())
    username = GUEST_USERNAME_PREFIX + secrets.token_hex(5)
    expires_at = moment + timedelta(hours=GUEST_SESSION_HOURS)
    conn.execute(
        """
        INSERT INTO users (user_id, username, password_hash, created_timestamp, is_guest, guest_expires_at)
        VALUES (?, ?, ?, ?, 1, ?)
        """,
        (user_id, username, _password_hash.hash(secrets.token_urlsafe(32)), moment.isoformat(), expires_at.isoformat()),
    )
    conn.commit()
    get_learner_profile(conn, user_id)  # creates the default profile row

    seeded = seed_sample_history(conn, user_id, now=moment) if seed_history else 0
    return {
        "user_id": user_id,
        "username": username,
        "expires_at": expires_at.isoformat(),
        "sample_rows": seeded,
    }


def count_active_guests(conn: sqlite3.Connection, now: datetime | None = None) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM users WHERE is_guest = 1 AND guest_expires_at > ?",
        (_now(now).isoformat(),),
    ).fetchone()
    return int(row[0]) if row else 0


def purge_expired_guests(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    retention_days: int = GUEST_RETENTION_DAYS,
) -> int:
    """Delete guests created more than ``retention_days`` ago, with everything they wrote."""
    cutoff = (_now(now) - timedelta(days=retention_days)).isoformat()
    ids = [
        row[0]
        for row in conn.execute(
            "SELECT user_id FROM users WHERE is_guest = 1 AND created_timestamp < ?", (cutoff,)
        )
    ]
    if not ids:
        return 0

    placeholders = ",".join("?" * len(ids))
    for table in ("answer_log", "video_answer_log", "learner_profiles"):
        if _table_exists(conn, table):
            conn.execute(f"DELETE FROM {table} WHERE user_id IN ({placeholders})", ids)
    if _table_exists(conn, "usage_counters"):
        conn.execute(
            f"DELETE FROM usage_counters WHERE subject IN ({placeholders})",
            [f"guest:{user_id}" for user_id in ids],
        )
    conn.execute(f"DELETE FROM users WHERE user_id IN ({placeholders})", ids)
    conn.commit()
    logger.info(f"Purged {len(ids)} guest account(s) older than {retention_days} days")
    return len(ids)


def upgrade_guest(conn: sqlite3.Connection, user_id: str, username: str, password_hash_value: str) -> None:
    """Turn a guest row into a registered account.

    The guest's own answers stay; the seeded sample rows are removed and the
    learner profile is recomputed from what is left.
    """
    conn.execute(
        """
        UPDATE users
        SET username = ?, password_hash = ?, is_guest = 0, guest_expires_at = NULL
        WHERE user_id = ? AND is_guest = 1
        """,
        (username, password_hash_value, user_id),
    )
    conn.execute("DELETE FROM answer_log WHERE user_id = ? AND is_sample = 1", (user_id,))
    conn.commit()
    backfill_learner_profile(conn, user_id)
