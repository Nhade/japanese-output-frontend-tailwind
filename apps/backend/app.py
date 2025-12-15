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
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/exercise/random', methods=['GET'])
def get_random_exercise():
    conn = get_db_connection()
    exercise = conn.execute('SELECT exercise_id, question_sentence, hint_chinese FROM exercise ORDER BY RANDOM() LIMIT 1').fetchone()
    conn.close()
    if exercise is None:
        return jsonify({"error": "No exercises found"}), 404
    
    return jsonify(dict(exercise))

@app.route('/api/mistakes/<user_id>', methods=['GET'])
def get_mistakes(user_id):
    conn = get_db_connection()
    mistakes = conn.execute('''
        SELECT al.log_id, e.question_sentence, al.user_answer, e.correct_answer,
               al.feedback, al.score, al.error_type
        FROM answer_log al
        JOIN exercise e ON al.exercise_id = e.exercise_id
        WHERE al.user_id = ? AND al.is_correct = 0
    ''', (user_id,)).fetchall()
    conn.close()

    return jsonify([dict(mistake) for mistake in mistakes])

from ai_service import evaluate_submission, get_detailed_feedback

@app.route('/api/exercise/submit', methods=['POST'])
def submit_answer():
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    user_answer = data.get('user_answer', '').strip()
    user_id = data.get('user_id')

    if not exercise_id or not user_id:
        return jsonify({"error": "exercise_id and user_id are required"}), 400

    conn = get_db_connection()
    try:
        # Fetch question_sentence as well
        row = conn.execute('SELECT question_sentence, correct_answer FROM exercise WHERE exercise_id = ?', (exercise_id,)).fetchone()

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
        conn.commit()
        
    finally:
        conn.close()
        
    return jsonify({
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "log_id": log_id
    })

@app.route('/api/exercise/explain', methods=['POST'])
def explain_answer():
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

@app.route('/api/users/register', methods=['POST'])
def register_user():
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
    conn.close()

    # Process the stats to create the desired JSON structure
    processed_stats = {
        "pos_accuracy": {},
        "jlpt_level_accuracy": {}
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

    return jsonify(processed_stats)

@app.route('/api/news', methods=['GET'])
def get_news_list():
    conn = get_db_connection()
    # Limit to 20 recent processed articles
    articles = conn.execute('''
        SELECT article_id, title, category, publish_timestamp 
        FROM articles 
        WHERE status = 'processed' 
        ORDER BY publish_timestamp DESC 
        LIMIT 20
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in articles])

@app.route('/api/news/<article_id>', methods=['GET'])
def get_news_detail(article_id):
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
    data = request.get_json()
    text = data.get('text')
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    translated = translate_text(text)
    return jsonify({"translated_text": translated})

@app.route('/api/tts', methods=['POST'])
def get_tts():
    data = request.get_json()
    text = data.get('text')
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    audio_content = generate_audio(text)
    
    if not audio_content:
        return jsonify({"error": "TTS generation failed"}), 500

    return Response(audio_content, mimetype="audio/mpeg")

if __name__ == '__main__':
    app.run(debug=True)