import sqlite3
import json
import os
from datetime import datetime
from ai_service import BASE_URL, API_KEY, MODEL_NAME, AI_TIMEOUT
import requests

def call_llm(messages):
    url = f"{BASE_URL}/api/chat"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "temperature": 0.7 
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=AI_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        content = data.get("message", {}).get("content", "")
        if not content:
             content = data.get("response", "")
        return content
    except Exception as e:
        print(f"LLM Call Error: {e}")
        return None

def generate_daily_review_agent(user_id, db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # 1. Retrieve today's mistakes (using localtime to ensure local time today)
    query = '''
        SELECT e.question_sentence, e.correct_answer, al.user_answer, al.error_type
        FROM answer_log al
        JOIN exercise e ON al.exercise_id = e.exercise_id
        WHERE al.user_id = ? 
          AND al.is_correct = 0 
          AND date(al.answered_timestamp) = date('now', 'localtime')
    '''

    print(f"Querying mistakes for user {user_id} on {datetime.now().date()}")
    
    mistakes = conn.execute(query, (user_id,)).fetchall()
    conn.close()

    if not mistakes:
        return "今天還沒有錯題紀錄喔！去練習幾題再來吧！💪"

    # Format mistake data for AI
    mistake_text = ""
    for idx, m in enumerate(mistakes, 1):
        mistake_text += f"{idx}. Q: {m['question_sentence']}\n   User: {m['user_answer']} | Correct: {m['correct_answer']} | Type: {m['error_type']}\n"

    # --- Agent Step 1: Analyze patterns (Analysis) ---
    print("Agent Step 1: Analyzing patterns...")
    prompt_analysis = f"""
    你是日文教學專家。請分析以下學生的今日錯題，找出 2-3 個主要的弱點模式（例如：特定助詞搞混、動詞變化不熟、還是單純粗心？）。
    
    錯題列表：
    {mistake_text}
    
    請簡短列出分析結果。
    """
    analysis_result = call_llm([{"role": "user", "content": prompt_analysis}])

    # --- Agent Step 2: Draft review (Drafting) ---
    print("Agent Step 2: Drafting review...")
    prompt_draft = f"""
    基於上述的分析結果，請用「溫暖、鼓勵但專業」的語氣，寫一份「今日學習總結」。
    
    分析結果：
    {analysis_result}
    
    要求：
    1. 指出今天做得好的地方（即使是錯題，也要肯定嘗試）。
    2. 重點講解 1-2 個今天最需要改進的觀念。
    3. 給出一個具體的建議練習方向。
    4. 使用繁體中文。
    """

    messages_draft = [
        {"role": "user", "content": prompt_analysis},
        {"role": "assistant", "content": analysis_result},
        {"role": "user", "content": prompt_draft}
    ]
    draft_result = call_llm(messages_draft)

    # --- Agent Step 3: Final polishing (Polishing) ---
    print("Agent Step 3: Polishing...")
    prompt_polish = f"""
    請作為編輯，檢查上述草稿。
    優化排版，使用 Markdown 格式（Bold, List, Quote）。
    確保語氣像是一個貼心的 AI 助教 (Agent)。
    開頭加上「📅 今日錯題回顧」。
    """
    messages_polish = messages_draft + [
        {"role": "assistant", "content": draft_result},
        {"role": "user", "content": prompt_polish}
    ]
    final_result = call_llm(messages_polish)

    return final_result
