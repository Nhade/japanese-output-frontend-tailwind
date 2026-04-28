"""Unit tests for grammar-pattern extraction (LLM mocked).

Covers schema parsing, the confidence → status split, per-chunk error
tolerance, and the full run_extraction lifecycle against an in-memory DB.
"""
import json
import os
import sqlite3
import tempfile
import unittest

from document_service import create_document_tables, ingest_document
from extraction_service import (
    ExtractionResponse,
    _compute_default_detector_spec,
    enqueue_extraction,
    extract_from_chunk,
    get_job,
    normalize_pattern_name,
    run_extraction,
)
from practice_service import create_practice_tables, reset_stale_jobs


def _make_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE users (user_id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO users (user_id) VALUES ('u1')")
    create_document_tables(conn)
    create_practice_tables(conn)
    return conn


class TestNormalize(unittest.TestCase):

    def test_tilde_aliases_canonicalize(self):
        self.assertEqual(normalize_pattern_name("～てしまう"), "〜てしまう")
        self.assertEqual(normalize_pattern_name("~てしまう"),  "〜てしまう")
        self.assertEqual(normalize_pattern_name("〜てしまう"), "〜てしまう")

    def test_strips_leading_ordinal(self):
        self.assertEqual(normalize_pattern_name("1. 〜とおり"), "〜とおり")
        self.assertEqual(normalize_pattern_name("2、〜あとで"), "〜あとで")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_pattern_name("  〜  ば  "), "〜 ば")


class TestDetectorSpecHelper(unittest.TestCase):

    def test_known_pattern_yields_substring_spec(self):
        spec = _compute_default_detector_spec("〜てしまう")
        self.assertEqual(spec, {"required_substrings": ["てしま"]})

    def test_blank_name_returns_none(self):
        self.assertIsNone(_compute_default_detector_spec(""))


class TestExtractFromChunk(unittest.TestCase):

    def test_parses_well_formed_response(self):
        fake_response = {
            "patterns": [
                {
                    "name": "〜てしまう",
                    "reading": "-teshimau",
                    "meaning_locale": "表示動作完成或遺憾",
                    "formation_rule": "て-form + しまう",
                    "jlpt": 4,
                    "register": "plain",
                    "examples": [
                        {"sentence": "食べてしまった",
                         "translation": "不小心吃光了",
                         "is_canonical": True},
                    ],
                    "confidence": 0.95,
                }
            ]
        }
        result = extract_from_chunk("# 〜てしまう\n\n...", "zh-tw",
                                    llm_fn=lambda _msgs: fake_response)
        self.assertIsInstance(result, ExtractionResponse)
        self.assertEqual(len(result.patterns), 1)
        self.assertEqual(result.patterns[0].name, "〜てしまう")
        self.assertAlmostEqual(result.patterns[0].confidence, 0.95)

    def test_empty_patterns_is_valid(self):
        result = extract_from_chunk("prose only", "en",
                                    llm_fn=lambda _msgs: {"patterns": []})
        self.assertEqual(result.patterns, [])

    def test_invalid_confidence_rejected(self):
        bad = {"patterns": [{"name": "X", "confidence": 1.5}]}
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            extract_from_chunk("x", "en", llm_fn=lambda _msgs: bad)


class TestRunExtraction(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        self.db_path = self.tmpfile.name
        self.conn = _make_db(self.db_path)
        md = ("# 〜てしまう\n\n意味：完了・残念。\n\n例：食べてしまった。\n\n"
              "# 〜ば\n\n条件節を作る。\n\n例：食べれば。")
        r = ingest_document(self.conn, "u1", "Notes", "grammar_notes",
                            md, "notes.md")
        self.doc_id = r["doc_id"]

    def tearDown(self):
        self.conn.close()
        os.unlink(self.db_path)

    def _stub_llm(self, per_chunk: list[dict]):
        """Return a stub that yields one response per call."""
        calls = iter(per_chunk)
        def fn(_messages):
            return next(calls)
        return fn

    def test_end_to_end_persists_patterns_with_status_split(self):
        job_id = enqueue_extraction(self.conn, self.doc_id, "u1", "zh-tw")

        stub = self._stub_llm([
            # Chunk 0: 〜てしまう at high confidence → published
            {"patterns": [{
                "name": "〜てしまう", "meaning_locale": "完了/遺憾",
                "examples": [{"sentence": "食べてしまった",
                              "translation": "不小心吃光了",
                              "is_canonical": True}],
                "confidence": 0.9,
            }]},
            # Chunk 1: 〜ば at low confidence → pending_review
            {"patterns": [{
                "name": "〜ば", "meaning_locale": "條件",
                "examples": [],
                "confidence": 0.5,
            }]},
        ])

        result = run_extraction(self.db_path, job_id, llm_fn=stub)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["processed_chunks"], 2)
        self.assertEqual(result["patterns_extracted"], 2)
        self.assertEqual(result["patterns_published"], 1)
        self.assertEqual(result["patterns_pending"], 1)

        # Document marked ready.
        doc_status = self.conn.execute(
            "SELECT status FROM documents WHERE doc_id = ?", (self.doc_id,)
        ).fetchone()["status"]
        self.assertEqual(doc_status, "ready")

        # Statuses reflect the threshold split.
        statuses = sorted(
            r["status"] for r in self.conn.execute(
                "SELECT status FROM grammar_patterns WHERE doc_id = ?",
                (self.doc_id,)
            ).fetchall()
        )
        self.assertEqual(statuses, ["pending_review", "published"])

        # meaning_locale is stored, meaning_en is not populated (by design).
        row = self.conn.execute(
            "SELECT meaning_locale, meaning_en FROM grammar_patterns "
            "WHERE name = '〜てしまう'"
        ).fetchone()
        self.assertEqual(row["meaning_locale"], "完了/遺憾")
        self.assertIsNone(row["meaning_en"])

        # Example persisted with is_canonical.
        ex = self.conn.execute(
            "SELECT sentence, is_canonical FROM pattern_examples"
        ).fetchone()
        self.assertEqual(ex["sentence"], "食べてしまった")
        self.assertEqual(ex["is_canonical"], 1)

    def test_per_chunk_failure_does_not_fail_job(self):
        job_id = enqueue_extraction(self.conn, self.doc_id, "u1", "en")

        def stub(_messages):
            # First call raises, second returns valid response.
            if not hasattr(stub, "called"):
                stub.called = True
                raise RuntimeError("LLM upstream error")
            return {"patterns": [{
                "name": "〜ば", "meaning_locale": "if", "examples": [],
                "confidence": 0.9,
            }]}

        result = run_extraction(self.db_path, job_id, llm_fn=stub)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["patterns_extracted"], 1)
        self.assertIsNotNone(result["error"])
        self.assertIn("chunk 0", result["error"])

    def test_dedups_pattern_across_chunks(self):
        # Same normalized name appears in two chunk extractions —
        # second occurrence should merge into the first row, not insert
        # a duplicate. Examples are deduped by sentence.
        job_id = enqueue_extraction(self.conn, self.doc_id, "u1", "en")

        first = {"patterns": [{
            "name": "～てしまう",  # fullwidth tilde — should normalise to 〜
            "meaning_locale": "completion/regret",
            "examples": [{"sentence": "食べてしまった",
                          "translation": "ate it",
                          "is_canonical": True}],
            "confidence": 0.7,  # below threshold
        }]}
        second = {"patterns": [{
            "name": "1. 〜てしまう",  # ordinal prefix; same pattern
            "meaning_locale": "完了/遺憾",
            "examples": [
                {"sentence": "食べてしまった",       # duplicate sentence
                 "translation": "ate", "is_canonical": False},
                {"sentence": "忘れてしまった",       # new
                 "translation": "forgot", "is_canonical": False},
            ],
            "confidence": 0.95,  # above threshold; should upgrade status
        }]}
        result = run_extraction(self.db_path, job_id,
                                llm_fn=self._stub_llm([first, second]))
        self.assertEqual(result["status"], "complete")

        rows = self.conn.execute(
            "SELECT pattern_id, name, confidence, status, detector_spec "
            "FROM grammar_patterns WHERE doc_id = ?",
            (self.doc_id,)
        ).fetchall()
        # Only one row for the dedup'd pattern.
        names = [r["name"] for r in rows]
        self.assertEqual(names.count("〜てしまう"), 1, names)
        merged = next(r for r in rows if r["name"] == "〜てしまう")

        # Confidence bumped to the higher of the two.
        self.assertAlmostEqual(merged["confidence"], 0.95)
        # Status upgraded from pending_review → published.
        self.assertEqual(merged["status"], "published")
        # detector_spec materialised from the canonical name.
        self.assertIsNotNone(merged["detector_spec"])

        # Examples appended without duplicating "食べてしまった".
        examples = self.conn.execute(
            "SELECT sentence FROM pattern_examples "
            "WHERE pattern_id = ?", (merged["pattern_id"],)
        ).fetchall()
        sentences = sorted(e["sentence"] for e in examples)
        self.assertEqual(sentences, ["忘れてしまった", "食べてしまった"])

    def test_detector_spec_populated_on_persist(self):
        job_id = enqueue_extraction(self.conn, self.doc_id, "u1", "en")
        stub = self._stub_llm([
            {"patterns": [{
                "name": "〜てしまう", "meaning_locale": "x", "examples": [],
                "confidence": 0.95,
            }]},
            {"patterns": []},
        ])
        run_extraction(self.db_path, job_id, llm_fn=stub)
        row = self.conn.execute(
            "SELECT detector_spec FROM grammar_patterns "
            "WHERE doc_id = ?", (self.doc_id,)
        ).fetchone()
        spec = json.loads(row["detector_spec"])
        # Stem-derivation drops the trailing 'う' from the canonical form.
        self.assertEqual(spec, {"required_substrings": ["てしま"]})

    def test_reset_stale_jobs_marks_running_failed(self):
        job_id = enqueue_extraction(self.conn, self.doc_id, "u1", "en")
        self.conn.execute(
            "UPDATE extraction_jobs SET status = 'running' WHERE job_id = ?",
            (job_id,)
        )
        self.conn.commit()
        reset_stale_jobs(self.conn)
        job = get_job(self.conn, job_id)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], "interrupted")


if __name__ == "__main__":
    unittest.main()
