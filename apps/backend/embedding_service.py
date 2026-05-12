"""
Mistake-history embeddings.

The unit of retrieval is a "mistake card" — the prompt, reference, the user's
wrong answer, the error type, and the feedback rendered into one text blob.
We embed each wrong answer_log row into a normalized float32 vector and store
it alongside the row so retrieval is a single SQL fetch + dot product.

Public surface:
  - ensure_embedding_columns(conn)            — idempotent schema migration
  - format_mistake_card(...)                  — canonical card text
  - embed_text(text) -> np.ndarray            — single-text embedding
  - embed_mistake_card(...) -> np.ndarray     — convenience: format + embed
  - serialize(arr) / deserialize(buf)         — BLOB conversion
  - cosine_search(conn, user_id, query_emb, ...) -> list[dict]

The embedding model is loaded lazily on first call so module import remains
cheap (the SentenceTransformer download is ~400 MB).
"""
from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np

# E5 family expects a "query:" / "passage:" prefix. Mistake cards are stored
# documents, so they get the passage prefix at write time; lookup queries get
# the query prefix at read time.
_MODEL_NAME = "intfloat/multilingual-e5-base"
_PASSAGE_PREFIX = "passage: "
_QUERY_PREFIX = "query: "
_EMBED_DIM = 768

_model = None  # lazy


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def ensure_embedding_columns(conn: sqlite3.Connection) -> None:
    """Add `embedding` (BLOB) and `embedding_model` (TEXT) to answer_log if absent.

    Idempotent — safe to call at every startup.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(answer_log)")
    existing = {row[1] for row in cursor.fetchall()}

    if "embedding" not in existing:
        cursor.execute("ALTER TABLE answer_log ADD COLUMN embedding BLOB")
    if "embedding_model" not in existing:
        cursor.execute("ALTER TABLE answer_log ADD COLUMN embedding_model TEXT")
    conn.commit()


# ---------------------------------------------------------------------------
# Card formatting
# ---------------------------------------------------------------------------

def format_mistake_card(
    *,
    prompt: str,
    reference: str,
    user_answer: str,
    error_type: str | None = None,
    feedback: str | None = None,
    section_label: str | None = None,
) -> str:
    """Render a wrong-answer row into the canonical text blob we embed.

    Keeping every field on its own line keeps similarity computations stable
    when one field is empty (e.g. feedback may be missing on freshly-graded
    rows before AI evaluation completes).
    """
    lines = []
    if section_label:
        lines.append(f"[{section_label}]")
    lines.append(f"Prompt: {prompt}")
    lines.append(f"Reference: {reference}")
    lines.append(f"User: {user_answer}")
    if error_type:
        lines.append(f"Error: {error_type}")
    if feedback:
        lines.append(f"Feedback: {feedback}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_text(text: str, *, kind: str = "passage") -> np.ndarray:
    """Embed a single string. Returns L2-normalized float32 vector.

    `kind` is "passage" (stored documents) or "query" (search inputs); E5
    treats these asymmetrically.
    """
    prefix = _PASSAGE_PREFIX if kind == "passage" else _QUERY_PREFIX
    model = _get_model()
    vec = model.encode(prefix + text, normalize_embeddings=True)
    return np.asarray(vec, dtype=np.float32)


def embed_texts(texts: list[str], *, kind: str = "passage", batch_size: int = 32) -> np.ndarray:
    """Batch variant. Returns (N, D) float32 array of normalized vectors."""
    if not texts:
        return np.zeros((0, _EMBED_DIM), dtype=np.float32)
    prefix = _PASSAGE_PREFIX if kind == "passage" else _QUERY_PREFIX
    model = _get_model()
    arr = model.encode(
        [prefix + t for t in texts],
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(arr, dtype=np.float32)


def embed_mistake_card(
    *,
    prompt: str,
    reference: str,
    user_answer: str,
    error_type: str | None = None,
    feedback: str | None = None,
    section_label: str | None = None,
) -> np.ndarray:
    card = format_mistake_card(
        prompt=prompt,
        reference=reference,
        user_answer=user_answer,
        error_type=error_type,
        feedback=feedback,
        section_label=section_label,
    )
    return embed_text(card, kind="passage")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize(arr: np.ndarray) -> bytes:
    """Pack a float32 numpy vector into bytes for SQLite BLOB storage."""
    return np.ascontiguousarray(arr, dtype=np.float32).tobytes()


def deserialize(buf: bytes) -> np.ndarray:
    return np.frombuffer(buf, dtype=np.float32)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def cosine_search(
    conn: sqlite3.Connection,
    user_id: str,
    query_embedding: np.ndarray,
    *,
    top_k: int = 3,
    min_score: float = 0.0,
    only_wrong: bool = True,
) -> list[dict[str, Any]]:
    """Brute-force nearest-mistake search for one user.

    Stored embeddings are pre-normalized at write time, so the query just
    needs to be normalized once and cosine collapses to a dot product.
    Linear in the number of mistakes the user has — fine up to ~10k rows;
    swap in a vector index when that ceiling is in sight.
    """
    sql = """
        SELECT al.log_id, al.user_answer, al.feedback, al.score, al.error_type,
               al.answered_timestamp, al.embedding,
               e.question_sentence AS prompt, e.correct_answer AS reference,
               e.part_of_speech, e.jlpt_level
        FROM answer_log al
        JOIN exercise e ON al.exercise_id = e.exercise_id
        WHERE al.user_id = ? AND al.embedding IS NOT NULL
    """
    if only_wrong:
        sql += " AND al.is_correct = 0"
    rows = conn.execute(sql, (user_id,)).fetchall()
    if not rows:
        return []

    embeddings = np.stack([deserialize(r["embedding"]) for r in rows])
    q = np.asarray(query_embedding, dtype=np.float32)
    qnorm = float(np.linalg.norm(q))
    if qnorm == 0.0:
        return []
    q = q / qnorm

    sims = embeddings @ q  # (N,)
    order = np.argsort(-sims)[:top_k]

    results = []
    for i in order:
        score = float(sims[i])
        if score < min_score:
            break
        row = dict(rows[i])
        row.pop("embedding", None)
        row["similarity"] = score
        results.append(row)
    return results


def search_by_text(
    conn: sqlite3.Connection,
    user_id: str,
    query_text: str,
    *,
    top_k: int = 3,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Convenience: embed `query_text` as a query then run cosine_search."""
    q = embed_text(query_text, kind="query")
    return cosine_search(conn, user_id, q, top_k=top_k, min_score=min_score)
