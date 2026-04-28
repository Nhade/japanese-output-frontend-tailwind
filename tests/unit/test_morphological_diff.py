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


if __name__ == "__main__":
    unittest.main()
