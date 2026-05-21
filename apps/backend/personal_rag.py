"""
Personal RAG annotation for grader feedback.

When a learner submits a wrong answer, surface their history of similar past
mistakes by appending a short "you've seen this kind of mistake before" line
to the AI feedback. Uses embeddings already stored on `answer_log` rows;
threshold-based cosine retrieval, same-user scoped, same-exercise excluded.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

import numpy as np

# Derived from the pairwise-similarity histogram in the embedding-quality
# report: above this cutoff, same-error pairs dominate cross-error pairs by
# a wide enough margin that "similar past mistake" is a defensible claim.
SIMILARITY_THRESHOLD = 0.92


def _deserialize(buf: bytes) -> np.ndarray:
    return np.frombuffer(buf, dtype=np.float32)


def _format_date(iso_ts: str) -> str:
    try:
        return datetime.fromisoformat(iso_ts).strftime("%b %d, %Y")
    except ValueError:
        return iso_ts[:10]


def find_similar_past_mistakes(
    conn: sqlite3.Connection,
    log_id: str,
    *,
    threshold: float = SIMILARITY_THRESHOLD,
) -> tuple[int, str | None]:
    """Count past mistakes from the same user that look like the given one.

    Returns (count, last_seen_date_iso). Same-exercise rows are excluded
    before ranking — repeat attempts at the same prompt would otherwise
    dominate the top of the list and the count would just measure retries.
    """
    target = conn.execute(
        "SELECT user_id, exercise_id, embedding FROM answer_log WHERE log_id = ?",
        (log_id,),
    ).fetchone()
    if not target or target["embedding"] is None:
        return 0, None

    query_emb = _deserialize(target["embedding"])
    qnorm = float(np.linalg.norm(query_emb))
    if qnorm == 0.0:
        return 0, None
    query_emb = query_emb / qnorm

    candidates = conn.execute(
        """
        SELECT log_id, exercise_id, answered_timestamp, embedding
        FROM answer_log
        WHERE user_id = ?
          AND exercise_id != ?
          AND embedding IS NOT NULL
          AND is_correct = 0
          AND log_id != ?
        """,
        (target["user_id"], target["exercise_id"], log_id),
    ).fetchall()
    if not candidates:
        return 0, None

    embs = np.stack([_deserialize(r["embedding"]) for r in candidates])
    sims = embs @ query_emb

    above = sims >= threshold
    count = int(above.sum())
    if count == 0:
        return 0, None

    latest = max(
        (candidates[i]["answered_timestamp"] for i in range(len(candidates)) if above[i]),
        default=None,
    )
    return count, latest


def find_top_similar_mistakes(
    conn: sqlite3.Connection,
    log_id: str,
    *,
    top_k: int = 3,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Return the top-K similar past mistakes with enough fields to render.

    Same retrieval rules as the annotation count, just returns the rows
    themselves (with similarity + the exercise prompt joined in) so the
    frontend can let the learner inspect them.
    """
    target = conn.execute(
        "SELECT user_id, exercise_id, embedding FROM answer_log WHERE log_id = ?",
        (log_id,),
    ).fetchone()
    if not target or target["embedding"] is None:
        return []

    query_emb = _deserialize(target["embedding"])
    qnorm = float(np.linalg.norm(query_emb))
    if qnorm == 0.0:
        return []
    query_emb = query_emb / qnorm

    rows = conn.execute(
        """
        SELECT al.log_id, al.user_answer, al.error_type, al.answered_timestamp,
               al.embedding, e.question_sentence, e.correct_answer
        FROM answer_log al
        JOIN exercise e ON al.exercise_id = e.exercise_id
        WHERE al.user_id = ?
          AND al.exercise_id != ?
          AND al.embedding IS NOT NULL
          AND al.is_correct = 0
          AND al.log_id != ?
        """,
        (target["user_id"], target["exercise_id"], log_id),
    ).fetchall()
    if not rows:
        return []

    embs = np.stack([_deserialize(r["embedding"]) for r in rows])
    sims = embs @ query_emb

    order = np.argsort(-sims)
    out: list[dict] = []
    for i in order:
        score = float(sims[i])
        if score < threshold:
            break
        r = rows[i]
        out.append({
            "log_id": r["log_id"],
            "question_sentence": r["question_sentence"],
            "user_answer": r["user_answer"],
            "correct_answer": r["correct_answer"],
            "error_type": r["error_type"],
            "answered_timestamp": r["answered_timestamp"],
            "similarity": round(score, 3),
        })
        if len(out) >= top_k:
            break
    return out


def annotate_feedback(conn: sqlite3.Connection, log_id: str, base_feedback: str) -> str:
    """Append "你已經犯過 N 次類似的錯 — 最近一次 {date}" to the feedback when applicable.

    Traditional Chinese to match the rest of the grader output.
    """
    count, last_seen = find_similar_past_mistakes(conn, log_id)
    if count == 0 or last_seen is None:
        return base_feedback
    note = f"\n\n你已經犯過 {count} 次類似的錯 — 最近一次 {_format_date(last_seen)}。"
    return base_feedback + note
