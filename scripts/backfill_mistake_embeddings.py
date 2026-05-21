"""
Backfill embeddings for existing wrong answer_log rows.

Run once after the schema migration adds the `embedding` and `embedding_model`
columns. Idempotent: skips rows that already have an embedding.

Usage:
    python scripts/backfill_mistake_embeddings.py
    python scripts/backfill_mistake_embeddings.py --batch-size 64 --limit 500
    python scripts/backfill_mistake_embeddings.py --reembed   # rebuild all rows
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time

from embedding_service import (
    _MODEL_NAME,
    embed_texts,
    ensure_embedding_columns,
    format_mistake_card,
    serialize,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data", "news_corpus.db"))


def fetch_pending(conn: sqlite3.Connection, *, reembed: bool, limit: int | None) -> list[sqlite3.Row]:
    sql = """
        SELECT al.log_id, al.user_answer, al.feedback, al.error_type,
               e.question_sentence AS prompt, e.correct_answer AS reference,
               e.part_of_speech, e.jlpt_level
        FROM answer_log al
        JOIN exercise e ON al.exercise_id = e.exercise_id
        WHERE al.is_correct = 0
    """
    if not reembed:
        sql += " AND al.embedding IS NULL"
    sql += " ORDER BY al.answered_timestamp DESC"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql).fetchall()


def backfill(db_path: str, *, batch_size: int = 32, reembed: bool = False, limit: int | None = None) -> None:
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    ensure_embedding_columns(conn)

    rows = fetch_pending(conn, reembed=reembed, limit=limit)
    total = len(rows)
    if total == 0:
        print("Nothing to backfill — all wrong rows already embedded.")
        return

    print(f"Embedding {total} mistake row(s) with {_MODEL_NAME}...")
    started = time.monotonic()

    cards = [
        format_mistake_card(
            prompt=r["prompt"] or "",
            reference=r["reference"] or "",
            user_answer=r["user_answer"] or "",
            error_type=r["error_type"],
            feedback=r["feedback"],
            section_label=f"{r['part_of_speech'] or ''} {r['jlpt_level'] or ''}".strip() or None,
        )
        for r in rows
    ]

    written = 0
    for start in range(0, total, batch_size):
        batch_rows = rows[start:start + batch_size]
        batch_cards = cards[start:start + batch_size]
        vectors = embed_texts(batch_cards, kind="passage", batch_size=batch_size)
        with conn:
            for row, vec in zip(batch_rows, vectors):
                conn.execute(
                    "UPDATE answer_log SET embedding = ?, embedding_model = ? WHERE log_id = ?",
                    (serialize(vec), _MODEL_NAME, row["log_id"]),
                )
        written += len(batch_rows)
        elapsed = time.monotonic() - started
        rate = written / elapsed if elapsed > 0 else 0.0
        print(f"  {written}/{total}  ({rate:.1f} rows/s)")

    conn.close()
    print(f"Done. Backfilled {written} row(s) in {time.monotonic() - started:.1f}s.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("SHIORI_DATABASE_PATH", DEFAULT_DB))
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=None, help="cap rows processed (debug)")
    parser.add_argument("--reembed", action="store_true", help="re-embed rows that already have an embedding")
    args = parser.parse_args()

    backfill(args.db, batch_size=args.batch_size, reembed=args.reembed, limit=args.limit)


if __name__ == "__main__":
    main()
