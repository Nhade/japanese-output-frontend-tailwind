import sqlite3
import json
import os
from datetime import datetime
from ai_service import query_llm



def generate_daily_review_agent(user_id, db_path):
    """
    Generates a daily review for the user based on their mistakes from the current day.
    
    This function performs a 3-step agentic workflow:
    1. Analysis: Analyzes the user's mistakes to identify weakness patterns.
    2. Drafting: Drafts a supportive and educational review based on the analysis.
    3. Polishing: Polishes the review to ensure a professional and encouraging tone.

    Args:
        user_id (str): The value of the user's ID.
        db_path (str): The path to the SQLite database.

    Returns:
        str: The final polished daily review text in Markdown format.
    """
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
    try:
        analysis_result = query_llm([{"role": "user", "content": prompt_analysis}])
    except Exception as e:
        print(f"Agent Step 1 Failed: {e}")
        return "無法進行分析。"

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
    try:
        draft_result = query_llm(messages_draft)
    except Exception as e:
        print(f"Agent Step 2 Failed: {e}")
        return analysis_result or "無法產生回顧。"

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
    try:
        final_result = query_llm(messages_polish)
    except Exception as e:
        print(f"Agent Step 3 Failed: {e}")
        return draft_result or "無法優化草稿。"

    return final_result
