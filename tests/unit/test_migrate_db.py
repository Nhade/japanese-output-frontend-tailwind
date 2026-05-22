import sqlite3
import unittest

from scripts.migrate_db import MIGRATIONS, migrate_connection


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _indexes(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'",
        )
    }


class TestMigrateConnection(unittest.TestCase):
    def test_adds_missing_columns_indexes_and_user_version(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE answer_log (
                log_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                exercise_id TEXT NOT NULL,
                user_answer TEXT NOT NULL,
                is_correct BOOLEAN NOT NULL,
                answered_timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE video_answer_log (
                log_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                answered_timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE video_exercises (
                exercise_id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL
            )
            """
        )

        applied = migrate_connection(conn)

        self.assertEqual([m.version for m in applied], [m.version for m in MIGRATIONS])
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], MIGRATIONS[-1].version)
        self.assertTrue({"feedback", "score", "error_type", "embedding", "embedding_model"} <= _columns(conn, "answer_log"))
        self.assertTrue(
            {
                "idx_answer_log_user_wrong_ts",
                "idx_answer_log_exercise",
                "idx_video_answer_log_user_video_ts",
                "idx_video_exercises_video_id",
            }
            <= _indexes(conn)
        )

    def test_is_idempotent_for_prepatched_database(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE answer_log (
                log_id TEXT PRIMARY KEY,
                user_id TEXT,
                exercise_id TEXT,
                user_answer TEXT,
                is_correct INTEGER,
                answered_timestamp TEXT,
                feedback TEXT,
                score INTEGER DEFAULT 0,
                error_type TEXT,
                embedding BLOB,
                embedding_model TEXT
            )
            """
        )

        first = migrate_connection(conn)
        second = migrate_connection(conn)

        self.assertEqual([m.version for m in first], [m.version for m in MIGRATIONS])
        self.assertEqual(second, [])


if __name__ == "__main__":
    unittest.main()
