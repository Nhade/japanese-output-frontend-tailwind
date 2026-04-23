"""
Grammar-pattern extraction service.

Per-chunk LLM pass that turns free-text grammar notes into typed
`grammar_patterns` + `pattern_examples` rows. Validated with Pydantic;
entries above the confidence threshold auto-publish, below go to
`pending_review`.

Runs asynchronously from the upload request via a daemon thread so the
client gets an immediate `job_id` to poll.

Public API:
  - enqueue_extraction(conn, doc_id, user_id, locale) -> job_id
  - start_extraction_background(db_path, job_id)
  - run_extraction(db_path, job_id, llm_fn=None)   # test-friendly entry
  - get_job(conn, job_id)
  - list_jobs_for_doc(conn, doc_id)
"""
import json
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Callable, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai_core import query_llm_json

CONFIDENCE_AUTO_PUBLISH = 0.8

LOCALE_LABELS = {
    "en": "English",
    "zh-tw": "Traditional Chinese",
    "zh-TW": "Traditional Chinese",
    "ja": "Japanese",
}


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class ExtractedExample(BaseModel):
    sentence: str = Field(..., min_length=1)
    translation: str = ""
    is_canonical: bool = False


class ExtractedPattern(BaseModel):
    # `register` as a field name shadows BaseModel.register; alias keeps
    # the JSON contract unchanged while avoiding the shadow warning.
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1)
    reading: Optional[str] = None
    meaning_locale: str = ""
    formation_rule: Optional[str] = None
    jlpt: Optional[int] = Field(None, ge=1, le=5)
    register_label: Optional[str] = Field(None, alias="register")
    examples: List[ExtractedExample] = Field(default_factory=list)
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class ExtractionResponse(BaseModel):
    patterns: List[ExtractedPattern] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a Japanese grammar-note structurer.

Given a chunk of grammar-note text, extract the discrete grammar patterns
that the chunk explicitly teaches. Ignore prose, cultural asides, vocabulary
lists, and conjugation drills unless they are the main subject.

For each pattern return:
  - name: the pattern form with tildes for verb/adj slots (e.g. "〜てしまう", "〜ば")
  - reading: romaji if obvious, else null
  - meaning_locale: meaning explained in the target_language below
  - formation_rule: plain description (e.g. "て-form + しまう")
  - jlpt: 1..5 if the chunk states or clearly implies a level, else null
  - register: one of "plain", "polite", "casual", "formal", or null
  - examples: list of {sentence, translation, is_canonical}. Translations
    must also be in target_language. Mark the most representative example
    as is_canonical=true.
  - confidence: 0.0..1.0 — how certain this is a real pattern entry in the
    chunk (not prose or a side note).

Return strict JSON:
{"patterns": [ ... ]}

If the chunk teaches no pattern, return {"patterns": []}.

Do not invent patterns that are not in the chunk. Do not merge patterns."""


def _build_messages(chunk_text: str, locale: str) -> list[dict]:
    locale_label = LOCALE_LABELS.get(locale, "English")
    user_msg = f"target_language: {locale_label}\n\n---CHUNK---\n{chunk_text}"
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


# ---------------------------------------------------------------------------
# Core extraction (pure; llm_fn injected for tests)
# ---------------------------------------------------------------------------

LLMFn = Callable[[list[dict]], dict]


def _default_llm(messages: list[dict]) -> dict:
    """Adapter over ai_core.query_llm_json at temperature 0."""
    result = query_llm_json(messages, retries=2, temperature=0.0)
    if result.get("data") is None:
        raise RuntimeError(result.get("error") or "LLM returned no JSON")
    return result["data"]


def extract_from_chunk(chunk_text: str, locale: str,
                       llm_fn: Optional[LLMFn] = None) -> ExtractionResponse:
    """Call the LLM once for a chunk and parse into the typed schema.

    llm_fn is injected for testing; default uses ai_core.query_llm_json.
    Raises ValidationError if the parsed JSON doesn't fit the schema.
    """
    fn = llm_fn or _default_llm
    raw = fn(_build_messages(chunk_text, locale))
    return ExtractionResponse.model_validate(raw)


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------

def enqueue_extraction(conn: sqlite3.Connection, doc_id: str, user_id: str,
                       locale: str) -> str:
    """Create a queued extraction_jobs row and return its job_id."""
    total = conn.execute(
        'SELECT COUNT(*) FROM doc_chunks WHERE doc_id = ?', (doc_id,)
    ).fetchone()[0]
    job_id = str(uuid.uuid4())
    conn.execute('''
        INSERT INTO extraction_jobs
        (job_id, doc_id, user_id, locale, status, total_chunks,
         created_timestamp)
        VALUES (?, ?, ?, ?, 'queued', ?, ?)
    ''', (job_id, doc_id, user_id, locale, total, datetime.now().isoformat()))
    conn.commit()
    return job_id


def get_job(conn: sqlite3.Connection, job_id: str) -> Optional[dict]:
    row = conn.execute(
        'SELECT * FROM extraction_jobs WHERE job_id = ?', (job_id,)
    ).fetchone()
    return dict(row) if row else None


def list_jobs_for_doc(conn: sqlite3.Connection, doc_id: str) -> List[dict]:
    rows = conn.execute(
        'SELECT * FROM extraction_jobs WHERE doc_id = ? '
        'ORDER BY created_timestamp DESC', (doc_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _fail_job(conn: sqlite3.Connection, job_id: str, error: str):
    conn.execute('''
        UPDATE extraction_jobs
        SET status = 'failed', error = ?, completed_at = ?
        WHERE job_id = ?
    ''', (error[:500], datetime.now().isoformat(), job_id))
    conn.commit()


def _persist_patterns(conn: sqlite3.Connection, doc_id: str, chunk_id: str,
                      response: ExtractionResponse) -> tuple[int, int, int]:
    """Write extracted patterns + examples. Returns (extracted, published, pending)."""
    now = datetime.now().isoformat()
    extracted = published = pending = 0

    for p in response.patterns:
        pattern_id = str(uuid.uuid4())
        status = ('published' if p.confidence >= CONFIDENCE_AUTO_PUBLISH
                  else 'pending_review')
        conn.execute('''
            INSERT INTO grammar_patterns
            (pattern_id, doc_id, source_chunk_id, name, reading, meaning_en,
             meaning_locale, formation_rule, jlpt, register, confidence,
             status, detector_spec, created_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pattern_id, doc_id, chunk_id, p.name, p.reading,
              None,  # meaning_en populated later if needed
              p.meaning_locale, p.formation_rule, p.jlpt, p.register_label,
              p.confidence, status, None, now))

        for ex in p.examples:
            conn.execute('''
                INSERT INTO pattern_examples
                (example_id, pattern_id, sentence, translation,
                 is_canonical, cloze_mask_hint, created_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), pattern_id, ex.sentence, ex.translation,
                  1 if ex.is_canonical else 0, None, now))

        extracted += 1
        if status == 'published':
            published += 1
        else:
            pending += 1

    return extracted, published, pending


def run_extraction(db_path: str, job_id: str,
                   llm_fn: Optional[LLMFn] = None) -> dict:
    """Execute an extraction job end-to-end.

    Opens its own DB connection (it's expected to run in a background
    thread). Updates the job row as it progresses. Returns the final job
    dict; per-chunk failures are tolerated (logged as partial error),
    but a job-level failure marks the job 'failed'.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        job = get_job(conn, job_id)
        if not job:
            raise RuntimeError(f"job {job_id} not found")

        conn.execute('''
            UPDATE extraction_jobs
            SET status = 'running', started_at = ?
            WHERE job_id = ?
        ''', (datetime.now().isoformat(), job_id))
        conn.commit()

        chunks = conn.execute('''
            SELECT chunk_id, text FROM doc_chunks
            WHERE doc_id = ? ORDER BY seq
        ''', (job['doc_id'],)).fetchall()

        totals = {"extracted": 0, "published": 0, "pending": 0}
        partial_errors: list[str] = []

        for i, chunk in enumerate(chunks):
            try:
                response = extract_from_chunk(chunk['text'], job['locale'],
                                              llm_fn=llm_fn)
                e, p, n = _persist_patterns(conn, job['doc_id'],
                                            chunk['chunk_id'], response)
                totals["extracted"] += e
                totals["published"] += p
                totals["pending"] += n
            except (ValidationError, RuntimeError, ValueError) as err:
                partial_errors.append(f"chunk {i}: {err}")

            conn.execute('''
                UPDATE extraction_jobs
                SET processed_chunks = ?,
                    patterns_extracted = ?,
                    patterns_published = ?,
                    patterns_pending = ?
                WHERE job_id = ?
            ''', (i + 1, totals["extracted"], totals["published"],
                  totals["pending"], job_id))
            conn.commit()

        # Mark document ready for practice.
        conn.execute(
            "UPDATE documents SET status = 'ready' WHERE doc_id = ?",
            (job['doc_id'],)
        )
        error_blob = "; ".join(partial_errors)[:500] if partial_errors else None
        conn.execute('''
            UPDATE extraction_jobs
            SET status = 'complete', error = ?, completed_at = ?
            WHERE job_id = ?
        ''', (error_blob, datetime.now().isoformat(), job_id))
        conn.commit()
        return get_job(conn, job_id)

    except Exception as e:
        _fail_job(conn, job_id, str(e))
        raise
    finally:
        conn.close()


def start_extraction_background(db_path: str, job_id: str) -> None:
    """Spawn a daemon thread to run the extraction job."""
    thread = threading.Thread(
        target=_background_runner, args=(db_path, job_id), daemon=True,
        name=f"extraction-{job_id[:8]}",
    )
    thread.start()


def _background_runner(db_path: str, job_id: str):
    try:
        run_extraction(db_path, job_id)
    except Exception as e:  # noqa: BLE001 — the thread boundary needs to swallow
        print(f"Extraction job {job_id} failed: {e}")
