"""Tests for morphological_diff."""
import unittest

from tools.morphological_diff import morphological_diff


class TestMorphologicalDiff(unittest.TestCase):

    def test_identical_sentences_full_match(self):
        d = morphological_diff("食べてしまった", "食べてしまった")
        # Janome surfaces both 食べる and the auxiliary しまう as verbs.
        self.assertIn("食べる", d["shared_verb_bases"])
        self.assertIn("しまう", d["shared_verb_bases"])
        self.assertTrue(d["verb_form_match"])
        self.assertEqual(d["particle_jaccard"], 1.0)
        self.assertTrue(d["negation_match"])

    def test_same_lemma_different_form_flagged(self):
        # Reference is past, user is dictionary form — same lemma, different form.
        d = morphological_diff("食べてしまった", "食べてしまう")
        self.assertIn("食べる", d["shared_verb_bases"])
        self.assertIn("しまう", d["shared_verb_bases"])
        # しまう differs in form (ta_stem vs dictionary) → mismatch.
        self.assertFalse(d["verb_form_match"])

    def test_negation_polarity_mismatch_detected(self):
        d = morphological_diff("食べてしまった", "食べてしまわなかった")
        self.assertFalse(d["negation_match"])
        self.assertGreaterEqual(d["user"]["negation_count"], 1)

    def test_particle_overlap(self):
        d = morphological_diff("ケーキを食べた", "ケーキは食べた")
        self.assertLess(d["particle_jaccard"], 1.0)
        # Shared lemma with same form.
        self.assertIn("食べる", d["shared_verb_bases"])
        self.assertTrue(d["verb_form_match"])

    def test_different_verbs_no_shared_bases(self):
        d = morphological_diff("ケーキを食べた", "本を読んだ")
        self.assertEqual(d["shared_verb_bases"], [])
        # No shared lemmas → verb_form_match defaults to False.
        self.assertFalse(d["verb_form_match"])

    def test_summary_string_is_compact(self):
        d = morphological_diff("食べた", "食べた")
        # All four fields appear.
        self.assertIn("verb-form match", d["summary"])
        self.assertIn("particle overlap", d["summary"])
        self.assertIn("negation match", d["summary"])


class TestRubricAnchorFixes(unittest.TestCase):
    """Regressions previously surfaced by rubric drift.

    Each case here was producing a False-positive `verb_form_match` or
    `negation_match`, letting the rubric judge mark opposite-meaning
    answers as "matches the reference's grammatical shape" and skip a
    deduction.
    """

    def test_te_form_vs_ta_form_distinguished(self):
        # 終わった (past) and 終わって (te-form) share the same verb
        # infl_form 連用タ接続; the discriminator is the trailing
        # auxiliary た vs particle て.
        d = morphological_diff("終わった", "終わって")
        self.assertEqual(d["shared_verb_bases"], ["終わる"])
        self.assertFalse(d["verb_form_match"], d["summary"])

    def test_te_form_vs_te_form_still_matches(self):
        d = morphological_diff("終わって", "終わって")
        self.assertTrue(d["verb_form_match"])

    def test_polite_negation_via_masen(self):
        # 行きます vs 行きません — janome marks the inner ん with
        # base="ん", not "ぬ", so the auxiliary scan misses it. Surface
        # detection of ません must catch it.
        d = morphological_diff("行きます", "行きません")
        self.assertFalse(d["negation_match"], d["summary"])
        self.assertEqual(d["user"]["negation_count"], 1)
        self.assertEqual(d["reference"]["negation_count"], 0)

    def test_polite_past_negation_masendeshita(self):
        d = morphological_diff("行きます", "行きませんでした")
        self.assertFalse(d["negation_match"])
        self.assertEqual(d["user"]["negation_count"], 1)

    def test_double_polite_negation_counts_twice(self):
        d = morphological_diff("食べる",
                               "食べません、行きません")
        self.assertEqual(d["user"]["negation_count"], 2)

    def test_plain_negation_still_counts(self):
        # Sanity: the polite-negation rescue must not double-count
        # plain forms.
        d = morphological_diff("行く", "行かない")
        self.assertEqual(d["user"]["negation_count"], 1)

    def test_mixed_plain_and_polite_negation(self):
        d = morphological_diff("食べる",
                               "食べない。行きません。")
        self.assertEqual(d["user"]["negation_count"], 2)


class TestRoleSwapDetection(unittest.TestCase):
    """Connector patterns (〜てから, 〜たあとで, 〜まえに, 〜ば, 〜と,
    〜なら, 〜ながら) carry meaning in clause order. The morph-diff
    anchor on its own treats two clause-reversed sentences as a
    "shape match" because lemmas, particles, and forms are identical
    — only the order differs. role_swap_detected is the deterministic
    signal that prevents the anchor from protecting a wrong-meaning
    answer.
    """

    def test_te_kara_role_swap_caught(self):
        # The exact handoff case: same lemmas (宿題, ゲーム, する),
        # same connector (〜てから), reversed clauses → opposite meaning.
        d = morphological_diff(
            "宿題をしてから、ゲームをします",
            "ゲームをしてから、宿題をします",
        )
        self.assertTrue(d["role_swap_detected"], d["summary"])

    def test_identical_two_clause_is_not_role_swap(self):
        d = morphological_diff(
            "宿題をしてから、ゲームをします",
            "宿題をしてから、ゲームをします",
        )
        self.assertFalse(d["role_swap_detected"])

    def test_single_clause_returns_false(self):
        # No comma → no clause split → role_swap_detected stays false.
        d = morphological_diff("食べてしまった", "食べてしまった")
        self.assertFalse(d["role_swap_detected"])

    def test_partial_overlap_is_not_role_swap(self):
        # User changed one of the clauses but didn't reverse — content
        # sets are not crossed, so no role swap.
        d = morphological_diff(
            "宿題をしてから、ゲームをします",
            "宿題をしてから、本を読みます",
        )
        self.assertFalse(d["role_swap_detected"])

    def test_ato_de_role_swap_caught(self):
        # Reverse the same two action-clauses across あとで.
        d = morphological_diff(
            "宿題をしたあとで、ゲームをします",
            "ゲームをしたあとで、宿題をします",
        )
        self.assertTrue(d["role_swap_detected"], d["summary"])


if __name__ == "__main__":
    unittest.main()
