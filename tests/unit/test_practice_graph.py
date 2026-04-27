"""Unit tests for the practice graph + pattern_use evaluator.

LLM calls are stubbed via the llm_fn injection point so no network is
involved. The full graph runs against an on-disk SQLite file (the graph
nodes open their own connections, so :memory: would be empty in each
node).
"""
import json
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import datetime

from document_service import (
    create_document_tables,
    create_range,
    ingest_document,
)
from graphs.eval_graph import evaluate_pattern_use_submission
from graphs.practice_graph import generate_exercise
from practice_service import create_practice_tables


def _seed_db() -> tuple[str, dict]:
    """Create a tmpfile DB with one user, one doc with two chunks, and
    two published patterns (one per chunk) plus canonical examples.
    Returns (db_path, ctx)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    conn = sqlite3.connect(db_path)
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
    conn.execute('''
        INSERT INTO learner_profiles (user_id, profile_json, updated_at)
        VALUES ('u1', ?, ?)
    ''', (json.dumps({"weak_points": ["conjugation:て"], "level_est": "N4"}),
          datetime.now().isoformat()))
    create_document_tables(conn)
    create_practice_tables(conn)

    md = "# 〜てしまう\n\n意味.\n\n# 〜ば\n\n条件."
    r = ingest_document(conn, "u1", "Notes", "grammar_notes", md, "n.md")
    chunks = conn.execute(
        "SELECT chunk_id FROM doc_chunks WHERE doc_id = ? ORDER BY seq",
        (r["doc_id"],)
    ).fetchall()
    chunk_a = chunks[0]["chunk_id"]
    chunk_b = chunks[1]["chunk_id"]

    p1 = str(uuid.uuid4())
    p2 = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn.executemany('''
        INSERT INTO grammar_patterns
        (pattern_id, doc_id, source_chunk_id, name, jlpt, register,
         meaning_locale, formation_rule, confidence, status,
         created_timestamp)
        VALUES (?, ?, ?, ?, ?, 'plain', ?, ?, 0.95, 'published', ?)
    ''', [
        (p1, r["doc_id"], chunk_a, "〜てしまう", 4,
         "完了/遺憾", "て-form + しまう", now),
        (p2, r["doc_id"], chunk_b, "〜ば", 4,
         "条件", "stem-e + ば", now),
    ])
    conn.executemany('''
        INSERT INTO pattern_examples
        (example_id, pattern_id, sentence, translation, is_canonical,
         created_timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', [
        (str(uuid.uuid4()), p1, "食べてしまった", "ate it all", 1, now),
        (str(uuid.uuid4()), p1, "忘れてしまった", "forgot it",   0, now),
        (str(uuid.uuid4()), p2, "食べれば",       "if eat",      1, now),
    ])

    rng = create_range(conn, "u1", r["doc_id"], "Both",
                       [chunk_a, chunk_b])
    conn.commit()
    conn.close()
    return db_path, {
        "doc_id": r["doc_id"], "p1": p1, "p2": p2,
        "range_id": rng["range_id"],
    }


def _make_llm(plan_pattern_id: str, ref_answer: str = "本を食べてしまった"):
    """Return an llm_fn stub. First call answers the planner; subsequent
    calls answer the executor with a fixed reference answer."""
    state = {"calls": 0}
    def fn(messages, _temperature):
        state["calls"] += 1
        sys = messages[0]["content"]
        if "practice planner" in sys:
            return {
                "target_pattern_id": plan_pattern_id,
                "strategy": "pattern_use",
                "difficulty": 3,
                "variant_hint": "regret about food",
            }
        if "exercise writer" in sys:
            return {
                "prompt_locale_text": "Write about a food regret.",
                "reference_answer_jp": ref_answer,
            }
        raise AssertionError("Unexpected LLM call: " + sys[:80])
    return fn, state


class TestGenerateExercise(unittest.TestCase):

    def setUp(self):
        self.db_path, self.ctx = _seed_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_happy_path_persists_exercise(self):
        llm, _ = _make_llm(self.ctx["p1"])
        result = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"],
            locale="zh-tw", llm_fn=llm,
        )
        self.assertIn("exercise", result, msg=result)
        ex = result["exercise"]
        self.assertEqual(ex["type"], "pattern_use")
        self.assertEqual(ex["target_pattern_id"], self.ctx["p1"])
        self.assertEqual(ex["source"], "graph")
        self.assertEqual(ex["retries"], 0)

        # Persisted to DB.
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT type, target_pattern_id, source FROM exercises "
            "WHERE exercise_id = ?", (ex["exercise_id"],)
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "pattern_use")
        self.assertEqual(row[1], self.ctx["p1"])
        self.assertEqual(row[2], "graph")

    def test_planner_rejects_invented_id(self):
        def llm(messages, _t):
            sys = messages[0]["content"]
            if "practice planner" in sys:
                return {
                    "target_pattern_id": "ghost-id",
                    "strategy": "pattern_use",
                    "difficulty": 3,
                    "variant_hint": "x",
                }
            return {}
        result = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"], llm_fn=llm,
        )
        self.assertEqual(result.get("error"), "plan_invented_pattern_id")

    def test_verifier_retry_then_fallback(self):
        # Executor always returns a reference that doesn't contain the
        # pattern → verifier fails → retries until budget → fallback.
        def llm(messages, _t):
            sys = messages[0]["content"]
            if "practice planner" in sys:
                return {
                    "target_pattern_id": self.ctx["p1"],
                    "strategy": "pattern_use",
                    "difficulty": 3,
                    "variant_hint": "any",
                }
            if "exercise writer" in sys:
                # No てしま in reference — verifier will reject every time.
                return {
                    "prompt_locale_text": "...",
                    "reference_answer_jp": "本を読んだ",
                }
            raise AssertionError(sys[:80])

        result = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"], llm_fn=llm,
        )
        ex = result["exercise"]
        self.assertEqual(ex["source"], "fallback_canonical")
        self.assertGreaterEqual(ex["retries"], 2)

    def test_empty_range_short_circuits(self):
        # Range with a chunk that has no patterns attached.
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Insert a third pattern but mark it pending_review (excluded).
        conn.execute(
            "UPDATE grammar_patterns SET status = 'pending_review' "
            "WHERE doc_id = ?", (self.ctx["doc_id"],)
        )
        conn.commit()
        conn.close()

        result = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"],
            llm_fn=lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("should not be called")),
        )
        self.assertEqual(result.get("error"),
                         "no_published_patterns_in_range")


class TestEvaluatePatternUse(unittest.TestCase):

    def setUp(self):
        self.db_path, self.ctx = _seed_db()
        # Generate an exercise so we have something to submit against.
        llm, _ = _make_llm(self.ctx["p1"], ref_answer="食べてしまった")
        gen = generate_exercise(self.db_path, "u1", self.ctx["range_id"],
                                llm_fn=llm)
        self.exercise_id = gen["exercise"]["exercise_id"]

    def tearDown(self):
        os.unlink(self.db_path)

    def test_correct_response_scores_high(self):
        def judge(messages):
            return {
                "score": 0.95, "used_pattern": True,
                "feedback_text": "Excellent.", "issues": [],
            }
        result = evaluate_pattern_use_submission(
            self.db_path, self.exercise_id, "u1",
            "ケーキを食べてしまった",
            llm_fn=judge,
        )
        self.assertTrue(result["is_correct"])
        self.assertTrue(result["used_pattern"])
        self.assertGreaterEqual(result["score"], 0.9)
        self.assertTrue(result["detector"]["detected"])

    def test_pattern_missing_caps_score(self):
        # User's response doesn't contain てしま → detector says false →
        # rubric MUST cap score at 0.4 even if the LLM hallucinates higher.
        def judge(messages):
            return {
                "score": 0.9, "used_pattern": True,
                "feedback_text": "Looks great.", "issues": [],
            }
        result = evaluate_pattern_use_submission(
            self.db_path, self.exercise_id, "u1", "本を読んだ",
            llm_fn=judge,
        )
        self.assertFalse(result["used_pattern"])
        self.assertLessEqual(result["score"], 0.4)
        self.assertFalse(result["is_correct"])
        self.assertFalse(result["detector"]["detected"])

    def test_persists_attempt(self):
        result = evaluate_pattern_use_submission(
            self.db_path, self.exercise_id, "u1",
            "ケーキを食べてしまった",
            llm_fn=lambda _msgs: {
                "score": 0.85, "used_pattern": True,
                "feedback_text": "Good.", "issues": [],
            },
        )
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT score, is_correct, response FROM exercise_attempts "
            "WHERE attempt_id = ?", (result["attempt_id"],)
        ).fetchone()
        conn.close()
        self.assertEqual(row["response"], "ケーキを食べてしまった")
        self.assertEqual(row["is_correct"], 1)

    def test_rejects_empty_response(self):
        with self.assertRaises(ValueError):
            evaluate_pattern_use_submission(
                self.db_path, self.exercise_id, "u1", "   ",
                llm_fn=lambda _msgs: {},
            )

    def test_llm_failure_falls_back_to_detector(self):
        def broken(_msgs):
            raise RuntimeError("LLM down")
        result = evaluate_pattern_use_submission(
            self.db_path, self.exercise_id, "u1",
            "ケーキを食べてしまった",
            llm_fn=broken,
        )
        # Detector found the pattern, so used_pattern is True even
        # without the LLM. Score is the conservative fallback.
        self.assertTrue(result["used_pattern"])
        self.assertAlmostEqual(result["score"], 0.4, places=2)
        self.assertIn("Automatic grading unavailable",
                      result["feedback_text"])


if __name__ == "__main__":
    unittest.main()
