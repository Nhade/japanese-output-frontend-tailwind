import sqlite3
from janome.tokenizer import Tokenizer

def load_jlpt_vocab_from_db(cursor) -> dict:
    """
    Loads JLPT vocabulary from the database into a dictionary for efficient lookup.
    """
    cursor.execute("SELECT expression, jlpt_level FROM vocabulary WHERE jlpt_level IS NOT NULL")
    return {row[0]: row[1] for row in cursor.fetchall()}

def find_target_token_index(tokenizer, question_sentence):
    """
    Finds the index of the token that was replaced by the blank.
    """
    # Find the text before the blank
    pre_blank_text = question_sentence.split('[＿＿＿]', 1)[0]
    
    # Count the number of tokens in the text before the blank
    pre_blank_tokens = list(tokenizer.tokenize(pre_blank_text))
    
    return len(pre_blank_tokens)

def backfill_exercises(db_name: str = 'news_corpus.db'):
    """
    Backfills missing part_of_speech and jlpt_level for old exercises.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        t = Tokenizer()
        jlpt_vocab_map = load_jlpt_vocab_from_db(cursor)

        # Select exercises that need backfilling
        cursor.execute("SELECT exercise_id, full_sentence, question_sentence, correct_answer FROM exercise WHERE part_of_speech IS NULL OR jlpt_level IS NULL")
        exercises_to_update = cursor.fetchall()

        if not exercises_to_update:
            print("No exercises to backfill.")
            return

        print(f"Found {len(exercises_to_update)} exercises to backfill...")
        updated_count = 0

        for exercise in exercises_to_update:
            exercise_id, full_sentence, question_sentence, correct_answer = exercise
            
            try:
                full_tokens = list(t.tokenize(full_sentence))
                target_index = find_target_token_index(t, question_sentence)
                
                if target_index < len(full_tokens) and full_tokens[target_index].surface == correct_answer:
                    target_token = full_tokens[target_index]
                    
                    part_of_speech = target_token.part_of_speech.split(',')[0]
                    
                    jlpt_level = jlpt_vocab_map.get(target_token.surface)
                    if jlpt_level is None:
                        jlpt_level = jlpt_vocab_map.get(target_token.base_form)
                    
                    cursor.execute(
                        "UPDATE exercise SET part_of_speech = ?, jlpt_level = ? WHERE exercise_id = ?",
                        (part_of_speech, jlpt_level, exercise_id)
                    )
                    updated_count += 1
                else:
                    print(f"  - Could not reliably identify token for exercise {exercise_id}. Answer: '{correct_answer}'. Skipping.")

            except Exception as e:
                print(f"  - Error processing exercise {exercise_id}: {e}. Skipping.")

        conn.commit()
        print(f"\nBackfill complete. Successfully updated {updated_count} exercises.")

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

if __name__ == '__main__':
    backfill_exercises()
