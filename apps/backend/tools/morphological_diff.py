"""
Morphological diff tool — compare two Japanese sentences using janome.

Used by the rubric evaluator as a *concrete anchor* so the LLM has
something deterministic to defer to. Without this the judge invents
naturalness criteria each call (the open complaint behind score drift).

The diff doesn't decide a score on its own — it surfaces:
  - which verb dictionary forms appear in each
  - which particles appear in each
  - whether the negation polarity matches
  - whether the user's verb-form *categories* (te/ta/nai/...) match
    the reference at the shared lemmas

If the user matches the reference on lemmas + verb-form categories +
particles, the rubric MUST NOT score lower for "naturalness" alone.
"""
from typing import Optional

from janome.tokenizer import Tokenizer

_tokenizer: Optional[Tokenizer] = None


def _tok() -> Tokenizer:
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return _tokenizer


# Janome's `infl_form` strings to a coarse category the LLM can reason about.
_FORM_CATEGORY = {
    "基本形":       "dictionary",
    "未然形":       "negative_stem",
    "未然ウ接続":   "volitional_stem",
    "未然レル接続": "passive_stem",
    "連用形":       "i_stem",
    "連用タ接続":   "ta_stem",
    "連用テ接続":   "te_stem",
    "仮定形":       "ba_stem",
    "命令形":       "imperative",
    "体言接続":     "noun_modifier",
}


def _categorise_form(infl_form: str) -> str:
    return _FORM_CATEGORY.get(infl_form, infl_form or "unknown")


def _features(text: str) -> dict:
    """Extract verb / particle / negation summary from one sentence."""
    verbs: list[dict] = []
    particles: list[str] = []
    aux_negations = 0  # 'ない', 'ぬ', 'ず' as 助動詞
    explicit_negations = 0  # surface form contains 'ない' / 'ぬ'

    for tok in _tok().tokenize(text):
        pos = tok.part_of_speech.split(",")
        head = pos[0]
        if head == "動詞":
            verbs.append({
                "surface": tok.surface,
                "base": tok.base_form or tok.surface,
                "form": _categorise_form(tok.infl_form or ""),
            })
        elif head == "助詞":
            particles.append(tok.surface)
        elif head == "助動詞":
            base = tok.base_form or tok.surface
            if base in ("ない", "ぬ", "ず"):
                aux_negations += 1
        if "ない" in tok.surface or "ぬ" == tok.surface:
            explicit_negations += 1

    return {
        "verbs": verbs,
        "particles": particles,
        "particle_set": sorted(set(particles)),
        "negation_count": aux_negations + (
            # `explicit_negations` rescues e.g. ない as an i-adjective ending.
            1 if (explicit_negations and aux_negations == 0) else 0
        ),
    }


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def morphological_diff(reference: str, user: str) -> dict:
    """Compare reference and user Japanese sentences.

    Returns:
        {
          "reference":  {verbs, particles, particle_set, negation_count},
          "user":       same shape,
          "shared_verb_bases":  sorted intersection of verb dict-forms,
          "verb_form_match":    bool — for every shared lemma, the user's
                                verb-form category equals the reference's,
          "particle_jaccard":   0..1 over distinct particles,
          "negation_match":     reference.negation_count == user.negation_count,
          "summary": "..."     # short human-readable line for the rubric
        }
    """
    ref = _features(reference)
    usr = _features(user)

    shared_bases = sorted(
        {v["base"] for v in ref["verbs"]} & {v["base"] for v in usr["verbs"]}
    )
    # For each shared base, do all forms agree?
    def forms_for(features: dict, base: str) -> set[str]:
        return {v["form"] for v in features["verbs"] if v["base"] == base}

    verb_form_match = bool(shared_bases) and all(
        forms_for(ref, b) == forms_for(usr, b) for b in shared_bases
    )

    particle_jaccard = _jaccard(set(ref["particle_set"]),
                                set(usr["particle_set"]))
    negation_match = ref["negation_count"] == usr["negation_count"]

    parts: list[str] = []
    parts.append(
        f"shared lemmas: {', '.join(shared_bases) if shared_bases else '(none)'}"
    )
    parts.append(
        f"verb-form match: {verb_form_match}"
    )
    parts.append(
        f"particle overlap: {particle_jaccard:.2f} "
        f"(ref={ref['particle_set']} user={usr['particle_set']})"
    )
    parts.append(f"negation match: {negation_match}")
    summary = "; ".join(parts)

    return {
        "reference": ref,
        "user": usr,
        "shared_verb_bases": shared_bases,
        "verb_form_match": verb_form_match,
        "particle_jaccard": round(particle_jaccard, 3),
        "negation_match": negation_match,
        "summary": summary,
    }
