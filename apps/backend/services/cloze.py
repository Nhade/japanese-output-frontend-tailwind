"""Shared cloze-deletion mechanics used by both article and video pipelines.

This module owns only the cloze-construction primitives:
  * Tokenizing a sentence (lazy Janome singleton)
  * Identifying candidate positions for a blank
  * Choosing a target
  * Building the masked question sentence

It deliberately does NOT own:
  * Sentence selection / splitting (article and video segment text differently)
  * JLPT vocab DB schema (callers pass a minimal {surface_or_base: level} map)
  * Hint generation (article uses sentence-translation; video prefers a word
    meaning lookup with sentence-translation fallback — see `Cloze.matched_vocab_key`)
  * Database writes
  * LLM verification

Both callers retain ownership of their own pipeline glue; this module is the
kernel they share.
"""
from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from janome.tokenizer import Tokenizer

BLANK_MARKER = "[＿＿＿]"

# Parts of speech eligible for blanking when no JLPT-graded vocab match is
# available at a given token. Mirrors the pre-existing behaviour in both call
# sites — particles and verbs are dense enough in news/transcript prose that
# we can almost always find one.
_FALLBACK_POS = frozenset({"助詞", "動詞"})


class TokenLike(Protocol):
    """Subset of janome.Token that the cloze code reads.

    Declared as a Protocol so tests can pass plain dataclasses — instantiating
    a real Janome tokenizer for every unit test is heavy and ties test
    behaviour to the dictionary version.
    """

    surface: str
    base_form: str
    part_of_speech: str  # comma-joined POS tag string, as Janome emits


@dataclass(frozen=True)
class Candidate:
    """A position in a tokenized sentence eligible for cloze masking."""

    token_index: int
    surface: str
    part_of_speech: str  # primary POS, already split from the comma-string
    jlpt_level: int | None
    # The actual key in `jlpt_levels` that matched (surface or base_form), or
    # None if this candidate was admitted via the POS fallback. The video
    # pipeline uses this to re-look-up the matched vocab entry's `meaning`
    # field for the hint; the article pipeline ignores it.
    matched_vocab_key: str | None


@dataclass(frozen=True)
class Cloze:
    """Shared output shape returned by `make_cloze`."""

    full_sentence: str
    question_sentence: str
    correct_answer: str
    part_of_speech: str
    jlpt_level: int | None
    matched_vocab_key: str | None


_tokenizer: Tokenizer | None = None


def _get_default_tokenizer() -> Tokenizer:
    """Lazy module-level Janome tokenizer.

    Janome is ~100ms to construct; reusing one across calls keeps batch
    generation snappy. Each former call site (`tools/exercise_generator.py`
    and `apps/backend/video_service.py`) built its own — folding here
    removes that duplication too.
    """
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return _tokenizer


def find_candidates(
    tokens: Sequence[TokenLike],
    jlpt_levels: Mapping[str, int],
) -> list[Candidate]:
    """Find positions eligible to be blanked out.

    Priority: tokens whose surface or base form is in `jlpt_levels` (any JLPT
    level wins over POS fallback). Fallback: tokens whose primary POS is 助詞
    or 動詞. Empty surfaces are skipped — Janome occasionally emits
    zero-width tokens for punctuation/whitespace fragments and they'd render
    as an empty blank.

    Candidates are returned in token order; selection happens in
    `choose_target`.
    """
    candidates: list[Candidate] = []
    for i, token in enumerate(tokens):
        if not token.surface:
            continue
        primary_pos = token.part_of_speech.split(",", 1)[0]

        # Vocab lookup: prefer surface match, fall back to lemma. The vocab
        # table is keyed on dictionary form, so most conjugated verbs and
        # adjective forms only hit via base_form.
        matched_key: str | None = None
        level: int | None = None
        if token.surface in jlpt_levels:
            matched_key = token.surface
            level = jlpt_levels[token.surface]
        elif token.base_form in jlpt_levels:
            matched_key = token.base_form
            level = jlpt_levels[token.base_form]

        if level is not None:
            candidates.append(Candidate(i, token.surface, primary_pos, level, matched_key))
        elif primary_pos in _FALLBACK_POS:
            candidates.append(Candidate(i, token.surface, primary_pos, None, None))
    return candidates


def choose_target(
    candidates: Sequence[Candidate],
    *,
    rng: random.Random | None = None,
) -> Candidate | None:
    """Pick one candidate uniformly at random. Returns None on empty input.

    `rng` is injectable so tests can pin selection without monkey-patching
    the global `random` module.
    """
    if not candidates:
        return None
    chooser = rng if rng is not None else random
    return chooser.choice(list(candidates))


def build_question_sentence(
    tokens: Sequence[TokenLike],
    target_index: int,
    *,
    blank: str = BLANK_MARKER,
) -> str:
    """Render the masked sentence by replacing one token's surface with `blank`.

    Concatenates token surfaces — Japanese does not use whitespace between
    morphemes, so naive join is the correct render.
    """
    if not 0 <= target_index < len(tokens):
        raise IndexError(
            f"target_index {target_index} out of range for {len(tokens)} tokens"
        )
    parts = [blank if i == target_index else token.surface for i, token in enumerate(tokens)]
    return "".join(parts)


def make_cloze(
    sentence: str,
    jlpt_levels: Mapping[str, int],
    *,
    tokenizer: Tokenizer | None = None,
    rng: random.Random | None = None,
) -> Cloze | None:
    """Convenience wrapper: tokenize → find candidates → pick → build.

    Returns None if the sentence yields no candidates — caller should skip
    and try the next sentence. The lower-level pieces are exposed so callers
    that already have tokens (or want a different selection strategy) can
    bypass this wrapper.
    """
    tok = tokenizer or _get_default_tokenizer()
    tokens = list(tok.tokenize(sentence))
    candidates = find_candidates(tokens, jlpt_levels)
    target = choose_target(candidates, rng=rng)
    if target is None:
        return None
    return Cloze(
        full_sentence=sentence,
        question_sentence=build_question_sentence(tokens, target.token_index),
        correct_answer=target.surface,
        part_of_speech=target.part_of_speech,
        jlpt_level=target.jlpt_level,
        matched_vocab_key=target.matched_vocab_key,
    )
