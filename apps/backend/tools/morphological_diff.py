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
    tokens = list(_tok().tokenize(text))
    verbs: list[dict] = []
    particles: list[str] = []
    aux_negations = 0       # 助動詞 with base ない / ぬ / ず
    surface_negation = False  # ない or ぬ as surface text — rescue path

    for i, tok in enumerate(tokens):
        pos = tok.part_of_speech.split(",")
        head = pos[0]
        if head == "動詞":
            base_form = _categorise_form(tok.infl_form or "")
            # Compound form key — distinguishes te-form (連用タ接続 + て)
            # from past (連用タ接続 + た) and polite (連用形 + ます)
            # from polite-negative-stem (連用形 + ます with the next ん
            # tagged separately, see polite_negations below). Without
            # this both 終わった and 終わって collapse to "ta_stem".
            tail = ""
            if i + 1 < len(tokens):
                nxt = tokens[i + 1]
                nxt_pos = nxt.part_of_speech.split(",")
                nxt_head = nxt_pos[0]
                nxt_sub = nxt_pos[1] if len(nxt_pos) > 1 else ""
                if nxt_head == "助動詞":
                    tail = nxt.base_form or nxt.surface
                elif nxt_head == "助詞" and nxt_sub == "接続助詞":
                    tail = nxt.base_form or nxt.surface
            form_key = f"{base_form}+{tail}" if tail else base_form
            verbs.append({
                "surface": tok.surface,
                "base": tok.base_form or tok.surface,
                "form": form_key,
            })
        elif head == "助詞":
            particles.append(tok.surface)
        elif head == "助動詞":
            base = tok.base_form or tok.surface
            if base in ("ない", "ぬ", "ず"):
                aux_negations += 1
        if "ない" in tok.surface or tok.surface == "ぬ":
            surface_negation = True

    # Polite negation: janome splits ません into ませ (base=ます) + ん
    # (base=ん, NOT ぬ), so the auxiliary-base scan above misses every
    # ます-form negation. Surface-detect each ません — count repeats so
    # double clauses still tally correctly.
    polite_negations = text.count("ません")

    negation_count = aux_negations + polite_negations
    if negation_count == 0 and surface_negation:
        # i-adjective ない / standalone ぬ that wasn't tagged as 助動詞.
        negation_count = 1

    return {
        "verbs": verbs,
        "particles": particles,
        "particle_set": sorted(set(particles)),
        "negation_count": negation_count,
    }


# Content POS heads we treat as "lemmas" for clause-role comparison —
# verbs and nouns capture the agent + action of each clause. Adjectives
# included so descriptive clauses also distinguish.
_CONTENT_HEADS = {"動詞", "名詞", "形容詞", "形容動詞"}

# Nouns that act as structural relative-time / position markers inside
# common connector patterns (〜たあとで, 〜まえに, 〜あいだに, 〜とおり,
# 〜ときに, 〜ところで, 〜ためには, 〜ばあいは…). They tokenise as 名詞
# but they're part of the connector, not the clause content. Excluding
# them from swap-detection lemma sets stops 〜あとで from looking
# asymmetric just because 'あと' rides on the pre-comma clause both
# times. Kanji forms included so kanji-spelt sources behave the same.
_CONNECTOR_NOUN_STEMS = frozenset({
    "あと", "まえ", "あいだ", "うち", "とおり",
    "とき", "ところ", "ため", "ばあい", "ほう",
    "なか", "うえ", "した", "ほか", "もの",
    "後", "前", "間", "内", "通り", "時", "所", "為",
    "場合", "方", "中", "上", "下", "他", "物",
})


def _content_lemmas(text: str) -> set[str]:
    """Bases of content words in a clause — used for role-swap detection.

    Skips particles, auxiliaries, punctuation, conjunctions, adverbs,
    and the structural connector-noun stems above.
    """
    out: set[str] = set()
    for tok in _tok().tokenize(text):
        head = tok.part_of_speech.split(",")[0]
        if head in _CONTENT_HEADS:
            base = tok.base_form or tok.surface
            if base and base != "*" and base not in _CONNECTOR_NOUN_STEMS:
                out.add(base)
    return out


def _split_at_comma(text: str) -> Optional[tuple[str, str]]:
    """Split on the first clause-boundary comma. None if no useful split."""
    for sep in ("、", ","):
        idx = text.find(sep)
        if 0 < idx < len(text) - 1:
            return text[:idx].strip(), text[idx + 1:].strip()
    return None


def _detect_role_swap(reference: str, user: str) -> bool:
    """True when reference and user have the same two-clause structure
    but their content sets are reversed across the comma — the
    canonical "wrong-order" failure mode for connector patterns
    (〜てから, 〜たあとで, 〜まえに, 〜ば, 〜と, 〜なら, 〜ながら)
    where the verbs and nouns are right but the order carries the
    meaning. The check the morph-diff anchor cannot otherwise see.
    """
    ref_split = _split_at_comma(reference)
    user_split = _split_at_comma(user)
    if not ref_split or not user_split:
        return False

    ref_pre = _content_lemmas(ref_split[0])
    ref_post = _content_lemmas(ref_split[1])
    user_pre = _content_lemmas(user_split[0])
    user_post = _content_lemmas(user_split[1])

    if not (ref_pre and ref_post and user_pre and user_post):
        return False

    # Same content per side (no swap) → not a role swap.
    if ref_pre == user_pre and ref_post == user_post:
        return False

    # Crossed assignment: reference's pre-set ≡ user's post-set, and
    # reference's post-set ≡ user's pre-set.
    return ref_pre == user_post and ref_post == user_pre


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
    role_swap = _detect_role_swap(reference, user)
    if role_swap:
        parts.append("role_swap: TRUE (clauses reversed across the comma)")
    summary = "; ".join(parts)

    return {
        "reference": ref,
        "user": usr,
        "shared_verb_bases": shared_bases,
        "verb_form_match": verb_form_match,
        "particle_jaccard": round(particle_jaccard, 3),
        "negation_match": negation_match,
        "role_swap_detected": role_swap,
        "summary": summary,
    }
