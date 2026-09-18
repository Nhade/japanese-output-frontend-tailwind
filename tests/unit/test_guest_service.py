from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

import guest_service
import usage_limits
from learner_service import create_learner_tables

SCHEMA = """
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    created_timestamp TEXT NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE exercise (
    exercise_id TEXT PRIMARY KEY,
    question_sentence TEXT,
    correct_answer TEXT,
    hint_chinese TEXT,
    part_of_speech TEXT,
    jlpt_level INTEGER
);
CREATE TABLE answer_log (
    log_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    exercise_id TEXT NOT NULL,
    user_answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    answered_timestamp TEXT NOT NULL,
    feedback TEXT,
    score INTEGER DEFAULT 0,
    error_type TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    FOREIGN KEY (exercise_id) REFERENCES exercise (exercise_id)
);
CREATE TABLE video_answer_log (
    log_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    answered_timestamp TEXT NOT NULL
);
"""

SEED_SUBSET = 6  # how many seed exercises the fixture materialises


def build_db(path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    create_learner_tables(conn)
    guest_service.ensure_guest_schema(conn)
    # Only some of the seed's exercises exist here, which also exercises the
    # "skip entries whose exercise is missing" rule.
    for entry in guest_service.load_seed_entries()[:SEED_SUBSET]:
        conn.execute(
            "INSERT INTO exercise (exercise_id, question_sentence, correct_answer, part_of_speech, jlpt_level) "
            "VALUES (?, ?, ?, ?, ?)",
            (entry["exercise_id"], "文[＿＿＿]。", "x", "助詞", 4),
        )
    conn.commit()
    return conn


@pytest.fixture()
def conn(tmp_path):
    connection = build_db(tmp_path / "guest.db")
    yield connection
    connection.close()


def _count(conn, sql, *params) -> int:
    return conn.execute(sql, params).fetchone()[0]


def test_seed_file_is_well_formed():
    entries = guest_service.load_seed_entries()
    assert len(entries) >= 20
    wrong = [e for e in entries if not e.get("is_correct")]
    assert wrong and all(e.get("feedback") and e.get("error_type") for e in wrong)
    assert all(("minutes_ago" in e) != ("days_ago" in e) for e in entries)
    assert any("minutes_ago" in e and not e.get("is_correct") for e in entries), "daily review needs a miss today"


def test_create_guest_seeds_only_existing_exercises(conn):
    now = datetime(2026, 9, 18, 9, 30)

    info = guest_service.create_guest(conn, now=now)

    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (info["user_id"],)).fetchone()
    assert user["is_guest"] == 1
    assert user["username"].startswith(guest_service.GUEST_USERNAME_PREFIX)
    assert datetime.fromisoformat(user["guest_expires_at"]) == now + timedelta(hours=guest_service.GUEST_SESSION_HOURS)
    assert info["sample_rows"] == SEED_SUBSET
    assert _count(conn, "SELECT COUNT(*) FROM answer_log WHERE user_id = ? AND is_sample = 1", info["user_id"]) == SEED_SUBSET

    timestamps = [
        datetime.fromisoformat(row[0])
        for row in conn.execute("SELECT answered_timestamp FROM answer_log WHERE user_id = ?", (info["user_id"],))
    ]
    assert all(ts < now for ts in timestamps), "seeded history must never be in the future"
    assert any(ts.date() == now.date() for ts in timestamps), "some misses must land today"

    profile = guest_service.get_learner_profile(conn, info["user_id"])
    assert profile["stats"]["by_pos_attempt"]["助詞"] == SEED_SUBSET
    assert profile["current_focus"]["tag"] == "助詞"


def test_create_guest_without_sample_history(conn):
    info = guest_service.create_guest(conn, seed_history=False)

    assert info["sample_rows"] == 0
    assert _count(conn, "SELECT COUNT(*) FROM answer_log WHERE user_id = ?", info["user_id"]) == 0
    assert _count(conn, "SELECT COUNT(*) FROM learner_profiles WHERE user_id = ?", info["user_id"]) == 1


def test_purge_removes_only_stale_guests(conn):
    now = datetime(2026, 9, 18, 12, 0)
    stale = guest_service.create_guest(conn, now=now - timedelta(days=guest_service.GUEST_RETENTION_DAYS + 1))
    fresh = guest_service.create_guest(conn, now=now - timedelta(days=1))
    conn.execute(
        "INSERT INTO users (user_id, username, created_timestamp, password_hash) VALUES ('real', 'ray', ?, 'h')",
        ((now - timedelta(days=400)).isoformat(),),
    )
    usage_limits.consume(conn, f"guest:{stale['user_id']}", "chat", 30, usage_limits.SESSION_WINDOW)
    conn.commit()

    purged = guest_service.purge_expired_guests(conn, now=now)

    assert purged == 1
    remaining = {row[0] for row in conn.execute("SELECT user_id FROM users")}
    assert remaining == {fresh["user_id"], "real"}
    assert _count(conn, "SELECT COUNT(*) FROM answer_log WHERE user_id = ?", stale["user_id"]) == 0
    assert _count(conn, "SELECT COUNT(*) FROM learner_profiles WHERE user_id = ?", stale["user_id"]) == 0
    assert _count(conn, "SELECT COUNT(*) FROM usage_counters WHERE subject = ?", f"guest:{stale['user_id']}") == 0
    assert _count(conn, "SELECT COUNT(*) FROM answer_log WHERE user_id = ?", fresh["user_id"]) == SEED_SUBSET


def test_create_guest_purges_stale_guests_first(conn):
    now = datetime(2026, 9, 18, 12, 0)
    stale = guest_service.create_guest(conn, now=now - timedelta(days=30))

    guest_service.create_guest(conn, now=now)

    assert _count(conn, "SELECT COUNT(*) FROM users WHERE user_id = ?", stale["user_id"]) == 0


def test_upgrade_guest_keeps_own_answers_and_drops_samples(conn):
    info = guest_service.create_guest(conn)
    exercise_id = conn.execute("SELECT exercise_id FROM exercise LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO answer_log (log_id, user_id, exercise_id, user_answer, is_correct, answered_timestamp, score) "
        "VALUES ('own', ?, ?, 'に', 0, ?, 95)",
        (info["user_id"], exercise_id, datetime.now().isoformat()),
    )
    conn.commit()

    guest_service.upgrade_guest(conn, info["user_id"], "newname", "hashed-secret")

    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (info["user_id"],)).fetchone()
    assert user["is_guest"] == 0
    assert user["guest_expires_at"] is None
    assert user["username"] == "newname"
    assert user["password_hash"] == "hashed-secret"
    rows = conn.execute("SELECT log_id FROM answer_log WHERE user_id = ?", (info["user_id"],)).fetchall()
    assert [row[0] for row in rows] == ["own"]
    profile = guest_service.get_learner_profile(conn, info["user_id"])
    assert profile["stats"]["by_pos_attempt"] == {"助詞": 1}


def test_guest_session_expired():
    now = datetime(2026, 9, 18, 12, 0)
    assert guest_service.guest_session_expired(None, now) is False
    assert guest_service.guest_session_expired((now + timedelta(hours=1)).isoformat(), now) is False
    assert guest_service.guest_session_expired((now - timedelta(seconds=1)).isoformat(), now) is True
    assert guest_service.guest_session_expired("not-a-date", now) is True


def test_count_active_guests_ignores_expired(conn):
    now = datetime(2026, 9, 18, 12, 0)
    guest_service.create_guest(conn, now=now, seed_history=False)
    guest_service.create_guest(conn, now=now - timedelta(hours=guest_service.GUEST_SESSION_HOURS + 1), seed_history=False)

    assert guest_service.count_active_guests(conn, now=now) == 1


# ---------------------------------------------------------------------------
# usage_limits
# ---------------------------------------------------------------------------

def test_consume_counts_per_window(conn):
    assert usage_limits.consume(conn, "ip:1", "guest_create", 2, "2026-09-18T10") == (True, 1)
    assert usage_limits.consume(conn, "ip:1", "guest_create", 2, "2026-09-18T10") == (True, 2)
    assert usage_limits.consume(conn, "ip:1", "guest_create", 2, "2026-09-18T10") == (False, 3)
    # A new hour window starts fresh; other subjects are independent.
    assert usage_limits.consume(conn, "ip:1", "guest_create", 2, "2026-09-18T11") == (True, 1)
    assert usage_limits.consume(conn, "ip:2", "guest_create", 2, "2026-09-18T10") == (True, 1)


def test_check_guest_action_session_limit_then_shared_budget(conn, monkeypatch):
    monkeypatch.setattr(usage_limits, "GUEST_ACTION_LIMITS", {"chat": 2, "submit": 5})
    monkeypatch.setattr(usage_limits, "GUEST_DAILY_BUDGET", 3)
    now = datetime(2026, 9, 18, 12, 0)

    assert usage_limits.check_guest_action(conn, "g1", "chat", now) is None
    assert usage_limits.check_guest_action(conn, "g1", "chat", now) is None
    assert usage_limits.check_guest_action(conn, "g1", "chat", now) == "preview_limit"
    # Another guest is still within their own session limit, but the shared
    # daily LLM budget (3) has now been consumed by the two calls above + this one.
    assert usage_limits.check_guest_action(conn, "g2", "chat", now) is None
    assert usage_limits.check_guest_action(conn, "g2", "chat", now) == "preview_busy"
    # Non-LLM actions never touch the shared budget.
    assert usage_limits.check_guest_action(conn, "g2", "submit", now) is None
    # Unknown actions are not metered.
    assert usage_limits.check_guest_action(conn, "g2", "profile", now) is None


def test_window_key_formats():
    now = datetime(2026, 9, 18, 7, 5)
    assert usage_limits.window_key("hour", now) == "2026-09-18T07"
    assert usage_limits.window_key("day", now) == "2026-09-18"
    assert usage_limits.window_key("session", now) == "session"
    with pytest.raises(ValueError):
        usage_limits.window_key("week", now)
