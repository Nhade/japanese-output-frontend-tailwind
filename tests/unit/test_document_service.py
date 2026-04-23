"""Unit tests for document parsing, chunking, and ingest."""
import sqlite3
import unittest

from document_service import (
    create_document_tables,
    create_range,
    get_chunks,
    ingest_document,
    list_documents,
    list_ranges,
    parse_markdown,
    parse_txt,
)


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE users (user_id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO users (user_id) VALUES ('u1')")
    conn.execute('''
        CREATE TABLE grammar_patterns (
            pattern_id TEXT PRIMARY KEY,
            doc_id TEXT,
            status TEXT
        )
    ''')  # stub so list_documents' pattern_count subquery works
    create_document_tables(conn)
    return conn


class TestMarkdownParsing(unittest.TestCase):

    def test_splits_on_headings_and_carries_section_path(self):
        md = """# Chapter 3

Intro paragraph about verbs.

## §2 Volitional

Explanation of volitional.

### ～よう

The short form. Used casually.

## §3 Potential

Potential form content."""
        chunks = parse_markdown(md)
        labels = [c.section_label for c in chunks]
        # Every non-empty chunk carries a path label.
        self.assertTrue(all(l is not None for l in labels), labels)
        # Nested heading path is preserved.
        self.assertIn("Chapter 3 > §2 Volitional > ～よう", labels)
        self.assertIn("Chapter 3 > §3 Potential", labels)

    def test_seq_is_zero_based_and_contiguous(self):
        chunks = parse_markdown("# A\n\nalpha\n\n# B\n\nbeta")
        self.assertEqual([c.seq for c in chunks], list(range(len(chunks))))

    def test_token_count_is_populated(self):
        chunks = parse_markdown("# Head\n\n食べてしまった")
        self.assertTrue(all(c.token_count > 0 for c in chunks))


class TestTxtParsing(unittest.TestCase):

    def test_paragraph_chunking(self):
        txt = "Para one text.\n\nPara two text.\n\nPara three text."
        chunks = parse_txt(txt)
        # All paragraphs fit under cap → single chunk.
        self.assertEqual(len(chunks), 1)
        self.assertIn("Para one", chunks[0].text)
        self.assertIn("Para three", chunks[0].text)

    def test_caps_when_oversized(self):
        big = ("あ" * 800 + "\n\n") * 5
        chunks = parse_txt(big)
        self.assertGreater(len(chunks), 1)


class TestIngestAndRanges(unittest.TestCase):

    def test_ingest_persists_document_and_chunks(self):
        conn = _fresh_conn()
        md = "# Intro\n\nHello world.\n\n# Body\n\nMore content."
        result = ingest_document(conn, "u1", "Notes", "grammar_notes", md, "notes.md")
        self.assertEqual(result["chunk_count"], 2)

        docs = list_documents(conn, "u1")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["title"], "Notes")
        self.assertEqual(docs[0]["chunk_count"], 2)

        chunks = get_chunks(conn, result["doc_id"])
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["seq"], 0)

    def test_ingest_rejects_empty(self):
        conn = _fresh_conn()
        with self.assertRaises(ValueError):
            ingest_document(conn, "u1", "Empty", "grammar_notes", "   ", "e.txt")

    def test_create_range_requires_chunks_from_same_doc(self):
        conn = _fresh_conn()
        r1 = ingest_document(conn, "u1", "A", "grammar_notes",
                             "# A\n\naaa", "a.md")
        r2 = ingest_document(conn, "u1", "B", "grammar_notes",
                             "# B\n\nbbb", "b.md")
        chunks_a = get_chunks(conn, r1["doc_id"])
        chunks_b = get_chunks(conn, r2["doc_id"])

        # Legal range: all chunks belong to doc A.
        created = create_range(conn, "u1", r1["doc_id"], "Ch 1",
                               [chunks_a[0]["chunk_id"]])
        self.assertEqual(created["chunk_count"], 1)

        # Illegal: mixing chunks from two docs.
        with self.assertRaises(ValueError):
            create_range(conn, "u1", r1["doc_id"], "Mixed",
                         [chunks_a[0]["chunk_id"], chunks_b[0]["chunk_id"]])

        ranges = list_ranges(conn, "u1", r1["doc_id"])
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0]["label"], "Ch 1")


if __name__ == "__main__":
    unittest.main()
