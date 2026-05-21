"""Tests for `services.cloze`.

Janome is intentionally *not* exercised here — `find_candidates`,
`choose_target`, and `build_question_sentence` operate on a duck-typed
TokenLike protocol, so we feed them lightweight `FakeToken` dataclasses.
This keeps the suite fast and decoupled from Janome's dictionary version.

The `make_cloze` wrapper is exercised through a `FakeTokenizer` that
returns pre-built token lists — same idea applied one level up.
"""
from __future__ import annotations

import random
import unittest
from dataclasses import dataclass

from services.cloze import (
    BLANK_MARKER,
    Cloze,
    build_question_sentence,
    choose_target,
    find_candidates,
    make_cloze,
)


@dataclass
class FakeToken:
    """Minimal stand-in for janome.tokenizer.Token in tests.

    Matches the TokenLike protocol — surface + base_form + comma-joined POS.
    """

    surface: str
    base_form: str
    part_of_speech: str  # comma-joined as Janome emits ("助詞,係助詞,*,*")


class FakeTokenizer:
    """Returns the exact token list it was constructed with."""

    def __init__(self, tokens: list[FakeToken]):
        self._tokens = tokens

    def tokenize(self, sentence: str):  # noqa: ARG002  -- sentence intentionally unused
        return self._tokens


# A small reusable token bag — Tarō reads a book in school today.
# Just enough variety to cover surface-vs-base_form and POS fallback.
def _sample_tokens() -> list[FakeToken]:
    return [
        FakeToken("太郎", "太郎", "名詞,固有名詞,*,*"),
        FakeToken("は", "は", "助詞,係助詞,*,*"),
        FakeToken("学校", "学校", "名詞,一般,*,*"),
        FakeToken("で", "で", "助詞,格助詞,*,*"),
        FakeToken("本", "本", "名詞,一般,*,*"),
        FakeToken("を", "を", "助詞,格助詞,*,*"),
        FakeToken("読んだ", "読む", "動詞,自立,*,*"),
        FakeToken("。", "。", "記号,句点,*,*"),
    ]


class TestFindCandidates(unittest.TestCase):
    def test_matches_jlpt_by_surface(self):
        tokens = _sample_tokens()
        cands = find_candidates(tokens, {"本": 5})
        # `本` matches; `は で を` are 助詞 fallback; `読んだ` is 動詞 fallback.
        # `太郎`, `学校` are 名詞 (no fallback). `。` is 記号 (no fallback).
        levels = {c.surface: c.jlpt_level for c in cands}
        self.assertEqual(levels["本"], 5)
        self.assertIsNone(levels["は"])
        self.assertIn("読んだ", levels)
        self.assertNotIn("学校", levels)  # 名詞 with no JLPT entry is dropped
        self.assertNotIn("。", levels)

    def test_matches_jlpt_by_base_form(self):
        tokens = _sample_tokens()
        # `読んだ` (surface) is the conjugated form; vocab is keyed on 読む.
        cands = find_candidates(tokens, {"読む": 4})
        read_cand = next(c for c in cands if c.surface == "読んだ")
        self.assertEqual(read_cand.jlpt_level, 4)
        self.assertEqual(read_cand.matched_vocab_key, "読む")

    def test_surface_match_preferred_over_base(self):
        # If both surface and base_form are in the vocab, surface wins —
        # avoids surprising level reassignments for irregular conjugations.
        tokens = [FakeToken("読んだ", "読む", "動詞,自立,*,*")]
        cands = find_candidates(tokens, {"読んだ": 3, "読む": 5})
        self.assertEqual(cands[0].jlpt_level, 3)
        self.assertEqual(cands[0].matched_vocab_key, "読んだ")

    def test_jlpt_match_records_matched_key(self):
        tokens = _sample_tokens()
        cands = find_candidates(tokens, {"本": 5})
        book = next(c for c in cands if c.surface == "本")
        self.assertEqual(book.matched_vocab_key, "本")

    def test_pos_fallback_records_none_matched_key(self):
        tokens = _sample_tokens()
        cands = find_candidates(tokens, {})
        wa = next(c for c in cands if c.surface == "は")
        self.assertIsNone(wa.matched_vocab_key)

    def test_jlpt_priority_over_pos_fallback(self):
        # A particle (は) that's also in JLPT vocab should report its level,
        # not the fallback None.
        tokens = [FakeToken("は", "は", "助詞,係助詞,*,*")]
        cands = find_candidates(tokens, {"は": 5})
        self.assertEqual(cands[0].jlpt_level, 5)
        self.assertEqual(cands[0].matched_vocab_key, "は")

    def test_skips_empty_surface(self):
        # Zero-width Janome tokens would otherwise render as an empty blank.
        tokens = [
            FakeToken("", "", "助詞,係助詞,*,*"),
            FakeToken("本", "本", "名詞,一般,*,*"),
        ]
        cands = find_candidates(tokens, {"本": 5})
        self.assertEqual([c.surface for c in cands], ["本"])

    def test_non_fallback_pos_with_no_vocab_match_is_dropped(self):
        tokens = [
            FakeToken("太郎", "太郎", "名詞,固有名詞,*,*"),
            FakeToken("です", "です", "助動詞,*,*,*"),
        ]
        self.assertEqual(find_candidates(tokens, {}), [])

    def test_primary_pos_only(self):
        # part_of_speech is comma-joined; we should split on the first comma.
        tokens = [FakeToken("で", "で", "助詞,格助詞,*,*")]
        cands = find_candidates(tokens, {})
        self.assertEqual(cands[0].part_of_speech, "助詞")

    def test_token_index_preserved(self):
        tokens = _sample_tokens()
        cands = find_candidates(tokens, {"本": 5})
        book = next(c for c in cands if c.surface == "本")
        self.assertEqual(book.token_index, 4)  # 0:太郎 1:は 2:学校 3:で 4:本


class TestChooseTarget(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(choose_target([]))

    def test_deterministic_with_seeded_rng(self):
        cands = find_candidates(_sample_tokens(), {})
        rng = random.Random(42)
        # Two calls with fresh seeds produce the same pick.
        rng2 = random.Random(42)
        self.assertEqual(choose_target(cands, rng=rng), choose_target(cands, rng=rng2))

    def test_returns_one_of_input(self):
        cands = find_candidates(_sample_tokens(), {})
        picked = choose_target(cands, rng=random.Random(0))
        self.assertIn(picked, cands)


class TestBuildQuestionSentence(unittest.TestCase):
    def test_replaces_target_with_blank(self):
        tokens = _sample_tokens()
        # index 4 is `本`
        out = build_question_sentence(tokens, 4)
        self.assertEqual(out, f"太郎は学校で{BLANK_MARKER}を読んだ。")

    def test_custom_blank_marker(self):
        tokens = _sample_tokens()
        out = build_question_sentence(tokens, 4, blank="___")
        self.assertEqual(out, "太郎は学校で___を読んだ。")

    def test_index_at_boundaries(self):
        tokens = _sample_tokens()
        self.assertTrue(build_question_sentence(tokens, 0).startswith(BLANK_MARKER))
        self.assertTrue(build_question_sentence(tokens, len(tokens) - 1).endswith(BLANK_MARKER))

    def test_oob_index_raises(self):
        tokens = _sample_tokens()
        with self.assertRaises(IndexError):
            build_question_sentence(tokens, len(tokens))
        with self.assertRaises(IndexError):
            build_question_sentence(tokens, -1)


class TestMakeCloze(unittest.TestCase):
    def test_returns_none_when_no_candidates(self):
        # All-名詞 sentence, no vocab match → no candidates → None.
        tokens = [
            FakeToken("太郎", "太郎", "名詞,固有名詞,*,*"),
            FakeToken("学校", "学校", "名詞,一般,*,*"),
        ]
        cloze = make_cloze("太郎学校", {}, tokenizer=FakeTokenizer(tokens))
        self.assertIsNone(cloze)

    def test_produces_cloze_with_expected_shape(self):
        tokens = _sample_tokens()
        cloze = make_cloze(
            "太郎は学校で本を読んだ。",
            {"本": 5},
            tokenizer=FakeTokenizer(tokens),
            rng=random.Random(0),
        )
        self.assertIsInstance(cloze, Cloze)
        # Whatever was picked, the question must contain exactly one blank
        # and the rest of the surfaces must concatenate to the original
        # when the blank is removed.
        self.assertEqual(cloze.question_sentence.count(BLANK_MARKER), 1)
        self.assertEqual(cloze.full_sentence, "太郎は学校で本を読んだ。")
        self.assertEqual(
            cloze.question_sentence.replace(BLANK_MARKER, cloze.correct_answer),
            "太郎は学校で本を読んだ。",
        )

    def test_rng_pins_selection(self):
        tokens = _sample_tokens()
        a = make_cloze(
            "x", {"本": 5}, tokenizer=FakeTokenizer(tokens), rng=random.Random(7),
        )
        b = make_cloze(
            "x", {"本": 5}, tokenizer=FakeTokenizer(tokens), rng=random.Random(7),
        )
        assert a is not None and b is not None
        self.assertEqual(a.correct_answer, b.correct_answer)

    def test_carries_matched_vocab_key_through(self):
        # A vocab match via base_form: surface 読んだ, base 読む, vocab keyed on 読む.
        tokens = [FakeToken("読んだ", "読む", "動詞,自立,*,*")]
        cloze = make_cloze(
            "読んだ",
            {"読む": 4},
            tokenizer=FakeTokenizer(tokens),
            rng=random.Random(0),
        )
        assert cloze is not None
        self.assertEqual(cloze.matched_vocab_key, "読む")
        self.assertEqual(cloze.correct_answer, "読んだ")
        self.assertEqual(cloze.jlpt_level, 4)


if __name__ == "__main__":
    unittest.main()
