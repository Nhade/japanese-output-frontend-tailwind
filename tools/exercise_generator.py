import sqlite3
import uuid
import random
import re
from datetime import datetime
from google.cloud import translate_v2 as translate

from config import settings
from services.cloze import make_cloze

def translate_to_traditional_chinese(text: str) -> str:
    """
    Translates a string from Japanese to Traditional Chinese with Google's Cloud Translation API.
    """
    translate_client = translate.Client()
    result = translate_client.translate(text, target_language='zh-TW', source_language='ja')
    return result['translatedText']

def create_database_tables(cursor):
    """
    Ensures the required tables exist in the database.
    """
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            article_id TEXT PRIMARY KEY, source TEXT, url TEXT UNIQUE, title TEXT,
            category TEXT, publish_timestamp TEXT, body_text TEXT, status TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exercise (
            exercise_id TEXT PRIMARY KEY,
            source_article_id TEXT,
            full_sentence TEXT,
            question_sentence TEXT,
            correct_answer TEXT,
            part_of_speech TEXT,
            jlpt_level INTEGER,
            hint_chinese TEXT,
            created_timestamp TEXT,
            FOREIGN KEY (source_article_id) REFERENCES articles (article_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_timestamp TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS answer_log (
            log_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            user_answer TEXT NOT NULL,
            is_correct BOOLEAN NOT NULL,
            answered_timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (exercise_id) REFERENCES exercise (exercise_id)
        )
    ''')

def load_jlpt_vocab_from_db(cursor) -> dict:
    """
    Loads JLPT vocabulary from the database into a dictionary for efficient lookup.
    Returns a dictionary mapping expressions to their JLPT level.
    """
    cursor.execute("SELECT expression, jlpt_level FROM vocabulary WHERE jlpt_level IS NOT NULL")
    vocab_map = {row[0]: row[1] for row in cursor.fetchall()}
    return vocab_map

def create_cloze_exercises_from_article(num_exercises: int, db_name: str | None = None):
    """
    Generates multiple cloze deletion (fill-in-the-blank) exercises from one article.
    The hint provided is the translation of the ENTIRE sentence.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_name or str(settings.database_path))
        cursor = conn.cursor()
        create_database_tables(cursor)

        jlpt_vocab_map = load_jlpt_vocab_from_db(cursor)

        # 1. Select a random, unprocessed article
        cursor.execute("SELECT article_id, body_text FROM articles WHERE status = 'unprocessed' ORDER BY RANDOM() LIMIT 1")
        result = cursor.fetchone()

        if not result:
            print("No unprocessed articles found.")
            return

        source_article_id, body_text = result
        print(f"\nSelected article {source_article_id} to generate {num_exercises} exercises.")

        # 2. Split article into sentences
        sentences = [s.strip() for s in re.split(r'(?<=[。？！])\s*', body_text) if s.strip() and len(s.strip()) > 10]
        random.shuffle(sentences) # Shuffle to get varied sentences

        # 3. Loop through sentences to create exercises
        exercises_created = 0
        for sentence in sentences:
            if exercises_created >= num_exercises:
                break

            cloze = make_cloze(sentence, jlpt_vocab_map)
            if cloze is None:
                continue  # No candidates in this sentence; try the next one.

            hint_chinese = translate_to_traditional_chinese(sentence)

            # Save the exercise to the database
            exercise_id = str(uuid.uuid4())
            created_timestamp = datetime.now().isoformat()

            cursor.execute('''
                INSERT INTO exercise (
                    exercise_id, source_article_id, full_sentence, question_sentence,
                    correct_answer, part_of_speech, jlpt_level, hint_chinese, created_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                exercise_id, source_article_id, cloze.full_sentence, cloze.question_sentence,
                cloze.correct_answer, cloze.part_of_speech, cloze.jlpt_level, hint_chinese, created_timestamp
            ))

            exercises_created += 1
            print(f"  -> Created exercise {exercises_created}/{num_exercises}: Removed '{cloze.correct_answer}' (POS: {cloze.part_of_speech}, JLPT: N{cloze.jlpt_level or '/A'})")

        # Update the article's status
        cursor.execute("UPDATE articles SET status = 'processed' WHERE article_id = ?", (source_article_id,))
        print(f"\nFinished. Created {exercises_created} exercises. Marked article as 'processed'.")
        conn.commit()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# --- Main execution block ---
if __name__ == "__main__":
    # Generate 5 cloze exercises from a single random article
    create_cloze_exercises_from_article(num_exercises=5)
