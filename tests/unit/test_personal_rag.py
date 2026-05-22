"""
Unit tests for `personal_rag` — the grader-feedback annotation that surfaces
the learner's history of similar past mistakes.

We seed an in-memory SQLite with `answer_log` and `exercise` tables, drop in
hand-crafted unit-norm embeddings, and assert the retrieval rules:
threshold cutoff, same-exercise exclusion, correct-answer exclusion,
per-user scoping, and the latest-timestamp pick.
"""
import sqlite3
import unittest

import numpy as np

from personal_rag import (
    SIMILARITY_THRESHOLD,
    _format_date,
    annotate_feedback,
    find_similar_past_mistakes,
    find_top_similar_mistakes,
)

EMBED_DIM = 768


def _unit_vector(*indices: int) -> np.ndarray:
    """Build a unit vector with 1.0 at the given indices (then L2-normalized)."""
    v = np.zeros(EMBED_DIM, dtype=np.float32)
    for i in indices:
        v[i] = 1.0
    norm = float(np.linalg.norm(v))
    if norm > 0:
        v = v / norm
    return v


def _to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE answer_log (
            log_id TEXT PRIMARY KEY,
            user_id TEXT,
            exercise_id TEXT,
            user_answer TEXT,
            error_type TEXT,
            is_correct INTEGER,
            answered_timestamp TEXT,
            embedding BLOB
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE exercise (
            exercise_id TEXT PRIMARY KEY,
            question_sentence TEXT,
            correct_answer TEXT
        )
        """
    )
    return conn


def _insert_log(
    conn: sqlite3.Connection,
    log_id: str,
    *,
    user_id: str = "u1",
    exercise_id: str = "ex-1",
    embedding: np.ndarray | None = None,
    is_correct: int = 0,
    timestamp: str = "2026-05-01T10:00:00",
    user_answer: str = "wrong",
    error_type: str = "grammar",
) -> None:
    conn.execute(
        "INSERT INTO answer_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            log_id,
            user_id,
            exercise_id,
            user_answer,
            error_type,
            is_correct,
            timestamp,
            _to_blob(embedding) if embedding is not None else None,
        ),
    )


def _insert_exercise(
    conn: sqlite3.Connection,
    exercise_id: str,
    *,
    prompt: str = "質問",
    answer: str = "答え",
) -> None:
    conn.execute(
        "INSERT INTO exercise VALUES (?, ?, ?)",
        (exercise_id, prompt, answer),
    )


class TestFormatDate(unittest.TestCase):
    def test_valid_iso(self):
        self.assertEqual(_format_date("2026-05-01T10:00:00"), "May 01, 2026")

    def test_malformed_falls_back(self):
        self.assertEqual(_format_date("garbage"), "garbage")


class TestFindSimilarPastMistakes(unittest.TestCase):
    def setUp(self):
        self.conn = _make_conn()
        self.q_vec = _unit_vector(0)
        _insert_exercise(self.conn, "ex-target")
        _insert_log(self.conn, "target", exercise_id="ex-target", embedding=self.q_vec)

    def test_missing_target_returns_zero(self):
        count, last = find_similar_past_mistakes(self.conn, "does-not-exist")
        self.assertEqual(count, 0)
        self.assertIsNone(last)

    def test_target_without_embedding_returns_zero(self):
        _insert_exercise(self.conn, "ex-no-emb")
        _insert_log(self.conn, "no-emb", exercise_id="ex-no-emb", embedding=None)
        count, last = find_similar_past_mistakes(self.conn, "no-emb")
        self.assertEqual(count, 0)
        self.assertIsNone(last)

    def test_empty_history_returns_zero(self):
        count, last = find_similar_past_mistakes(self.conn, "target")
        self.assertEqual(count, 0)
        self.assertIsNone(last)

    def test_identical_vector_counts(self):
        _insert_exercise(self.conn, "ex-other")
        _insert_log(
            self.conn,
            "past1",
            exercise_id="ex-other",
            embedding=self.q_vec,
            timestamp="2026-04-01T10:00:00",
        )
        count, last = find_similar_past_mistakes(self.conn, "target")
        self.assertEqual(count, 1)
        self.assertEqual(last, "2026-04-01T10:00:00")

    def test_orthogonal_vector_excluded(self):
        _insert_exercise(self.conn, "ex-other")
        # cos(self.q_vec, orthogonal) = 0.0 — well below threshold 0.92
        _insert_log(
            self.conn,
            "past1",
            exercise_id="ex-other",
            embedding=_unit_vector(1),
        )
        count, _ = find_similar_past_mistakes(self.conn, "target")
        self.assertEqual(count, 0)

    def test_same_exercise_excluded(self):
        # Identical vector but same exercise_id — must be excluded so the
        # count doesn't just measure retries of the same prompt.
        _insert_log(
            self.conn,
            "retry",
            exercise_id="ex-target",
            embedding=self.q_vec,
        )
        count, _ = find_similar_past_mistakes(self.conn, "target")
        self.assertEqual(count, 0)

    def test_correct_answers_excluded(self):
        _insert_exercise(self.conn, "ex-other")
        _insert_log(
            self.conn,
            "got-right",
            exercise_id="ex-other",
            embedding=self.q_vec,
            is_correct=1,
        )
        count, _ = find_similar_past_mistakes(self.conn, "target")
        self.assertEqual(count, 0)

    def test_other_user_excluded(self):
        _insert_exercise(self.conn, "ex-other")
        _insert_log(
            self.conn,
            "other-user",
            user_id="u2",
            exercise_id="ex-other",
            embedding=self.q_vec,
        )
        count, _ = find_similar_past_mistakes(self.conn, "target")
        self.assertEqual(count, 0)

    def test_returns_latest_timestamp_among_above_threshold(self):
        _insert_exercise(self.conn, "ex-a")
        _insert_exercise(self.conn, "ex-b")
        _insert_log(
            self.conn,
            "older",
            exercise_id="ex-a",
            embedding=self.q_vec,
            timestamp="2026-01-15T10:00:00",
        )
        _insert_log(
            self.conn,
            "newer",
            exercise_id="ex-b",
            embedding=self.q_vec,
            timestamp="2026-04-20T10:00:00",
        )
        count, last = find_similar_past_mistakes(self.conn, "target")
        self.assertEqual(count, 2)
        self.assertEqual(last, "2026-04-20T10:00:00")

    def test_threshold_cutoff_respected(self):
        _insert_exercise(self.conn, "ex-above")
        _insert_exercise(self.conn, "ex-below")
        # Build a vector with cosine ~0.95 with q_vec: heavy on index 0,
        # small leak to index 1 — still above 0.92.
        above = np.zeros(EMBED_DIM, dtype=np.float32)
        above[0] = 0.95
        above[1] = float(np.sqrt(1 - 0.95**2))
        _insert_log(self.conn, "above", exercise_id="ex-above", embedding=above)
        # And one with cosine 0.5 — below threshold.
        below = np.zeros(EMBED_DIM, dtype=np.float32)
        below[0] = 0.5
        below[1] = float(np.sqrt(1 - 0.5**2))
        _insert_log(self.conn, "below", exercise_id="ex-below", embedding=below)

        count, _ = find_similar_past_mistakes(self.conn, "target")
        self.assertEqual(count, 1)


class TestFindTopSimilarMistakes(unittest.TestCase):
    def setUp(self):
        self.conn = _make_conn()
        self.q_vec = _unit_vector(0)
        _insert_exercise(self.conn, "ex-target", prompt="目標", answer="正解")
        _insert_log(self.conn, "target", exercise_id="ex-target", embedding=self.q_vec)
        _insert_exercise(self.conn, "ex-a", prompt="質問A", answer="答えA")
        _insert_exercise(self.conn, "ex-b", prompt="質問B", answer="答えB")
        _insert_log(
            self.conn,
            "past-a",
            exercise_id="ex-a",
            embedding=self.q_vec,
            timestamp="2026-04-01T10:00:00",
        )
        _insert_log(
            self.conn,
            "past-b",
            exercise_id="ex-b",
            embedding=self.q_vec,
            timestamp="2026-03-01T10:00:00",
        )

    def test_returns_joined_exercise_fields(self):
        rows = find_top_similar_mistakes(self.conn, "target")
        self.assertEqual(len(rows), 2)
        prompts = {r["question_sentence"] for r in rows}
        self.assertSetEqual(prompts, {"質問A", "質問B"})
        for r in rows:
            self.assertGreaterEqual(r["similarity"], SIMILARITY_THRESHOLD)
            self.assertIn("log_id", r)
            self.assertIn("user_answer", r)
            self.assertIn("correct_answer", r)

    def test_top_k_caps_results(self):
        _insert_exercise(self.conn, "ex-c", prompt="質問C", answer="答えC")
        _insert_log(
            self.conn,
            "past-c",
            exercise_id="ex-c",
            embedding=self.q_vec,
            timestamp="2026-02-01T10:00:00",
        )
        rows = find_top_similar_mistakes(self.conn, "target", top_k=2)
        self.assertEqual(len(rows), 2)

    def test_below_threshold_excluded(self):
        # Replace past-a with a low-similarity vector
        self.conn.execute("DELETE FROM answer_log WHERE log_id = 'past-a'")
        low = _unit_vector(1)  # orthogonal to q_vec
        _insert_log(
            self.conn,
            "past-a",
            exercise_id="ex-a",
            embedding=low,
        )
        rows = find_top_similar_mistakes(self.conn, "target")
        # past-b is still identical → above threshold, past-a is orthogonal
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["log_id"], "past-b")


class TestAnnotateFeedback(unittest.TestCase):
    def test_appends_when_similar_history_exists(self):
        conn = _make_conn()
        q_vec = _unit_vector(0)
        _insert_exercise(conn, "ex-target")
        _insert_log(conn, "target", exercise_id="ex-target", embedding=q_vec)
        _insert_exercise(conn, "ex-other")
        _insert_log(
            conn,
            "past",
            exercise_id="ex-other",
            embedding=q_vec,
            timestamp="2026-04-01T10:00:00",
        )
        result = annotate_feedback(conn, "target", "原始回饋")
        self.assertIn("原始回饋", result)
        self.assertIn("你已經犯過 1 次類似的錯", result)
        self.assertIn("Apr 01, 2026", result)

    def test_no_op_when_no_similar_history(self):
        conn = _make_conn()
        q_vec = _unit_vector(0)
        _insert_exercise(conn, "ex-target")
        _insert_log(conn, "target", exercise_id="ex-target", embedding=q_vec)
        result = annotate_feedback(conn, "target", "原始回饋")
        self.assertEqual(result, "原始回饋")


if __name__ == "__main__":
    unittest.main()
