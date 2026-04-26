"""
detect_pattern tool — given a sentence and a grammar_pattern_id, decide
whether the sentence uses that pattern.

v1 strategy:
  1. If grammar_patterns.detector_spec is set, follow its rules.
  2. Otherwise, derive a kana stem from the pattern name and substring
     match. Strips the leading 〜/～ and the final conjugating kana
     (う/く/ぐ/す/つ/ぬ/ぶ/む/る/い), so 〜てしまう → "てしま" matches
     てしまう / てしまった / てしまわない.

This is a best-effort baseline; richer detectors can be authored later
by populating detector_spec (JSON):

    {
      "required_substrings":   [...],   # all must be present
      "negative_substrings":   [...],   # none may be present
      "any_of_substrings":     [...]    # at least one must be present
    }

Returns a dict {detected, matched, reason}. The LLM evaluator and the
verifier node both call this; never trust LLM-reported pattern usage.
"""
import json
import sqlite3
from typing import Optional

# Final kana that mark conjugating endings; safe to strip from a pattern
# name to derive the invariant stem.
_CONJ_ENDINGS = set("うくぐすつぬぶむるい")


def _derive_stem(pattern_name: str) -> str:
    """Strip leading wave-tilde and a single trailing conjugating kana.

    Examples:
        〜てしまう → 'てしま'
        〜ば      → 'ば'
        〜たい    → 'た'  (see note below)
        〜ことができる → 'ことができ'

    For very short results (<2 chars) we keep the original ending to
    reduce false positives. The fallback is documented as best-effort —
    populate detector_spec for finer control.
    """
    s = pattern_name.lstrip('〜～').strip()
    if len(s) >= 3 and s[-1] in _CONJ_ENDINGS:
        return s[:-1]
    return s


def _match_spec(sentence: str, spec: dict) -> tuple[bool, list[str], str]:
    matched: list[str] = []
    reasons: list[str] = []

    for sub in spec.get("required_substrings") or []:
        if sub in sentence:
            matched.append(sub)
        else:
            reasons.append(f"missing required substring {sub!r}")

    if reasons:
        return False, matched, "; ".join(reasons)

    for sub in spec.get("negative_substrings") or []:
        if sub in sentence:
            return False, matched, f"contains forbidden substring {sub!r}"

    any_of = spec.get("any_of_substrings") or []
    if any_of:
        hits = [s for s in any_of if s in sentence]
        if not hits:
            return False, matched, "none of any_of_substrings found"
        matched.extend(hits)

    if not matched:
        return False, [], "spec produced no matches"

    return True, matched, "matched detector_spec"


def detect_pattern(conn: sqlite3.Connection, sentence: str,
                   pattern_id: str) -> dict:
    """Check whether `sentence` uses the grammar pattern with `pattern_id`.

    Returns:
        {
          "detected": bool,
          "matched": list[str],   # substrings that triggered detection
          "reason": str,          # human-readable explanation
          "stem": str,            # the stem actually searched (fallback path)
          "pattern_name": str
        }
    """
    row = conn.execute(
        "SELECT name, detector_spec FROM grammar_patterns "
        "WHERE pattern_id = ?", (pattern_id,)
    ).fetchone()
    if not row:
        return {
            "detected": False, "matched": [], "stem": "",
            "pattern_name": "", "reason": f"pattern {pattern_id} not found",
        }

    name = row["name"] if hasattr(row, "keys") else row[0]
    spec_json: Optional[str] = (row["detector_spec"] if hasattr(row, "keys")
                                else row[1])

    if spec_json:
        try:
            spec = json.loads(spec_json)
            ok, matched, reason = _match_spec(sentence, spec)
            return {
                "detected": ok, "matched": matched, "stem": "",
                "pattern_name": name, "reason": reason,
            }
        except (ValueError, TypeError) as e:
            # Bad spec → fall through to stem-based detection.
            stem_reason_prefix = f"detector_spec invalid ({e}); fell back. "
        else:
            stem_reason_prefix = ""
    else:
        stem_reason_prefix = ""

    stem = _derive_stem(name)
    if stem and stem in sentence:
        return {
            "detected": True, "matched": [stem], "stem": stem,
            "pattern_name": name,
            "reason": stem_reason_prefix + f"stem {stem!r} found in sentence",
        }
    return {
        "detected": False, "matched": [], "stem": stem,
        "pattern_name": name,
        "reason": stem_reason_prefix + f"stem {stem!r} not in sentence",
    }
