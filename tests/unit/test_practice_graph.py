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

    def test_fallback_uses_localized_template(self):
        # zh-tw fallback must use Chinese phrasing, not English.
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
                return {
                    "prompt_locale_text": "x",
                    "reference_answer_jp": "本を読んだ",  # forces fallback
                }
            raise AssertionError(sys[:80])

        result = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"],
            locale="zh-tw", llm_fn=llm,
        )
        ex = result["exercise"]
        self.assertEqual(ex["source"], "fallback_canonical")
        # The template's leading phrase appears, in Chinese.
        self.assertIn("請使用", ex["prompt"])
        # The pattern name is bracketed with 「」 in every locale.
        self.assertIn("「〜てしまう」", ex["prompt"])
        # No English boilerplate left over.
        self.assertNotIn("Translate", ex["prompt"])
        self.assertNotIn("(Traditional Chinese):", ex["prompt"])

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

    def test_progress_counters_on_exercise(self):
        # Range covers two published patterns. First call: index=1 of 2.
        llm, _ = _make_llm(self.ctx["p1"])
        first = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"], llm_fn=llm,
        )
        self.assertEqual(first["exercise"]["pattern_count_in_range"], 2)
        self.assertEqual(first["exercise"]["pattern_index_in_session"], 1)

    def test_exclude_drives_rotation(self):
        # First exercise targets p1; passing p1 in exclude pushes the
        # planner to p2.
        first_llm, _ = _make_llm(self.ctx["p1"])
        first = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"], llm_fn=first_llm,
        )
        self.assertEqual(first["exercise"]["target_pattern_id"], self.ctx["p1"])

        second_llm, _ = _make_llm(self.ctx["p2"], ref_answer="行けば")
        second = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"],
            llm_fn=second_llm,
            exclude_pattern_ids=[self.ctx["p1"]],
        )
        self.assertEqual(second["exercise"]["target_pattern_id"], self.ctx["p2"])
        self.assertEqual(second["exercise"]["pattern_count_in_range"], 2)
        self.assertEqual(second["exercise"]["pattern_index_in_session"], 2)

    def test_session_complete_when_all_excluded(self):
        result = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"],
            llm_fn=lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("should not be called")),
            exclude_pattern_ids=[self.ctx["p1"], self.ctx["p2"]],
        )
        self.assertEqual(result.get("error"), "session_complete")
        self.assertEqual(result["total_in_range"], 2)
        self.assertEqual(result["covered_in_session"], 2)

    def test_planner_invented_id_rejected_after_exclude(self):
        # Defensive: after excluding p1, the planner is offered only p2.
        # If it still invents another id we reject — already covered by
        # test_planner_rejects_invented_id but reverified post-filter.
        def llm(messages, _t):
            sys = messages[0]["content"]
            if "practice planner" in sys:
                return {
                    "target_pattern_id": self.ctx["p1"],  # excluded
                    "strategy": "pattern_use",
                    "difficulty": 3,
                    "variant_hint": "x",
                }
            return {}
        result = generate_exercise(
            self.db_path, "u1", self.ctx["range_id"],
            llm_fn=llm,
            exclude_pattern_ids=[self.ctx["p1"]],
        )
        self.assertEqual(result.get("error"), "plan_invented_pattern_id")


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
        # Result carries the morphological diff + register target so the
        # frontend (and any future audit) can see what the rubric saw.
        self.assertEqual(result["target_register"], "plain")
        self.assertIsNotNone(result["morph_diff"])
        self.assertIn("食べる", result["morph_diff"]["shared_verb_bases"])

    def test_rubric_payload_includes_register_and_diff(self):
        # Capture what the rubric judge actually receives so the contract
        # the prompt expects is locked in by tests, not just docs.
        captured: list[dict] = []
        def judge(messages):
            captured.append(json.loads(messages[1]["content"]))
            return {
                "score": 0.8, "used_pattern": True,
                "feedback_text": "ok", "issues": [],
            }
        evaluate_pattern_use_submission(
            self.db_path, self.exercise_id, "u1",
            "ケーキを食べてしまった",
            llm_fn=judge,
        )
        self.assertEqual(len(captured), 1)
        payload = captured[0]
        # Register travels through.
        self.assertEqual(payload["target_register"], "plain")
        # Morph diff travels through with the five signal fields the
        # rubric prompt references.
        self.assertIn("morph_diff", payload)
        for key in ("shared_verb_bases", "verb_form_match",
                    "particle_jaccard", "negation_match",
                    "role_swap_detected"):
            self.assertIn(key, payload["morph_diff"])
        # Prompt travels through so check 3's topic match has something
        # to evaluate against; without this the rubric was judging a
        # synthetic "topic" with no anchor.
        self.assertIn("prompt_locale_text", payload)
        # Detector still travels through, unchanged.
        self.assertTrue(payload["detector_result"]["detected"])

    def test_role_swap_caps_score_at_half(self):
        # The handoff case: same lemmas, reversed across the comma.
        # Even if the rubric judge hallucinates a high score, the
        # deterministic backstop must cap at 0.5 so a wrong-meaning
        # answer can never read as "is_correct".
        # First, create an exercise whose reference uses 〜てから and
        # has a comma split so role-swap detection has something to
        # work with.
        db_conn = sqlite3.connect(self.db_path)
        db_conn.row_factory = sqlite3.Row
        kara_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        db_conn.execute('''
            INSERT INTO grammar_patterns
            (pattern_id, doc_id, source_chunk_id, name, jlpt, register,
             meaning_locale, formation_rule, confidence, status,
             created_timestamp)
            VALUES (?, ?, NULL, '〜てから', 4, 'polite',
                    'do A first then B', 'て-form + から', 0.95,
                    'published', ?)
        ''', (kara_id, self.ctx["doc_id"], now))
        ex_id = str(uuid.uuid4())
        db_conn.execute('''
            INSERT INTO exercises
            (exercise_id, user_id, range_id, type, target_pattern_id,
             difficulty, prompt, expected_json, rubric_json, seed,
             source, created_timestamp)
            VALUES (?, 'u1', ?, 'pattern_use', ?, 3,
                    'Use 〜てから to say: do homework first, then play games.',
                    ?, '{}', 'seed', 'graph', ?)
        ''', (ex_id, self.ctx["range_id"], kara_id,
              json.dumps({
                  "reference_answer_jp": "宿題をしてから、ゲームをします",
                  "target_pattern_id": kara_id,
                  "target_pattern_name": "〜てから",
                  "target_register": "polite",
              }), now))
        db_conn.commit()
        db_conn.close()

        # Judge hallucinates "great answer!" — the cap must override it.
        def cheating_judge(_msgs):
            return {
                "score": 0.95,
                "used_pattern": True,
                "feedback_text": "Looks good!",
                "issues": [],
            }
        result = evaluate_pattern_use_submission(
            self.db_path, ex_id, "u1",
            "ゲームをしてから、宿題をします",   # clauses reversed
            llm_fn=cheating_judge,
        )
        self.assertLessEqual(result["score"], 0.5,
                             f"role_swap should cap; got {result}")
        self.assertFalse(result["is_correct"])
        self.assertIn("role_swap", result["issues"])
        self.assertTrue(result["morph_diff"]["role_swap_detected"])

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
