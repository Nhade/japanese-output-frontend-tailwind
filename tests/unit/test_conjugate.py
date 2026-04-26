"""Conjugation tool tests — broad coverage across verb classes and forms."""
import unittest

from tools.conjugate import VerbClass, classify, conjugate


class TestClassify(unittest.TestCase):

    def test_ichidan(self):
        self.assertEqual(classify("食べる"), (VerbClass.ICHIDAN, "食べる"))
        self.assertEqual(classify("見る"), (VerbClass.ICHIDAN, "見る"))

    def test_godan(self):
        self.assertEqual(classify("行く"), (VerbClass.GODAN, "行く"))
        self.assertEqual(classify("話す"), (VerbClass.GODAN, "話す"))
        self.assertEqual(classify("飲む"), (VerbClass.GODAN, "飲む"))
        self.assertEqual(classify("作る"), (VerbClass.GODAN, "作る"))

    def test_suru_and_kuru(self):
        self.assertEqual(classify("する")[0], VerbClass.SURU)
        self.assertEqual(classify("勉強する")[0], VerbClass.SURU)
        self.assertEqual(classify("来る")[0], VerbClass.KURU)

    def test_rejects_non_verb(self):
        with self.assertRaises(ValueError):
            classify("猫")  # noun
        with self.assertRaises(ValueError):
            classify("赤い")  # adjective


class TestConjugateIchidan(unittest.TestCase):

    def test_taberu_full_paradigm(self):
        cases = {
            "masu": "食べます",
            "te": "食べて",
            "ta": "食べた",
            "nai": "食べない",
            "nakatta": "食べなかった",
            "ba": "食べれば",
            "volitional": "食べよう",
            "potential": "食べられる",
            "passive": "食べられる",
            "causative": "食べさせる",
        }
        for form, expected in cases.items():
            with self.subTest(form=form):
                self.assertEqual(conjugate("食べる", form), expected)


class TestConjugateGodan(unittest.TestCase):

    def test_iku_irregular_te_ta(self):
        # 行く takes 行って / 行った, NOT 行いて / 行いた.
        self.assertEqual(conjugate("行く", "te"), "行って")
        self.assertEqual(conjugate("行く", "ta"), "行った")
        # Other forms follow regular 五段 rules.
        self.assertEqual(conjugate("行く", "masu"), "行きます")
        self.assertEqual(conjugate("行く", "nai"), "行かない")
        self.assertEqual(conjugate("行く", "ba"), "行けば")
        self.assertEqual(conjugate("行く", "volitional"), "行こう")

    def test_hanasu(self):
        self.assertEqual(conjugate("話す", "masu"), "話します")
        self.assertEqual(conjugate("話す", "te"), "話して")
        self.assertEqual(conjugate("話す", "nai"), "話さない")
        self.assertEqual(conjugate("話す", "ba"), "話せば")
        self.assertEqual(conjugate("話す", "potential"), "話せる")
        self.assertEqual(conjugate("話す", "passive"), "話される")
        self.assertEqual(conjugate("話す", "causative"), "話させる")

    def test_nomu(self):
        # む → んで / んだ euphonic change.
        self.assertEqual(conjugate("飲む", "te"), "飲んで")
        self.assertEqual(conjugate("飲む", "ta"), "飲んだ")
        self.assertEqual(conjugate("飲む", "masu"), "飲みます")
        self.assertEqual(conjugate("飲む", "nai"), "飲まない")

    def test_tsukuru(self):
        # 五段 in -る — distinct from 一段.
        self.assertEqual(conjugate("作る", "masu"), "作ります")
        self.assertEqual(conjugate("作る", "te"), "作って")
        self.assertEqual(conjugate("作る", "nai"), "作らない")
        self.assertEqual(conjugate("作る", "ba"), "作れば")
        self.assertEqual(conjugate("作る", "potential"), "作れる")


class TestConjugateSuru(unittest.TestCase):

    def test_plain_suru(self):
        cases = {
            "masu": "します",
            "te": "して",
            "ta": "した",
            "nai": "しない",
            "ba": "すれば",
            "volitional": "しよう",
            "potential": "できる",
            "passive": "される",
            "causative": "させる",
        }
        for form, expected in cases.items():
            with self.subTest(form=form):
                self.assertEqual(conjugate("する", form), expected)

    def test_compound_suru(self):
        # Compound する verbs: stem + する.
        self.assertEqual(conjugate("勉強する", "masu"), "勉強します")
        self.assertEqual(conjugate("勉強する", "te"), "勉強して")
        self.assertEqual(conjugate("勉強する", "nai"), "勉強しない")
        self.assertEqual(conjugate("勉強する", "potential"), "勉強できる")


class TestConjugateKuru(unittest.TestCase):

    def test_kuru(self):
        # 来 reads き for masu/te/ta, こ for nai/volitional/potential/etc.
        # Surface form (kanji) is what we return.
        self.assertEqual(conjugate("来る", "masu"), "来ます")
        self.assertEqual(conjugate("来る", "te"), "来て")
        self.assertEqual(conjugate("来る", "ta"), "来た")
        self.assertEqual(conjugate("来る", "nai"), "来ない")
        self.assertEqual(conjugate("来る", "ba"), "来れば")
        self.assertEqual(conjugate("来る", "volitional"), "来よう")
        self.assertEqual(conjugate("来る", "potential"), "来られる")
        self.assertEqual(conjugate("来る", "causative"), "来させる")


class TestConjugateErrors(unittest.TestCase):

    def test_unsupported_form(self):
        with self.assertRaises(ValueError):
            conjugate("食べる", "imperative")

    def test_non_verb(self):
        with self.assertRaises(ValueError):
            conjugate("猫", "masu")


if __name__ == "__main__":
    unittest.main()
