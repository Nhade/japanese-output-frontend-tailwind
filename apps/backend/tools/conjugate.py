"""
Conjugate tool — turn a verb dictionary form into a target inflected form.

Closed system: 五段 / 一段 / サ変 / カ変 × {masu, te, ta, nai, nakatta, ba,
volitional, potential, passive, causative}. Janome classifies the verb;
hand-written rule tables produce the surface form. The LLM never inflects.

Public API:
    conjugate(verb_dict_form, form) -> str
    classify(verb_dict_form) -> (VerbClass, dict_form)

Raises ValueError for non-verbs, unknown forms, or unrecognised classes.
"""
from enum import StrEnum
from typing import Optional

from janome.tokenizer import Tokenizer

# Single shared tokenizer; janome init is expensive.
_tokenizer: Optional[Tokenizer] = None


def _tok() -> Tokenizer:
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return _tokenizer


class VerbClass(StrEnum):
    ICHIDAN = "ichidan"   # 一段 — 食べる, 見る
    GODAN = "godan"       # 五段 — 行く, 話す
    SURU = "suru"         # サ変 — する, 勉強する
    KURU = "kuru"         # カ変 — 来る


# 五段 stem maps. Indexed by the *final character* of the dictionary form.
_GODAN_STEM_A = {
    'う': 'わ', 'く': 'か', 'ぐ': 'が', 'す': 'さ', 'つ': 'た',
    'ぬ': 'な', 'ぶ': 'ば', 'む': 'ま', 'る': 'ら',
}
_GODAN_STEM_I = {
    'う': 'い', 'く': 'き', 'ぐ': 'ぎ', 'す': 'し', 'つ': 'ち',
    'ぬ': 'に', 'ぶ': 'び', 'む': 'み', 'る': 'り',
}
_GODAN_STEM_E = {
    'う': 'え', 'く': 'け', 'ぐ': 'げ', 'す': 'せ', 'つ': 'て',
    'ぬ': 'ね', 'ぶ': 'べ', 'む': 'め', 'る': 'れ',
}
_GODAN_STEM_O = {
    'う': 'お', 'く': 'こ', 'ぐ': 'ご', 'す': 'そ', 'つ': 'と',
    'ぬ': 'の', 'ぶ': 'ぼ', 'む': 'も', 'る': 'ろ',
}
# て-form: 五段 euphonic changes (音便).
_GODAN_TE = {
    'く': 'いて', 'ぐ': 'いで', 'す': 'して',
    'つ': 'って', 'う': 'って', 'る': 'って',
    'ぬ': 'んで', 'ぶ': 'んで', 'む': 'んで',
}
_GODAN_TA = {k: v[:-1] + ('だ' if v.endswith('で') else 'た')
             for k, v in _GODAN_TE.items()}

# Irregular: 行く takes 行って / 行った, not 行いて / 行いた.
_IRREGULAR_TE = {'行く': '行って', 'いく': 'いって'}
_IRREGULAR_TA = {'行く': '行った', 'いく': 'いった'}


def classify(verb: str) -> tuple[VerbClass, str]:
    """Identify the verb class for a dictionary-form verb.

    The irregulars する / 来る (and their compounds like 勉強する) are
    matched by suffix first because janome can split or misclassify them
    depending on whether they appear in a fuller sentence. Everything
    else falls through to janome's inflection-type label.

    Returns (class, dict_form). Raises ValueError if the input isn't a
    verb or its class isn't recognised.
    """
    # Irregulars first — bypass janome quirks.
    if verb == 'する' or (verb.endswith('する') and len(verb) > 2):
        return VerbClass.SURU, verb
    if verb in ('来る', 'くる'):
        return VerbClass.KURU, verb

    tokens = list(_tok().tokenize(verb))
    if not tokens:
        raise ValueError(f"Cannot tokenize: {verb!r}")
    tok = tokens[0]
    pos_parts = tok.part_of_speech.split(',')
    if pos_parts[0] != '動詞':
        raise ValueError(f"Not a verb: {verb!r} (POS={pos_parts[0]})")

    infl = tok.infl_type or ''
    base = tok.base_form or verb

    if infl.startswith('一段'):
        return VerbClass.ICHIDAN, base
    if infl.startswith('五段'):
        return VerbClass.GODAN, base
    if 'サ変' in infl:
        return VerbClass.SURU, base
    if 'カ変' in infl:
        return VerbClass.KURU, base
    raise ValueError(f"Unrecognised verb class for {verb!r}: infl={infl!r}")


# ---------------------------------------------------------------------------
# Form handlers — each takes (cls, dict_form) and returns the inflected form.
# ---------------------------------------------------------------------------

def _suru_stem(v: str) -> str:
    """Compound する verbs: '勉強する' → '勉強'. Plain する → ''."""
    if v.endswith('する'):
        return v[:-2]
    raise ValueError(f"Expected suru-class verb ending in する: {v!r}")


def _kuru_replace(v: str, suffix_kanji: str, suffix_kana: str) -> str:
    """カ変 — 来る/くる take different stems for different forms."""
    if v.endswith('来る'):
        return v[:-2] + '来' + suffix_kanji
    if v.endswith('くる'):
        return v[:-2] + suffix_kana
    raise ValueError(f"Expected kuru-class verb: {v!r}")


def _godan_last(v: str) -> str:
    last = v[-1]
    if last not in _GODAN_STEM_I:
        raise ValueError(f"Not a 五段 ending: {v!r} (last={last!r})")
    return last


def _masu(cls: VerbClass, v: str) -> str:
    if cls == VerbClass.ICHIDAN:
        return v[:-1] + 'ます'
    if cls == VerbClass.GODAN:
        last = _godan_last(v)
        return v[:-1] + _GODAN_STEM_I[last] + 'ます'
    if cls == VerbClass.SURU:
        return _suru_stem(v) + 'します'
    if cls == VerbClass.KURU:
        return _kuru_replace(v, 'ます', 'きます')


def _te(cls: VerbClass, v: str) -> str:
    if cls == VerbClass.ICHIDAN:
        return v[:-1] + 'て'
    if cls == VerbClass.GODAN:
        if v in _IRREGULAR_TE:
            return _IRREGULAR_TE[v]
        last = _godan_last(v)
        return v[:-1] + _GODAN_TE[last]
    if cls == VerbClass.SURU:
        return _suru_stem(v) + 'して'
    if cls == VerbClass.KURU:
        return _kuru_replace(v, 'て', 'きて')


def _ta(cls: VerbClass, v: str) -> str:
    if cls == VerbClass.ICHIDAN:
        return v[:-1] + 'た'
    if cls == VerbClass.GODAN:
        if v in _IRREGULAR_TA:
            return _IRREGULAR_TA[v]
        last = _godan_last(v)
        return v[:-1] + _GODAN_TA[last]
    if cls == VerbClass.SURU:
        return _suru_stem(v) + 'した'
    if cls == VerbClass.KURU:
        return _kuru_replace(v, 'た', 'きた')


def _nai(cls: VerbClass, v: str) -> str:
    if cls == VerbClass.ICHIDAN:
        return v[:-1] + 'ない'
    if cls == VerbClass.GODAN:
        last = _godan_last(v)
        return v[:-1] + _GODAN_STEM_A[last] + 'ない'
    if cls == VerbClass.SURU:
        return _suru_stem(v) + 'しない'
    if cls == VerbClass.KURU:
        # 来ない (こない) — 来 reads こ in nai-form.
        if v.endswith('来る'):
            return v[:-2] + '来ない'
        return v[:-2] + 'こない'


def _nakatta(cls: VerbClass, v: str) -> str:
    return _nai(cls, v)[:-1] + 'かった'


def _ba(cls: VerbClass, v: str) -> str:
    if cls == VerbClass.ICHIDAN:
        return v[:-1] + 'れば'
    if cls == VerbClass.GODAN:
        last = _godan_last(v)
        return v[:-1] + _GODAN_STEM_E[last] + 'ば'
    if cls == VerbClass.SURU:
        return _suru_stem(v) + 'すれば'
    if cls == VerbClass.KURU:
        return _kuru_replace(v, 'れば', 'くれば')


def _volitional(cls: VerbClass, v: str) -> str:
    if cls == VerbClass.ICHIDAN:
        return v[:-1] + 'よう'
    if cls == VerbClass.GODAN:
        last = _godan_last(v)
        return v[:-1] + _GODAN_STEM_O[last] + 'う'
    if cls == VerbClass.SURU:
        return _suru_stem(v) + 'しよう'
    if cls == VerbClass.KURU:
        if v.endswith('来る'):
            return v[:-2] + '来よう'
        return v[:-2] + 'こよう'


def _potential(cls: VerbClass, v: str) -> str:
    if cls == VerbClass.ICHIDAN:
        return v[:-1] + 'られる'
    if cls == VerbClass.GODAN:
        last = _godan_last(v)
        return v[:-1] + _GODAN_STEM_E[last] + 'る'
    if cls == VerbClass.SURU:
        return _suru_stem(v) + 'できる'
    if cls == VerbClass.KURU:
        if v.endswith('来る'):
            return v[:-2] + '来られる'
        return v[:-2] + 'こられる'


def _passive(cls: VerbClass, v: str) -> str:
    if cls == VerbClass.ICHIDAN:
        return v[:-1] + 'られる'
    if cls == VerbClass.GODAN:
        last = _godan_last(v)
        return v[:-1] + _GODAN_STEM_A[last] + 'れる'
    if cls == VerbClass.SURU:
        return _suru_stem(v) + 'される'
    if cls == VerbClass.KURU:
        if v.endswith('来る'):
            return v[:-2] + '来られる'
        return v[:-2] + 'こられる'


def _causative(cls: VerbClass, v: str) -> str:
    if cls == VerbClass.ICHIDAN:
        return v[:-1] + 'させる'
    if cls == VerbClass.GODAN:
        last = _godan_last(v)
        return v[:-1] + _GODAN_STEM_A[last] + 'せる'
    if cls == VerbClass.SURU:
        return _suru_stem(v) + 'させる'
    if cls == VerbClass.KURU:
        if v.endswith('来る'):
            return v[:-2] + '来させる'
        return v[:-2] + 'こさせる'


_HANDLERS = {
    'masu': _masu,
    'te': _te,
    'ta': _ta,
    'nai': _nai,
    'nakatta': _nakatta,
    'ba': _ba,
    'volitional': _volitional,
    'potential': _potential,
    'passive': _passive,
    'causative': _causative,
}


def conjugate(verb_dict_form: str, form: str) -> str:
    """Conjugate a Japanese verb into the requested form.

    Args:
        verb_dict_form: dictionary form (基本形), e.g. '食べる', '行く', '勉強する'.
        form: one of {'masu','te','ta','nai','nakatta','ba','volitional',
              'potential','passive','causative'}.

    Returns:
        The inflected surface form as a string.

    Raises:
        ValueError: input isn't a verb, class can't be recognised, or
                    `form` is unsupported.
    """
    handler = _HANDLERS.get(form)
    if handler is None:
        raise ValueError(
            f"Unsupported form: {form!r}. Supported: {sorted(_HANDLERS)}"
        )
    cls, dict_form = classify(verb_dict_form)
    return handler(cls, dict_form)


SUPPORTED_FORMS = tuple(_HANDLERS.keys())
