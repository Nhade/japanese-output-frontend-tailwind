"""Tests for the detect_pattern tool — both fallback and detector_spec paths."""
import json
import sqlite3
import unittest
import uuid
from datetime import datetime

from document_service import create_document_tables
from practice_service import create_practice_tables
from tools.detect_pattern import _derive_stem, detect_pattern


def _fresh_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE users (user_id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO users (user_id) VALUES ('u1')")
    create_document_tables(conn)
    create_practice_tables(conn)
    conn.execute('''
        INSERT INTO documents (doc_id, user_id, title, source_type,
                               status, created_timestamp)
        VALUES ('d1', 'u1', 't', 'grammar_notes', 'ready', ?)
    ''', (datetime.now().isoformat(),))
    return conn


def _seed_pattern(conn, name: str,
                  detector_spec: dict | None = None) -> str:
    pid = str(uuid.uuid4())
    conn.execute('''
        INSERT INTO grammar_patterns
        (pattern_id, doc_id, name, confidence, status, detector_spec,
         created_timestamp)
        VALUES (?, 'd1', ?, 1.0, 'published', ?, ?)
    ''', (pid, name,
          json.dumps(detector_spec) if detector_spec else None,
          datetime.now().isoformat()))
    conn.commit()
    return pid


class TestDeriveStem(unittest.TestCase):

    def test_strips_tilde_and_verb_ending(self):
        self.assertEqual(_derive_stem("〜てしまう"), "てしま")
        self.assertEqual(_derive_stem("〜ことができる"), "ことができ")

    def test_keeps_short_forms_intact(self):
        # Stems shorter than 3 chars stay whole; otherwise stripping would
        # produce single-character matches that false-positive everywhere.
        self.assertEqual(_derive_stem("〜たい"), "たい")
        self.assertEqual(_derive_stem("～ば"), "ば")


class TestDetectFallback(unittest.TestCase):

    def test_te_shimau_matches_conjugations(self):
        conn = _fresh_db()
        pid = _seed_pattern(conn, "〜てしまう")

        cases = {
            "食べてしまった":   True,   # past
            "食べてしまう":     True,   # dictionary
            "食べてしまわない": True,   # negative
            "食べた":          False,  # plain past, no しまう
            "本を読みました":   False,
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence=sentence):
                result = detect_pattern(conn, sentence, pid)
                self.assertEqual(result["detected"], expected, result["reason"])

    def test_unknown_pattern_returns_not_detected(self):
        conn = _fresh_db()
        result = detect_pattern(conn, "食べた", "no-such-id")
        self.assertFalse(result["detected"])
        self.assertIn("not found", result["reason"])

    def test_kanji_alternate_matches_when_pattern_named_in_kana(self):
        # Pattern was extracted with kana name 〜とおり; learner writes
        # the kanji form 計画通り. Without the alias table this misses.
        conn = _fresh_db()
        pid = _seed_pattern(conn, "〜とおり")
        result = detect_pattern(conn, "計画通り、行ってください。", pid)
        self.assertTrue(result["detected"], result["reason"])
        self.assertIn("通り", result["matched"])

    def test_kana_form_still_matches_after_alias_added(self):
        conn = _fresh_db()
        pid = _seed_pattern(conn, "〜とおり")
        result = detect_pattern(conn, "計画のとおり進める。", pid)
        self.assertTrue(result["detected"])
        self.assertIn("とおり", result["matched"])


class TestDetectorSpec(unittest.TestCase):

    def test_required_substring_must_all_be_present(self):
        conn = _fresh_db()
        pid = _seed_pattern(conn, "〜ば良かった",
                            detector_spec={
                                "required_substrings": ["ば", "良かった"],
                            })
        ok = detect_pattern(conn, "勉強すれば良かった", pid)
        self.assertTrue(ok["detected"])

        miss = detect_pattern(conn, "勉強すれば", pid)
        self.assertFalse(miss["detected"])
        self.assertIn("required substring", miss["reason"])

    def test_negative_substring_blocks_match(self):
        conn = _fresh_db()
        pid = _seed_pattern(conn, "〜ば",
                            detector_spec={
                                "required_substrings": ["ば"],
                                "negative_substrings": ["ばかり"],
                            })
        self.assertTrue(detect_pattern(conn, "食べれば", pid)["detected"])
        # Has 'ば' but also forbidden 'ばかり' (different pattern).
        self.assertFalse(
            detect_pattern(conn, "食べてばかりいる", pid)["detected"]
        )

    def test_any_of_substrings(self):
        conn = _fresh_db()
        pid = _seed_pattern(conn, "〜たい",
                            detector_spec={
                                "any_of_substrings": ["たい", "たく", "たかっ"],
                            })
        self.assertTrue(detect_pattern(conn, "食べたい", pid)["detected"])
        self.assertTrue(detect_pattern(conn, "食べたくない", pid)["detected"])
        self.assertTrue(detect_pattern(conn, "食べたかった", pid)["detected"])
        self.assertFalse(detect_pattern(conn, "食べる", pid)["detected"])

    def test_invalid_spec_falls_back_to_stem(self):
        conn = _fresh_db()
        # detector_spec is malformed JSON in DB — fallback should kick in.
        pid = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO grammar_patterns
            (pattern_id, doc_id, name, confidence, status, detector_spec,
             created_timestamp)
            VALUES (?, 'd1', '〜てしまう', 1.0, 'published', '{not json',
             ?)
        ''', (pid, datetime.now().isoformat()))
        conn.commit()
        result = detect_pattern(conn, "食べてしまった", pid)
        self.assertTrue(result["detected"])
        self.assertIn("fell back", result["reason"])


if __name__ == "__main__":
    unittest.main()
