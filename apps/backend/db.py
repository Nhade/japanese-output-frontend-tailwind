import sqlite3
from pathlib import Path


def connect_db(path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with app-wide baseline settings."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
