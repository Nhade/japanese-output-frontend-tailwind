import os
import sqlite3
import uuid
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from pwdlib import PasswordHash, exceptions
from pykakasi import kakasi
from translation_service import translate_text
from tts_service import generate_audio
from flask import Response

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

k = kakasi()
password_hash = PasswordHash.recommended()

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'news_corpus.db')

def get_db_connection():
    """
    Establish a connection to the SQLite database.
    
    Returns:
        sqlite3.Connection: Connection object with row_factory set to sqlite3.Row.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/exercise/random', methods=['GET'])
def get_random_exercise():
    """
    Fetch a random exercise from the database.

    Returns:
        JSON: A dictionary containing the exercise details (id, question, hint).
    """
    conn = get_db_connection()
    exercise = conn.execute('SELECT exercise_id, question_sentence, hint_chinese FROM exercise ORDER BY RANDOM() LIMIT 1').fetchone()
    conn.close()
    if exercise is None:
        return jsonify({"error": "No exercises found"}), 404
    
    return jsonify(dict(exercise))

@app.route('/api/mistakes/<user_id>', methods=['GET'])
def get_mistakes(user_id):
    """
    Retrieve the list of mistakes (incorrect answers) for a specific user.

    Args:
        user_id (str): The ID of the user.

    Returns:
        JSON: A list of mistake objects (question, user_answer, correct_answer, feedback, etc.).
    """
    conn = get_db_connection()
    mistakes = conn.execute('''
        SELECT al.log_id, e.question_sentence, al.user_answer, e.correct_answer,
               al.feedback, al.score, al.error_type
        FROM answer_log al
        JOIN exercise e ON al.exercise_id = e.exercise_id
        WHERE al.user_id = ? AND al.is_correct = 0
        ORDER BY al.answered_timestamp DESC
    ''', (user_id,)).fetchall()
    conn.close()

    return jsonify([dict(mistake) for mistake in mistakes])

from ai_service import evaluate_submission, get_detailed_feedback, chat_with_ai
from agent_service import generate_daily_review_agent
from learner_service import create_learner_tables, update_learner_profile, get_learner_profile, backfill_learner_profile, update_learner_settings

# Initialize Learner Tables
try:
    with sqlite3.connect(DATABASE_PATH) as conn:
        create_learner_tables(conn)
except Exception as e:
    print(f"Database init error: {e}")


@app.route('/api/exercise/submit', methods=['POST'])
def submit_answer():
    """
    Submit an answer for an exercise.
    Evaluates the answer locally first (using Kakasi for simple matching).
    Updates the answer log and learner profile.

    Returns:
        JSON: result containing is_correct, correct_answer, log_id, key focus updates.
    """
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    user_answer = data.get('user_answer', '').strip()
    user_id = data.get('user_id')

    if not exercise_id or not user_id:
        return jsonify({"error": "exercise_id and user_id are required"}), 400

    conn = get_db_connection()
    try:
        # Fetch question_sentence as well
        row = conn.execute('SELECT question_sentence, correct_answer, part_of_speech, jlpt_level FROM exercise WHERE exercise_id = ?', (exercise_id,)).fetchone()


        if row is None:
            return jsonify({"error": "Exercise not found"}), 404

        correct_answer = row['correct_answer']
        question_sentence = row['question_sentence']
        
        # 1. First Layer: Simple String Matching (Kakasi)
        user_answer_hira = "".join([item['hira'] for item in k.convert(user_answer)])
        correct_answer_hira = "".join([item['hira'] for item in k.convert(correct_answer)])
        
        # Default values
        score = 100
        feedback = "完全正確！"
        error_type = "none"
        is_correct = False

        if user_answer_hira == correct_answer_hira:
            is_correct = True
        
        # Log to database with new fields (Initial)
        log_id = str(uuid.uuid4())
        answered_timestamp = datetime.now().isoformat()
        
        # Default empty values for AI fields
        feedback = None
        score = 100 if is_correct else 0
        error_type = "none" if is_correct else None

        conn.execute('''
            INSERT INTO answer_log 
            (log_id, user_id, exercise_id, user_answer, is_correct, answered_timestamp, feedback, score, error_type) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (log_id, user_id, exercise_id, user_answer, is_correct, answered_timestamp, feedback, score, error_type))
        
        # Update Learner Profile
        exercise_info = {
            "part_of_speech": row['part_of_speech'],
            "jlpt_level": row['jlpt_level']
        }
        _, focus_diff = update_learner_profile(conn, user_id, exercise_info, is_correct)
        
        conn.commit()

        
    finally:
        conn.close()
        
    return jsonify({
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "log_id": log_id,
        "focus_diff": focus_diff
    })

@app.route('/api/exercise/explain', methods=['POST'])
def explain_answer():
    """
    Request AI evaluation for a specific submission log.
    Updates the log with AI-generated feedback, score, and error type.

    Returns:
        JSON: The AI evaluation result (feedback, score, error_type).
    """
    data = request.get_json()
    log_id = data.get('log_id')
    
    if not log_id:
        return jsonify({"error": "log_id is required"}), 400
        
    conn = get_db_connection()
    try:
        # Fetch details to ensure data integrity
        row = conn.execute('''
            SELECT al.user_answer, e.question_sentence, e.correct_answer 
            FROM answer_log al
            JOIN exercise e ON al.exercise_id = e.exercise_id
            WHERE al.log_id = ?
        ''', (log_id,)).fetchone()
        
        if not row:
            return jsonify({"error": "Log entry not found"}), 404
            
        question = row['question_sentence']
        user_answer = row['user_answer']
        correct_answer = row['correct_answer']
        
        print(f"Calling AI for evaluation (Log ID: {log_id})...")
        ai_result = evaluate_submission(question, user_answer, correct_answer)
        
        # Update record
        conn.execute('''
            UPDATE answer_log 
            SET feedback = ?, score = ?, error_type = ?
            WHERE log_id = ?
        ''', (ai_result['feedback'], ai_result['score'], ai_result['error_type'], log_id))
        conn.commit()
        
        return jsonify(ai_result)
        
    finally:
        conn.close()

@app.route('/api/exercise/explain-detailed', methods=['POST'])
def explain_answer_detailed():
    """
    Request detailed grammatical explanation for a submission.
    Does not update the database, just returns the explanation.

    Returns:
        JSON: {"detailed_feedback": str}
    """
    data = request.get_json()
    log_id = data.get('log_id')
    
    if not log_id:
        return jsonify({"error": "log_id is required"}), 400
        
    conn = get_db_connection()
    try:
        row = conn.execute('''
            SELECT al.user_answer, e.question_sentence, e.correct_answer 
            FROM answer_log al
            JOIN exercise e ON al.exercise_id = e.exercise_id
            WHERE al.log_id = ?
        ''', (log_id,)).fetchone()
        
        if not row:
            return jsonify({"error": "Log entry not found"}), 404
            
        question = row['question_sentence']
        user_answer = row['user_answer']
        correct_answer = row['correct_answer']
        
        detailed_feedback = get_detailed_feedback(question, user_answer, correct_answer)
        
        return jsonify({"detailed_feedback": detailed_feedback})
        
    finally:
        conn.close()

@app.route('/api/chat/send', methods=['POST'])
def chat_send():
    """
    Send a message to the AI chat interface.
    The AI considers the user's learner profile (level, weak points) when responding.

    Returns:
        JSON: The AI's response and feedback on the user's input.
    """
    data = request.get_json()
    message = data.get('message')
    history = data.get('history', [])
    locale = data.get('locale', 'en') # Default to English if not provided
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
        
    # Optional: Basic validation on history structure
    if not isinstance(history, list):
        return jsonify({"error": "History must be a list"}), 400
        
    # Fetch Learner Profile if user_id is provided
    user_id = data.get('user_id')
    learner_profile = None
    if user_id:
        try:
            conn = get_db_connection()
            learner_profile = get_learner_profile(conn, user_id)
            conn.close()
        except Exception as e:
            print(f"Error fetching profile for chat: {e}")
            
    result = chat_with_ai(message, history, locale, learner_profile)
    return jsonify(result)

@app.route('/api/users/register', methods=['POST'])
def register_user():
    """
    Register a new user.

    Returns:
        JSON: Success message and new user_id, or error if username exists.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db_connection()
    try:
        # Check if the username is occupied
        if conn.execute('SELECT user_id FROM users WHERE username = ?', (username,)).fetchone() is not None:
            return jsonify({"error": "Username already occupied"}), 400
        
        # Insert the new user
        user_id = str(uuid.uuid4())
        hashed_password = password_hash.hash(password)
        created_timestamp = datetime.now().isoformat()
        conn.execute('INSERT INTO users (user_id, username, password_hash, created_timestamp) VALUES (?, ?, ?, ?)', (user_id, username, hashed_password, created_timestamp))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"message": "User registered successfully", "user_id": user_id}), 201
    
@app.route('/api/users/login', methods=['POST'])
def login_user():
    """
    Authenticate a user.

    Returns:
        JSON: Success message and user_id if credentials match, else 401 error.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

    if user is None:
        conn.close()
        return jsonify({"error": "Invalid username or password"}), 401
    try:
        valid, updated_hash = password_hash.verify_and_update(password, user['password_hash'])
        if not valid:
            conn.close()
            return jsonify({"error": "Invalid username or password"}), 401
    except exceptions.InvalidHash:
        conn.close()
        return jsonify({"error": "Invalid username or password"}), 401
    except exceptions.MismatchedHash:
        conn.close()
        return jsonify({"error": "Invalid username or password"}), 401

    if updated_hash is not None:
        conn.execute('UPDATE users SET password_hash = ? WHERE username = ?', (updated_hash, username))
        conn.commit()

    conn.close()
    return jsonify({"message": "Login successful", "user_id": user['user_id']}), 200

@app.route('/api/statistics/<user_id>', methods=['GET'])
def get_user_statistics(user_id):
    """
    Calculate and return comprehensive statistics for a user.
    Includes accuracy by Part of Speech, JLPT level, overall summary, and daily history.

    Args:
        user_id (str): The ID of the user.

    Returns:
        JSON: Structured statistics object.
    """
    conn = get_db_connection()
    # query to get statistics for a user
    query = """
    SELECT
        e.part_of_speech,
        e.jlpt_level,
        COUNT(al.log_id) AS total_answers,
        SUM(CASE WHEN al.is_correct = 1 THEN 1 ELSE 0 END) AS correct_answers
    FROM
        answer_log al
    JOIN
        exercise e ON al.exercise_id = e.exercise_id
    WHERE
        al.user_id = ?
    GROUP BY
        e.part_of_speech,
        e.jlpt_level;
    """
    stats = conn.execute(query, (user_id,)).fetchall()
    
    # Process the stats to create the desired JSON structure
    processed_stats = {
        "pos_accuracy": {},
        "jlpt_level_accuracy": {},
        "summary": {
            "total_exercises": 0,
            "total_correct": 0,
            "average_accuracy": 0
        }
    }

    # Temporary dictionaries to hold summed values for accuracy calculation
    pos_totals = {}
    jlpt_totals = {}

    for row in stats:
        pos = row['part_of_speech']
        jlpt_level = row['jlpt_level']
        total_answers = row['total_answers']
        correct_answers = row['correct_answers']

        # Aggregate POS data
        if pos not in pos_totals:
            pos_totals[pos] = {'total': 0, 'correct': 0}
        pos_totals[pos]['total'] += total_answers
        pos_totals[pos]['correct'] += correct_answers

        # Aggregate JLPT level data
        if jlpt_level is not None:
            if jlpt_level not in jlpt_totals:
                jlpt_totals[jlpt_level] = {'total': 0, 'correct': 0}
            jlpt_totals[jlpt_level]['total'] += total_answers
            jlpt_totals[jlpt_level]['correct'] += correct_answers

    # Calculate accuracies
    for pos, totals in pos_totals.items():
        processed_stats["pos_accuracy"][pos] = (totals['correct'] / totals['total']) * 100 if totals['total'] > 0 else 0

    for jlpt_level, totals in jlpt_totals.items():
        processed_stats["jlpt_level_accuracy"][jlpt_level] = (totals['correct'] / totals['total']) * 100 if totals['total'] > 0 else 0
        
    # --- Summary ---
    # Use direct query to ensure we catch all answer logs, independent of joint constraints that might be tight
    summary_query = """
    SELECT 
        COUNT(log_id) as total,
        SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
    FROM answer_log
    WHERE user_id = ?
    """
    summary_row = conn.execute(summary_query, (user_id,)).fetchone()
    
    if summary_row:
        overall_total = summary_row['total']
        overall_correct = summary_row['correct'] if summary_row['correct'] else 0
        
        processed_stats["summary"]["total_exercises"] = overall_total
        processed_stats["summary"]["total_correct"] = overall_correct
        processed_stats["summary"]["average_accuracy"] = (overall_correct / overall_total) * 100 if overall_total > 0 else 0

    # --- History (Daily Accuracy) ---
    history_query = """
    SELECT 
        DATE(answered_timestamp) as date,
        COUNT(log_id) as total,
        SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
    FROM answer_log
    WHERE user_id = ?
    GROUP BY DATE(answered_timestamp)
    ORDER BY DATE(answered_timestamp) ASC
    """
    history_rows = conn.execute(history_query, (user_id,)).fetchall()
    conn.close() # Close connection here
    
    history_data = []
    for row in history_rows:
        date_str = row['date']
        total = row['total']
        correct = row['correct']
        accuracy = (correct / total) * 100 if total > 0 else 0
        history_data.append({
            "date": date_str,
            "accuracy": accuracy,
            "total": total
        })
    
    processed_stats["history"] = history_data

    return jsonify(processed_stats)

@app.route('/api/news', methods=['GET'])
def get_news_list():
    """
    Get a list of processed news articles.
    Supports filtering by category and date.

    Returns:
        JSON: List of article summaries.
    """
    category = request.args.get('category')
    date_str = request.args.get('date')  # Expected format YYYY-MM-DD

    conn = get_db_connection()
    
    query = "SELECT article_id, title, category, publish_timestamp FROM articles WHERE status = 'processed'"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)
    
    if date_str:
        # Match date part of ISO timestamp
        query += " AND publish_timestamp LIKE ?"
        params.append(f"{date_str}%")

    query += " ORDER BY publish_timestamp DESC LIMIT 20"

    articles = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in articles])

@app.route('/api/news/<article_id>', methods=['GET'])
def get_news_detail(article_id):
    """
    Get details of a specific news article.
    The body text is split into paragraphs for the frontend.

    Args:
        article_id (str): The ID of the article.

    Returns:
        JSON: Article details and list of paragraphs.
    """
    conn = get_db_connection()
    article = conn.execute('SELECT * FROM articles WHERE article_id = ?', (article_id,)).fetchone()
    conn.close()
    
    if not article:
        return jsonify({"error": "Article not found"}), 404
    
    data = dict(article)
    
    # Process paragraphs: split by newline, filter empty
    paragraphs = []
    raw_paragraphs = data['body_text'].split('\n')
    
    for p in raw_paragraphs:
        p = p.strip()
        # Filter out separators or empty lines
        if p and not p.startswith('---'): 
            paragraphs.append({
                "text": p,
                "translation": None,
                "loadingTranslation": False
            })
    
    return jsonify({
        "info": {
            "title": data['title'],
            "category": data['category'],
            "date": data['publish_timestamp']
        },
        "paragraphs": paragraphs
    })

@app.route('/api/translate', methods=['POST'])
def translate_paragraph():
    """
    Translate a specific text segment.

    Returns:
        JSON: {"translated_text": str}
    """
    data = request.get_json()
    text = data.get('text')
    target = data.get('target', 'zh-TW')  # Default to zh-TW if not provided
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    translated = translate_text(text, target)
    return jsonify({"translated_text": translated})

@app.route('/api/tts', methods=['POST'])
def get_tts():
    """
    Generate Text-to-Speech audio for a given text.
    
    Returns:
        Response: Audio file (WAV).
    """
    data = request.get_json()
    text = data.get('text')
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    audio_content = generate_audio(text)
    
    if not audio_content:
        return jsonify({"error": "TTS generation failed"}), 500

    return Response(audio_content, mimetype="audio/wav")

@app.route('/api/agent/daily_review/<user_id>', methods=['GET'])
def get_daily_review(user_id):
    """
    Trigger the Daily Review Agent to generate a personalized review using the Agent Service.

    Args:
        user_id (str): The ID of the user.

    Returns:
        JSON: {"review": markdown_string}
    """
    try:
        review_content = generate_daily_review_agent(user_id, DATABASE_PATH)
        return jsonify({"review": review_content})
    except Exception as e:
        print(f"Agent Error: {e}")
        return jsonify({"error": "Agent 正在忙碌中，請稍後再試"}), 500

@app.route('/api/learner/profile/<user_id>', methods=['GET'])
def get_learner_profile_route(user_id):
    """
    Get the learner profile for a specific user.

    Args:
        user_id (str): The ID of the user.

    Returns:
        JSON: Learner profile object.
    """
    conn = get_db_connection()
    try:
        profile = get_learner_profile(conn, user_id)
        return jsonify(profile)
    finally:
        conn.close()

@app.route('/api/learner/recalculate/<user_id>', methods=['POST'])
def recalculate_learner_profile_route(user_id):
    """
    Force a recalculation (backfill) of the learner profile based on all logs.

    Args:
        user_id (str): The ID of the user.

    Returns:
        JSON: Updated learner profile object.
    """
    conn = get_db_connection()
    try:
        # Check if user exists first (optional but good)
        user = conn.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        profile = backfill_learner_profile(conn, user_id)
        return jsonify(profile)
    finally:
        conn.close()


@app.route('/api/users/profile', methods=['POST'])
def update_profile():
    """
    Update specific settings in the learner profile (like level estimate or feedback preference).

    Returns:
        JSON: Updated learner profile object.
    """
    data = request.json
    user_id = data.get('user_id')
    settings = data.get('settings')
    
    if not user_id or not settings:
        return jsonify({"error": "Missing user_id or settings"}), 400
        
    conn = get_db_connection()
    try:
        updated_profile = update_learner_settings(conn, user_id, settings)
        return jsonify(updated_profile)
    except Exception as e:
        print(f"Error updating profile: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        conn.close()


if __name__ == '__main__':
    app.run(debug=True)