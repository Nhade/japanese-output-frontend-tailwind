"""Tests for the lookup tools."""
import json
import sqlite3
import unittest
import uuid
from datetime import datetime

from document_service import (
    create_document_tables,
    create_range,
    ingest_document,
)
from practice_service import create_practice_tables
from tools.lookup import (
    learner_weak_points,
    lookup_pattern,
    search_examples,
    srs_due,
)


def _fresh_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE users (user_id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO users (user_id) VALUES ('u1')")
    conn.execute('''
        CREATE TABLE learner_profiles (
            user_id TEXT PRIMARY KEY,
            profile_json TEXT,
            updated_at TEXT
        )
    ''')
    create_document_tables(conn)
    create_practice_tables(conn)
    return conn


def _seed_doc_with_patterns(conn) -> dict:
    """Ingest a doc with two chunks; attach one pattern to each chunk."""
    md = "# A\n\nFirst chunk content.\n\n# B\n\nSecond chunk content."
    r = ingest_document(conn, "u1", "Notes", "grammar_notes", md, "n.md")
    chunks = conn.execute(
        "SELECT chunk_id FROM doc_chunks WHERE doc_id = ? ORDER BY seq",
        (r["doc_id"],)
    ).fetchall()
    chunk_a, chunk_b = chunks[0]["chunk_id"], chunks[1]["chunk_id"]

    p1 = str(uuid.uuid4())
    p2 = str(uuid.uuid4())
    p_pending = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn.executemany('''
        INSERT INTO grammar_patterns
        (pattern_id, doc_id, source_chunk_id, name, confidence, status,
         created_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [
        (p1, r["doc_id"], chunk_a, "〜てしまう", 0.9, "published", now),
        (p2, r["doc_id"], chunk_b, "〜ば",      0.9, "published", now),
        (p_pending, r["doc_id"], chunk_a, "〜らしい",
         0.5, "pending_review", now),
    ])
    # Examples: canonical and non-canonical for p1.
    conn.executemany('''
        INSERT INTO pattern_examples
        (example_id, pattern_id, sentence, translation, is_canonical,
         created_timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', [
        (str(uuid.uuid4()), p1, "食べてしまった", "ate it all", 1, now),
        (str(uuid.uuid4()), p1, "忘れてしまった", "forgot it",   0, now),
        (str(uuid.uuid4()), p1, "言ってしまった", "said it",     0, now),
        (str(uuid.uuid4()), p2, "食べれば",       "if eat",      1, now),
    ])
    conn.commit()
    return {
        "doc_id": r["doc_id"], "chunk_a": chunk_a, "chunk_b": chunk_b,
        "p1": p1, "p2": p2, "p_pending": p_pending,
    }


class TestLookupPattern(unittest.TestCase):

    def test_round_trip(self):
        conn = _fresh_db()
        ctx = _seed_doc_with_patterns(conn)
        result = lookup_pattern(conn, ctx["p1"])
        self.assertEqual(result["name"], "〜てしまう")
        self.assertEqual(result["status"], "published")

    def test_missing_returns_none(self):
        conn = _fresh_db()
        self.assertIsNone(lookup_pattern(conn, "no-id"))


class TestSearchExamples(unittest.TestCase):

    def test_canonical_first_then_capped(self):
        conn = _fresh_db()
        ctx = _seed_doc_with_patterns(conn)
        examples = search_examples(conn, ctx["p1"], k=2)
        self.assertEqual(len(examples), 2)
        self.assertEqual(examples[0]["sentence"], "食べてしまった")
        self.assertEqual(examples[0]["is_canonical"], 1)


class TestSrsDue(unittest.TestCase):

    def test_returns_only_published_in_range(self):
        conn = _fresh_db()
        ctx = _seed_doc_with_patterns(conn)
        # Range covers only chunk_a, which has one published pattern (p1)
        # and one pending (p_pending — should be excluded).
        r = create_range(conn, "u1", ctx["doc_id"], "Ch A", [ctx["chunk_a"]])
        due = srs_due(conn, "u1", r["range_id"])
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["pattern_id"], ctx["p1"])

    def test_returns_all_published_when_range_covers_doc(self):
        conn = _fresh_db()
        ctx = _seed_doc_with_patterns(conn)
        r = create_range(conn, "u1", ctx["doc_id"], "All",
                         [ctx["chunk_a"], ctx["chunk_b"]])
        due = srs_due(conn, "u1", r["range_id"])
        ids = sorted(d["pattern_id"] for d in due)
        self.assertEqual(ids, sorted([ctx["p1"], ctx["p2"]]))

    def test_unknown_range_returns_empty(self):
        conn = _fresh_db()
        self.assertEqual(srs_due(conn, "u1", "no-range"), [])


class TestLearnerWeakPoints(unittest.TestCase):

    def test_returns_weak_points(self):
        conn = _fresh_db()
        conn.execute('''
            INSERT INTO learner_profiles (user_id, profile_json, updated_at)
            VALUES ('u1', ?, ?)
        ''', (json.dumps({"weak_points": ["particle:を", "conjugation:て"],
                          "level_est": "N4"}),
              datetime.now().isoformat()))
        conn.commit()
        weak = learner_weak_points(conn, "u1")
        self.assertEqual(weak, ["particle:を", "conjugation:て"])

    def test_missing_profile_returns_empty(self):
        conn = _fresh_db()
        self.assertEqual(learner_weak_points(conn, "ghost"), [])


if __name__ == "__main__":
    unittest.main()
