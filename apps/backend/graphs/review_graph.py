"""
Daily review workflow as a LangGraph StateGraph.

Graph: fetch_mistakes →[no mistakes?]→ END
                      →[has mistakes]→ analyze → draft → polish → END

Each LLM step has graceful degradation: if a later step fails,
the best partial output from an earlier step is returned.
"""
import sqlite3
from datetime import datetime
from typing import TypedDict

from langgraph.graph import END, StateGraph

from ai_core import query_llm

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ReviewState(TypedDict, total=False):
    # Inputs
    user_id: str
    db_path: str
    # Intermediate
    mistakes_text: str
    has_mistakes: bool
    analysis_result: str
    draft_result: str
    # Output
    result: str


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def fetch_mistakes(state: ReviewState) -> dict:
    conn = sqlite3.connect(state["db_path"])
    conn.row_factory = sqlite3.Row

    query = '''
        SELECT e.question_sentence, e.correct_answer, al.user_answer, al.error_type
        FROM answer_log al
        JOIN exercise e ON al.exercise_id = e.exercise_id
        WHERE al.user_id = ?
          AND al.is_correct = 0
          AND date(al.answered_timestamp) = date('now', 'localtime')
    '''

    print(f"Querying mistakes for user {state['user_id']} on {datetime.now().date()}")

    mistakes = conn.execute(query, (state["user_id"],)).fetchall()
    conn.close()

    if not mistakes:
        return {
            "has_mistakes": False,
            "result": "今天還沒有錯題紀錄喔！去練習幾題再來吧！💪",
        }

    # Format mistake data for AI
    mistake_text = ""
    for idx, m in enumerate(mistakes, 1):
        mistake_text += (
            f"{idx}. Q: {m['question_sentence']}\n"
            f"   User: {m['user_answer']} | Correct: {m['correct_answer']} | Type: {m['error_type']}\n"
        )

    return {
        "has_mistakes": True,
        "mistakes_text": mistake_text,
    }


def analyze(state: ReviewState) -> dict:
    print("Agent Step 1: Analyzing patterns...")

    prompt = f"""
    你是日文教學專家。請分析以下學生的今日錯題，找出 2-3 個主要的弱點模式（例如：特定助詞搞混、動詞變化不熟、還是單純粗心？）。

    錯題列表：
    {state["mistakes_text"]}

    請簡短列出分析結果。
    """

    try:
        analysis = query_llm([{"role": "user", "content": prompt}])
        return {"analysis_result": analysis}
    except Exception as e:
        print(f"Agent Step 1 Failed: {e}")
        return {"analysis_result": "", "result": "無法進行分析。"}


def draft(state: ReviewState) -> dict:
    # Short-circuit if earlier node already set a final result (failure case)
    if state.get("result") and not state.get("analysis_result"):
        return {}

    print("Agent Step 2: Drafting review...")

    prompt_analysis = f"""
    你是日文教學專家。請分析以下學生的今日錯題，找出 2-3 個主要的弱點模式（例如：特定助詞搞混、動詞變化不熟、還是單純粗心？）。

    錯題列表：
    {state["mistakes_text"]}

    請簡短列出分析結果。
    """

    prompt_draft = f"""
    基於上述的分析結果，請用「溫暖、鼓勵但專業」的語氣，寫一份「今日學習總結」。

    分析結果：
    {state["analysis_result"]}

    要求：
    1. 指出今天做得好的地方（即使是錯題，也要肯定嘗試）。
    2. 重點講解 1-2 個今天最需要改進的觀念。
    3. 給出一個具體的建議練習方向。
    4. 使用繁體中文。
    """

    messages = [
        {"role": "user", "content": prompt_analysis},
        {"role": "assistant", "content": state["analysis_result"]},
        {"role": "user", "content": prompt_draft},
    ]

    try:
        draft_text = query_llm(messages)
        return {"draft_result": draft_text}
    except Exception as e:
        print(f"Agent Step 2 Failed: {e}")
        return {"result": state.get("analysis_result") or "無法產生回顧。"}


def polish(state: ReviewState) -> dict:
    # Short-circuit if earlier node already set a final result (failure case)
    if state.get("result") and not state.get("draft_result"):
        return {}

    print("Agent Step 3: Polishing...")

    prompt_analysis = f"""
    你是日文教學專家。請分析以下學生的今日錯題，找出 2-3 個主要的弱點模式（例如：特定助詞搞混、動詞變化不熟、還是單純粗心？）。

    錯題列表：
    {state["mistakes_text"]}

    請簡短列出分析結果。
    """

    prompt_draft = f"""
    基於上述的分析結果，請用「溫暖、鼓勵但專業」的語氣，寫一份「今日學習總結」。

    分析結果：
    {state["analysis_result"]}

    要求：
    1. 指出今天做得好的地方（即使是錯題，也要肯定嘗試）。
    2. 重點講解 1-2 個今天最需要改進的觀念。
    3. 給出一個具體的建議練習方向。
    4. 使用繁體中文。
    """

    prompt_polish = """
    請作為編輯，檢查上述草稿。
    優化排版，使用 Markdown 格式（Bold, List, Quote）。
    確保語氣像是一個貼心的 AI 助教 (Agent)。
    開頭加上「📅 今日錯題回顧」。
    """

    messages = [
        {"role": "user", "content": prompt_analysis},
        {"role": "assistant", "content": state["analysis_result"]},
        {"role": "user", "content": prompt_draft},
        {"role": "assistant", "content": state["draft_result"]},
        {"role": "user", "content": prompt_polish},
    ]

    try:
        final = query_llm(messages)
        return {"result": final}
    except Exception as e:
        print(f"Agent Step 3 Failed: {e}")
        return {"result": state.get("draft_result") or "無法優化草稿。"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def route_after_fetch(state: ReviewState) -> str:
    if not state.get("has_mistakes"):
        return END
    return "analyze"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_review_graph():
    graph = StateGraph(ReviewState)
    graph.add_node("fetch_mistakes", fetch_mistakes)
    graph.add_node("analyze", analyze)
    graph.add_node("draft", draft)
    graph.add_node("polish", polish)

    graph.set_entry_point("fetch_mistakes")
    graph.add_conditional_edges(
        "fetch_mistakes",
        route_after_fetch,
        {END: END, "analyze": "analyze"},
    )
    graph.add_edge("analyze", "draft")
    graph.add_edge("draft", "polish")
    graph.add_edge("polish", END)

    return graph.compile()


# Compile once at module load
_review_graph = _build_review_graph()


# ---------------------------------------------------------------------------
# Public runner function (drop-in replacement)
# ---------------------------------------------------------------------------

def generate_daily_review_agent(user_id: str, db_path: str) -> str:
    """
    Generates a daily review for the user based on their mistakes from the current day.

    This function performs a 3-step agentic workflow via LangGraph:
    1. Analysis: Analyzes the user's mistakes to identify weakness patterns.
    2. Drafting: Drafts a supportive and educational review based on the analysis.
    3. Polishing: Polishes the review to ensure a professional and encouraging tone.

    Args:
        user_id (str): The value of the user's ID.
        db_path (str): The path to the SQLite database.

    Returns:
        str: The final polished daily review text in Markdown format.
    """
    initial_state = {
        "user_id": user_id,
        "db_path": db_path,
    }
    final_state = _review_graph.invoke(initial_state)
    return final_state["result"]
