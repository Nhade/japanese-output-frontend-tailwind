"""
Practice service — stores extracted grammar patterns and typed exercises
generated against user-selected document ranges.

Public API (in this phase):
  - create_practice_tables(conn)  — ensure practice-related tables exist

Extraction, strategy dispatch, and the HTTP routes arrive in later phases.
"""
import sqlite3


def create_practice_tables(conn: sqlite3.Connection):
    """Create practice-related tables if they don't exist.

    Tables:
      grammar_patterns    — structured entries extracted from documents
      pattern_examples    — canonical and supporting examples per pattern
      exercises           — typed, polymorphic (cloze / pattern_use / etc.)
      exercise_attempts   — per-submission log with score + structured feedback
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
    conn.commit()
