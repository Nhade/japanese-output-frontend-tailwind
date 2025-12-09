import sqlite3
import os

# Robust path handling
# Assumes structure:
# root/
#   data/news_corpus.db
#   scripts/migrate_db.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level to root, then into data
DB_PATH = os.path.join(SCRIPT_DIR, '..', 'data', 'news_corpus.db')

def migrate_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get current columns in answer_log
    cursor.execute("PRAGMA table_info(answer_log)")
    columns = [info[1] for info in cursor.fetchall()]
    print(f"Current columns: {columns}")

    # Add new columns if they don't exist
    new_columns = {
        'feedback': 'TEXT',
        'score': 'INTEGER DEFAULT 0',
        'error_type': 'TEXT'
    }

    for col, data_type in new_columns.items():
        if col not in columns:
            print(f"Adding column: {col}")
            try:
                cursor.execute(f"ALTER TABLE answer_log ADD COLUMN {col} {data_type}")
            except sqlite3.Error as e:
                print(f"Error adding {col}: {e}")
        else:
            print(f"Column {col} already exists.")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate_db()
