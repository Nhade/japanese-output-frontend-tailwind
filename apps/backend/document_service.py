"""
Document service — uploads, parses, and chunks learner documents
(grammar notes, textbook sections).

Public API:
  - create_document_tables(conn)
  - parse_document(content, source_type, filename) -> List[Chunk]
  - ingest_document(conn, user_id, title, source_type, content, filename)
  - list_documents(conn, user_id) / get_document(conn, doc_id)
  - get_chunks(conn, doc_id)
  - create_range(conn, user_id, doc_id, label, chunk_ids)
  - list_ranges(conn, user_id, doc_id)

Design notes:
  - Markdown is split on headings; the section_label carries the full heading
    path ("Ch 3 > §2 Volitional") so planner + verifier can surface it.
  - TXT has no headings, so it chunks on blank-line paragraphs capped by
    character length.
  - token_count is computed with janome post-chunk (same tokenizer used
    elsewhere in this codebase) so downstream strategies can budget.
"""
import hashlib
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from janome.tokenizer import Tokenizer
from markdown_it import MarkdownIt

# Flush a chunk once its accumulated text passes this many characters.
# Japanese text averages ~2 chars per token, so ~400 tokens.
_CHUNK_CHAR_CAP = 1200

# Headings at or above this level start a new chunk and update the
# section label. Deeper headings (e.g. ### 接續, ### 例文) are folded
# into the parent chunk as inline emphasis so the structural unit
# matches the pedagogical unit (one grammar pattern per chunk).
_DEFAULT_MAX_SPLIT_LEVEL = 2

_tokenizer: Optional[Tokenizer] = None


def _get_tokenizer() -> Tokenizer:
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return _tokenizer


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def create_document_tables(conn: sqlite3.Connection):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            title TEXT NOT NULL,
            source_type TEXT NOT NULL,
            original_filename TEXT,
            content_hash TEXT,
            status TEXT NOT NULL DEFAULT 'uploaded',
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS doc_chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL REFERENCES documents(doc_id),
            seq INTEGER NOT NULL,
            section_label TEXT,
            heading_level INTEGER,
            text TEXT NOT NULL,
            token_count INTEGER,
            UNIQUE(doc_id, seq)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS practice_ranges (
            range_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            doc_id TEXT NOT NULL REFERENCES documents(doc_id),
            label TEXT NOT NULL,
            chunk_ids_json TEXT NOT NULL,
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    seq: int
    text: str
    section_label: Optional[str] = None
    heading_level: Optional[int] = None
    token_count: int = 0


def _count_tokens(text: str) -> int:
    return sum(1 for _ in _get_tokenizer().tokenize(text))


def _flush(buf: List[str], seq: int, section_label: Optional[str],
           heading_level: Optional[int], out: List[Chunk]) -> int:
    text = "".join(buf).strip()
    if not text:
        return seq
    out.append(Chunk(
        seq=seq,
        text=text,
        section_label=section_label,
        heading_level=heading_level,
        token_count=_count_tokens(text),
    ))
    buf.clear()
    return seq + 1


def parse_markdown(content: str,
                   max_split_level: int = _DEFAULT_MAX_SPLIT_LEVEL
                   ) -> List[Chunk]:
    """Split Markdown into chunks by heading.

    Headings at or above `max_split_level` start a new chunk and extend
    the section label. Deeper headings are kept inline as bold markers
    so a pattern's subsections (接續 / 説明 / 例文) stay grouped with
    the pattern itself — extraction otherwise produces duplicate
    pattern entries, one per subsection chunk.
    """
    md = MarkdownIt()
    tokens = md.parse(content)

    chunks: List[Chunk] = []
    heading_stack: List[tuple[int, str]] = []  # (level, text) — split-level only
    current_label: Optional[str] = None
    current_level: Optional[int] = None
    buf: List[str] = []
    seq = 0

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok.type == "heading_open":
            level = int(tok.tag[1:])  # 'h2' -> 2
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            heading_text = (inline.content if inline else "").strip()

            if level <= max_split_level:
                # Splitting heading: flush prior content, update label.
                seq = _flush(buf, seq, current_label, current_level, chunks)
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading_text))
                current_label = " > ".join(t for _, t in heading_stack)
                current_level = level
            else:
                # Sub-heading: include in body so the LLM still sees the
                # subsection marker, but don't split or change the label.
                buf.append(f"**{heading_text}**\n\n")

            # Skip heading_open + inline + heading_close.
            i += 3
            continue

        if tok.type == "inline" and tok.content:
            buf.append(tok.content + "\n\n")
            if sum(len(s) for s in buf) >= _CHUNK_CHAR_CAP:
                seq = _flush(buf, seq, current_label, current_level, chunks)
        elif tok.type == "fence":
            buf.append(tok.content + "\n\n")
            if sum(len(s) for s in buf) >= _CHUNK_CHAR_CAP:
                seq = _flush(buf, seq, current_label, current_level, chunks)

        i += 1

    _flush(buf, seq, current_label, current_level, chunks)
    return chunks


def parse_txt(content: str) -> List[Chunk]:
    """Split plain text into paragraph-grouped chunks."""
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks: List[Chunk] = []
    buf: List[str] = []
    seq = 0

    for para in paragraphs:
        buf.append(para + "\n\n")
        if sum(len(s) for s in buf) >= _CHUNK_CHAR_CAP:
            seq = _flush(buf, seq, None, None, chunks)

    _flush(buf, seq, None, None, chunks)
    return chunks


def parse_document(content: str, source_type: str,
                   filename: Optional[str] = None) -> List[Chunk]:
    """Dispatch to the right parser based on filename extension or source_type."""
    ext = (filename or "").rsplit(".", 1)[-1].lower() if filename else ""
    if ext in ("md", "markdown") or source_type == "grammar_notes_md":
        return parse_markdown(content)
    return parse_txt(content)


# ---------------------------------------------------------------------------
# Ingest + queries
# ---------------------------------------------------------------------------

def ingest_document(conn: sqlite3.Connection, user_id: str, title: str,
                    source_type: str, content: str,
                    original_filename: Optional[str] = None) -> dict:
    """Parse + store a document with its chunks. Returns {doc_id, chunk_count}."""
    doc_id = str(uuid.uuid4())
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    now = datetime.now().isoformat()

    chunks = parse_document(content, source_type, original_filename)
    if not chunks:
        raise ValueError("Document produced no chunks (empty or unparseable).")

    conn.execute('''
        INSERT INTO documents
        (doc_id, user_id, title, source_type, original_filename,
         content_hash, status, created_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (doc_id, user_id, title, source_type, original_filename,
          content_hash, 'chunked', now))

    for chunk in chunks:
        conn.execute('''
            INSERT INTO doc_chunks
            (chunk_id, doc_id, seq, section_label, heading_level,
             text, token_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (str(uuid.uuid4()), doc_id, chunk.seq, chunk.section_label,
              chunk.heading_level, chunk.text, chunk.token_count))

    conn.commit()
    return {"doc_id": doc_id, "chunk_count": len(chunks)}


def list_documents(conn: sqlite3.Connection, user_id: str) -> List[dict]:
    rows = conn.execute('''
        SELECT d.doc_id, d.title, d.source_type, d.status, d.created_timestamp,
               (SELECT COUNT(*) FROM doc_chunks c WHERE c.doc_id = d.doc_id)
                   AS chunk_count,
               (SELECT COUNT(*) FROM grammar_patterns p
                   WHERE p.doc_id = d.doc_id AND p.status = 'published')
                   AS pattern_count
        FROM documents d
        WHERE d.user_id = ?
        ORDER BY d.created_timestamp DESC
    ''', (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_document(conn: sqlite3.Connection, doc_id: str) -> Optional[dict]:
    row = conn.execute(
        'SELECT * FROM documents WHERE doc_id = ?', (doc_id,)
    ).fetchone()
    return dict(row) if row else None


def get_chunks(conn: sqlite3.Connection, doc_id: str) -> List[dict]:
    rows = conn.execute('''
        SELECT chunk_id, seq, section_label, heading_level, text, token_count
        FROM doc_chunks
        WHERE doc_id = ?
        ORDER BY seq
    ''', (doc_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Practice ranges
# ---------------------------------------------------------------------------

def create_range(conn: sqlite3.Connection, user_id: str, doc_id: str,
                 label: str, chunk_ids: List[str]) -> dict:
    import json
    if not chunk_ids:
        raise ValueError("chunk_ids must be non-empty")
    # Validate chunks belong to the doc.
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f'SELECT chunk_id FROM doc_chunks WHERE doc_id = ? '
        f'AND chunk_id IN ({placeholders})',
        (doc_id, *chunk_ids)
    ).fetchall()
    if len(rows) != len(chunk_ids):
        raise ValueError("One or more chunk_ids do not belong to this document")

    range_id = str(uuid.uuid4())
    conn.execute('''
        INSERT INTO practice_ranges
        (range_id, user_id, doc_id, label, chunk_ids_json, created_timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (range_id, user_id, doc_id, label, json.dumps(chunk_ids),
          datetime.now().isoformat()))
    conn.commit()
    return {"range_id": range_id, "label": label, "chunk_count": len(chunk_ids)}


def list_ranges(conn: sqlite3.Connection, user_id: str,
                doc_id: Optional[str] = None) -> List[dict]:
    import json
    if doc_id:
        rows = conn.execute('''
            SELECT range_id, doc_id, label, chunk_ids_json, created_timestamp
            FROM practice_ranges
            WHERE user_id = ? AND doc_id = ?
            ORDER BY created_timestamp DESC
        ''', (user_id, doc_id)).fetchall()
    else:
        rows = conn.execute('''
            SELECT range_id, doc_id, label, chunk_ids_json, created_timestamp
            FROM practice_ranges
            WHERE user_id = ?
            ORDER BY created_timestamp DESC
        ''', (user_id,)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        chunk_ids = json.loads(d.pop("chunk_ids_json"))
        d["chunk_ids"] = chunk_ids
        d["chunk_count"] = len(chunk_ids)
        result.append(d)
    return result
