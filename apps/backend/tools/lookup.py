"""
Lookup tools — typed reads the LangGraph nodes use to get grounded
inputs. None of these involve an LLM; the planner / executor / evaluator
call them so their decisions reference the actual catalog instead of
hallucinated ids or examples.

Public API:
  - lookup_pattern(conn, pattern_id)
  - search_examples(conn, pattern_id, k=3)
  - srs_due(conn, user_id, range_id)
  - learner_weak_points(conn, user_id)

`srs_due` is currently a uniform-weight stub (returns all published
patterns whose source chunk is in the range, capped at `limit`). Real
spaced-repetition scheduling is deferred to a follow-up; the function
signature is the contract the planner can rely on now.
"""
import json
import sqlite3
from typing import List, Optional


def lookup_pattern(conn: sqlite3.Connection,
                   pattern_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM grammar_patterns WHERE pattern_id = ?", (pattern_id,)
    ).fetchone()
    return dict(row) if row else None


def search_examples(conn: sqlite3.Connection, pattern_id: str,
                    k: int = 3) -> List[dict]:
    """Return up to k examples for a pattern, canonical first."""
    rows = conn.execute(
        "SELECT example_id, sentence, translation, is_canonical, "
        "cloze_mask_hint "
        "FROM pattern_examples WHERE pattern_id = ? "
        "ORDER BY is_canonical DESC, created_timestamp ASC "
        "LIMIT ?", (pattern_id, k)
    ).fetchall()
    return [dict(r) for r in rows]


def srs_due(conn: sqlite3.Connection, user_id: str, range_id: str,
            limit: int = 20) -> List[dict]:
    """Patterns due for practice in a range.

    v1 stub: every published pattern whose source chunk is part of the
    range. No scheduling; the planner picks one at random or by weak-
    point overlap.
    """
    row = conn.execute(
        "SELECT chunk_ids_json, doc_id FROM practice_ranges "
        "WHERE range_id = ? AND user_id = ?", (range_id, user_id)
    ).fetchone()
    if not row:
        return []

    chunk_ids = json.loads(row["chunk_ids_json"])
    if not chunk_ids:
        return []

    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"SELECT pattern_id, name, reading, jlpt, register, "
        f"meaning_locale, formation_rule "
        f"FROM grammar_patterns "
        f"WHERE doc_id = ? AND status = 'published' "
        f"AND source_chunk_id IN ({placeholders}) "
        f"LIMIT ?",
        (row["doc_id"], *chunk_ids, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def learner_weak_points(conn: sqlite3.Connection,
                        user_id: str) -> List[str]:
    """Return weak_points list from learner_profiles (empty if missing)."""
    row = conn.execute(
        "SELECT profile_json FROM learner_profiles WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    if not row:
        return []
    try:
        profile = json.loads(row["profile_json"])
    except (TypeError, ValueError):
        return []
    weak = profile.get("weak_points") or []
    return [w for w in weak if isinstance(w, str)]
