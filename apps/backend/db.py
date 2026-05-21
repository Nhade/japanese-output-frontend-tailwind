import sqlite3


def connect_db(path: str) -> sqlite3.Connection:
    """Open a SQLite connection with app-wide baseline settings."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
