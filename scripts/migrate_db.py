from __future__ import annotations

import argparse
import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "news_corpus.db"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        raise RuntimeError(f"Required table does not exist: {table}")
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _create_index_if_table_exists(conn: sqlite3.Connection, table: str, sql: str) -> None:
    if _table_exists(conn, table):
        conn.execute(sql)


def _migration_001_answer_log_feedback(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "answer_log", "feedback", "TEXT")
    _add_column_if_missing(conn, "answer_log", "score", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "answer_log", "error_type", "TEXT")


def _migration_002_answer_log_embeddings(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "answer_log", "embedding", "BLOB")
    _add_column_if_missing(conn, "answer_log", "embedding_model", "TEXT")


def _migration_003_indexes(conn: sqlite3.Connection) -> None:
    _create_index_if_table_exists(
        conn,
        "answer_log",
        """
        CREATE INDEX IF NOT EXISTS idx_answer_log_user_wrong_ts
        ON answer_log(user_id, is_correct, answered_timestamp)
        """,
    )
    _create_index_if_table_exists(
        conn,
        "answer_log",
        "CREATE INDEX IF NOT EXISTS idx_answer_log_exercise ON answer_log(exercise_id)",
    )
    _create_index_if_table_exists(
        conn,
        "video_answer_log",
        """
        CREATE INDEX IF NOT EXISTS idx_video_answer_log_user_video_ts
        ON video_answer_log(user_id, video_id, answered_timestamp)
        """,
    )
    _create_index_if_table_exists(
        conn,
        "video_exercises",
        "CREATE INDEX IF NOT EXISTS idx_video_exercises_video_id ON video_exercises(video_id)",
    )
    _create_index_if_table_exists(
        conn,
        "articles",
        "CREATE INDEX IF NOT EXISTS idx_articles_status_publish ON articles(status, publish_timestamp)",
    )
    _create_index_if_table_exists(
        conn,
        "videos",
        "CREATE INDEX IF NOT EXISTS idx_videos_status_created ON videos(status, created_timestamp)",
    )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "answer_log feedback fields", _migration_001_answer_log_feedback),
    Migration(2, "answer_log embedding fields", _migration_002_answer_log_embeddings),
    Migration(3, "hot-path indexes", _migration_003_indexes),
)


def migrate_connection(conn: sqlite3.Connection) -> list[Migration]:
    """Apply pending migrations and return the migrations that ran.

    Migrations are intentionally idempotent so databases that were patched by
    older one-off scripts can still be versioned safely.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    applied: list[Migration] = []

    for migration in MIGRATIONS:
        if migration.version <= current_version:
            continue
        with conn:
            migration.apply(conn)
            conn.execute(f"PRAGMA user_version = {migration.version}")
        applied.append(migration)

    return applied


def resolve_db_path(raw_path: str | None = None) -> Path:
    candidate = raw_path or os.environ.get("SHIORI_DATABASE_PATH") or str(DEFAULT_DB_PATH)
    return Path(candidate).expanduser().resolve()


def migrate_db(db_path: str | None = None) -> list[Migration]:
    resolved = resolve_db_path(db_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Database not found at {resolved}")

    with sqlite3.connect(resolved) as conn:
        return migrate_connection(conn)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Shiori SQLite migrations.")
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database. Defaults to SHIORI_DATABASE_PATH or data/news_corpus.db.",
    )
    args = parser.parse_args()

    db_path = resolve_db_path(args.db)
    try:
        applied = migrate_db(str(db_path))
    except Exception as exc:
        raise SystemExit(f"Migration failed for {db_path}: {exc}") from exc

    if not applied:
        print(f"No pending migrations for {db_path}.")
        return

    for migration in applied:
        print(f"Applied {migration.version:04d}: {migration.name}")


if __name__ == "__main__":
    main()
