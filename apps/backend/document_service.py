"""
Document service — uploads, parses, and chunks learner documents
(grammar notes, textbook sections).

Public API (in this phase):
  - create_document_tables(conn)  — ensure document-related tables exist

Parse/chunk and the HTTP routes arrive in Phase 2a.
"""
import sqlite3


def create_document_tables(conn: sqlite3.Connection):
    """Create document-related tables if they don't exist.

    Tables:
      documents         — one row per uploaded document
      doc_chunks        — structural split (by heading) for retrieval/display
      practice_ranges   — user-named subsets of a document for practice
    """
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            title TEXT NOT NULL,
            source_type TEXT NOT NULL,
            original_filename TEXT,
            content_hash TEXT,
            status TEXT NOT NULL DEFAULT 'uploaded',
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS doc_chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL REFERENCES documents(doc_id),
            seq INTEGER NOT NULL,
            section_label TEXT,
            heading_level INTEGER,
            text TEXT NOT NULL,
            token_count INTEGER,
            UNIQUE(doc_id, seq)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS practice_ranges (
            range_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            doc_id TEXT NOT NULL REFERENCES documents(doc_id),
            label TEXT NOT NULL,
            chunk_ids_json TEXT NOT NULL,
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
