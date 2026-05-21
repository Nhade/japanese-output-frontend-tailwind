"""
Manual smoke test for cosine_search.

Picks a backfilled wrong row from answer_log, treats its mistake card as
a query, runs cosine_search against the user's other embeddings, and
prints the top-3 with similarity scores. The first hit should be the
query itself at ~1.0; subsequent hits should be conceptually related
(same particle confusion, same conjugation, same grammar pattern).

Usage:
    python scripts/smoke_test_cosine_search.py [--db PATH] [--top-k 3]

Not run in CI — needs the real model weights + a backfilled DB.
This file is intentionally a smoke test rather than a unit test;
proper integration coverage with mocked vectors is a separate follow-up.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

# Force UTF-8 on stdout so Japanese characters print on Windows consoles
# whose default codepage (e.g. cp950) can't encode them.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from embedding_service import (
    cosine_search,
    embed_text,
    format_mistake_card,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data", "news_corpus.db"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("SHIORI_DATABASE_PATH", DEFAULT_DB))
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # Pick a query row from the user with the most backfilled mistakes —
    # cosine_search is user-scoped, so a user with only one embedded row
    # produces a trivially-empty top-k beyond the self-match.
    target_user = conn.execute(
        """
        SELECT user_id
        FROM answer_log
        WHERE is_correct = 0 AND embedding IS NOT NULL
        GROUP BY user_id
        ORDER BY COUNT(*) DESC, user_id
        LIMIT 1
        """
    ).fetchone()
    if target_user is None:
        print("No backfilled rows. Run backfill_mistake_embeddings.py first.")
        sys.exit(1)

    query_row = conn.execute(
        """
        SELECT al.user_id, al.log_id, al.user_answer, al.feedback, al.error_type,
               e.question_sentence AS prompt, e.correct_answer AS reference,
               e.part_of_speech, e.jlpt_level
        FROM answer_log al
        JOIN exercise e ON al.exercise_id = e.exercise_id
        WHERE al.is_correct = 0 AND al.embedding IS NOT NULL AND al.user_id = ?
        ORDER BY al.log_id
        LIMIT 1
        """,
        (target_user["user_id"],),
    ).fetchone()

    section_label = (
        f"{query_row['part_of_speech'] or ''} {query_row['jlpt_level'] or ''}".strip()
        or None
    )
    card = format_mistake_card(
        prompt=query_row["prompt"] or "",
        reference=query_row["reference"] or "",
        user_answer=query_row["user_answer"] or "",
        error_type=query_row["error_type"],
        feedback=query_row["feedback"],
        section_label=section_label,
    )

    print("=== query mistake ===")
    print(f"user_id: {query_row['user_id']}")
    print(f"log_id:  {query_row['log_id']}")
    print(card)
    print()

    # Two ways to query — both should return the source row at ~1.0:
    # (a) re-embed the card with the "query:" prefix and run cosine_search
    # (b) read the stored embedding back and use it directly. We use (a)
    #     since it exercises the search_by_text-style path.
    q_emb = embed_text(card, kind="query")
    results = cosine_search(
        conn,
        user_id=query_row["user_id"],
        query_embedding=q_emb,
        top_k=args.top_k,
    )

    print(f"=== top-{args.top_k} cosine_search results ===")
    for i, r in enumerate(results, start=1):
        print(f"\n#{i}  similarity={r['similarity']:.4f}  log_id={r['log_id']}")
        print(f"  prompt: {r['prompt']}")
        print(f"  reference: {r['reference']}")
        print(f"  user:      {r['user_answer']}")
        if r.get("error_type"):
            print(f"  error_type: {r['error_type']}")

    conn.close()


if __name__ == "__main__":
    main()
