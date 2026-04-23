"""
Practice service — stores extracted grammar patterns and typed exercises
generated against user-selected document ranges.

Public API (in this phase):
  - create_practice_tables(conn)  — ensure practice-related tables exist
  - reset_stale_jobs(conn)        — mark running jobs failed at startup

Extraction, strategy dispatch, and the HTTP routes arrive in later phases.
"""
import sqlite3
from datetime import datetime


def create_practice_tables(conn: sqlite3.Connection):
    """Create practice-related tables if they don't exist.

    Tables:
      grammar_patterns    — structured entries extracted from documents
      pattern_examples    — canonical and supporting examples per pattern
      exercises           — typed, polymorphic (cloze / pattern_use / etc.)
      exercise_attempts   — per-submission log with score + structured feedback
      extraction_jobs     — background extraction progress per uploaded doc
    """
    conn.execute('''
        CREATE TABLE IF NOT EXISTS grammar_patterns (
            pattern_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL REFERENCES documents(doc_id),
            source_chunk_id TEXT REFERENCES doc_chunks(chunk_id),
            name TEXT NOT NULL,
            reading TEXT,
            meaning_en TEXT,
            meaning_locale TEXT,
            formation_rule TEXT,
            jlpt INTEGER,
            register TEXT,
            confidence REAL NOT NULL DEFAULT 1.0,
            status TEXT NOT NULL DEFAULT 'published',
            detector_spec TEXT,
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pattern_examples (
            example_id TEXT PRIMARY KEY,
            pattern_id TEXT NOT NULL REFERENCES grammar_patterns(pattern_id),
            sentence TEXT NOT NULL,
            translation TEXT,
            is_canonical INTEGER NOT NULL DEFAULT 0,
            cloze_mask_hint TEXT,
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS exercises (
            exercise_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            range_id TEXT REFERENCES practice_ranges(range_id),
            type TEXT NOT NULL,
            target_pattern_id TEXT REFERENCES grammar_patterns(pattern_id),
            target_vocab_id TEXT,
            difficulty INTEGER NOT NULL DEFAULT 3,
            prompt TEXT NOT NULL,
            expected_json TEXT,
            rubric_json TEXT,
            seed TEXT,
            source TEXT,
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS exercise_attempts (
            attempt_id TEXT PRIMARY KEY,
            exercise_id TEXT NOT NULL REFERENCES exercises(exercise_id),
            user_id TEXT NOT NULL REFERENCES users(user_id),
            response TEXT NOT NULL,
            score REAL,
            is_correct INTEGER,
            feedback_json TEXT,
            answered_timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS extraction_jobs (
            job_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL REFERENCES documents(doc_id),
            user_id TEXT NOT NULL REFERENCES users(user_id),
            locale TEXT NOT NULL DEFAULT 'en',
            status TEXT NOT NULL DEFAULT 'queued',
            total_chunks INTEGER,
            processed_chunks INTEGER NOT NULL DEFAULT 0,
            patterns_extracted INTEGER NOT NULL DEFAULT 0,
            patterns_published INTEGER NOT NULL DEFAULT 0,
            patterns_pending INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()


def reset_stale_jobs(conn: sqlite3.Connection):
    """Mark any 'running' jobs as failed.

    Call at startup — a job left in 'running' means the worker died
    mid-extraction (process killed, OOM, deploy) and will never complete
    on its own.
    """
    conn.execute('''
        UPDATE extraction_jobs
        SET status = 'failed',
            error = COALESCE(error, 'interrupted'),
            completed_at = ?
        WHERE status IN ('queued', 'running')
    ''', (datetime.now().isoformat(),))
    conn.commit()
