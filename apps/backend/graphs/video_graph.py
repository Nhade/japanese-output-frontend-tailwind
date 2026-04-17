"""
Video comprehension workflows as LangGraph StateGraphs.

Two graphs:
  - comprehension_gen_graph: generate MCQ comprehension questions from transcript
  - comprehension_check_graph: evaluate a user's comprehension answer
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph

from ai_core import query_llm, query_llm_json

# ---------------------------------------------------------------------------
# State definitions
# ---------------------------------------------------------------------------

class ComprehensionGenState(TypedDict, total=False):
    transcript: str
    video_title: str
    num_questions: int
    result: list  # [{question, choices, correct_index, explanation}, ...]


class ComprehensionCheckState(TypedDict, total=False):
    question: str
    choices: list
    correct_index: int
    user_answer_index: int
    transcript_context: str
    result: dict  # {is_correct, feedback, score}


# ---------------------------------------------------------------------------
# Comprehension generation nodes
# ---------------------------------------------------------------------------

def generate_questions_node(state: ComprehensionGenState) -> dict:
    num = state.get("num_questions", 5)
    title = state.get("video_title", "")
    transcript = state["transcript"]

    # Truncate transcript if too long (keep ~3000 chars for context window)
    if len(transcript) > 3000:
        transcript = transcript[:3000] + "..."

    prompt = f"""你是日語教學專家。根據以下影片字幕內容，出 {num} 題理解測驗（選擇題）。

影片標題：{title}

字幕內容：
{transcript}

要求：
1. 每題有 4 個選項（A、B、C、D），只有一個正確答案。
2. 題目應測試對內容的理解（主旨、細節、因果關係等）。
3. 題目和選項都用日文撰寫。
4. 用 JSON 格式回覆，結構如下：

{{
  "questions": [
    {{
      "question": "題目文字",
      "choices": ["選項A", "選項B", "選項C", "選項D"],
      "correct_index": 0,
      "explanation": "簡短解釋為什麼這是正確答案（繁體中文）"
    }}
  ]
}}
"""

    try:
        result = query_llm_json(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        if result["data"] and "questions" in result["data"]:
            return {"result": result["data"]["questions"]}
        return {"result": []}
    except Exception as e:
        print(f"Comprehension generation failed: {e}")
        return {"result": []}


# ---------------------------------------------------------------------------
# Comprehension check nodes
# ---------------------------------------------------------------------------

def check_answer_node(state: ComprehensionCheckState) -> dict:
    correct_idx = state["correct_index"]
    user_idx = state["user_answer_index"]
    is_correct = correct_idx == user_idx

    if is_correct:
        return {
            "result": {
                "is_correct": True,
                "feedback": "正確！",
                "score": 100,
            }
        }

    # Wrong answer — generate brief explanation
    question = state["question"]
    choices = state["choices"]
    correct_answer = choices[correct_idx] if correct_idx < len(choices) else ""
    user_answer = choices[user_idx] if user_idx < len(choices) else ""
    context = state.get("transcript_context", "")

    prompt = f"""學生答錯了一道理解題。請用繁體中文簡短說明正確答案及原因（50-80字）。

題目：{question}
學生選擇：{user_answer}
正確答案：{correct_answer}
相關字幕段落：{context[:500]}
"""

    try:
        feedback = query_llm(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )
    except Exception:
        feedback = f"正確答案是：{correct_answer}"

    return {
        "result": {
            "is_correct": False,
            "feedback": feedback,
            "score": 0,
        }
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_comprehension_gen_graph():
    graph = StateGraph(ComprehensionGenState)
    graph.add_node("generate_questions", generate_questions_node)
    graph.set_entry_point("generate_questions")
    graph.add_edge("generate_questions", END)
    return graph.compile()


def _build_comprehension_check_graph():
    graph = StateGraph(ComprehensionCheckState)
    graph.add_node("check_answer", check_answer_node)
    graph.set_entry_point("check_answer")
    graph.add_edge("check_answer", END)
    return graph.compile()


# Compile once at module load
_comprehension_gen_graph = _build_comprehension_gen_graph()
_comprehension_check_graph = _build_comprehension_check_graph()


# ---------------------------------------------------------------------------
# Public runner functions
# ---------------------------------------------------------------------------

def generate_comprehension_questions(transcript: str, title: str = "", num_questions: int = 5) -> list:
    """Generate MCQ comprehension questions from a video transcript.

    Returns list of dicts: [{question, choices, correct_index, explanation}, ...]
    """
    state = {
        "transcript": transcript,
        "video_title": title,
        "num_questions": num_questions,
    }
    final = _comprehension_gen_graph.invoke(state)
    return final["result"]


def check_comprehension_answer(
    question: str,
    choices: list,
    correct_index: int,
    user_answer_index: int,
    transcript_context: str = "",
) -> dict:
    """Check a comprehension answer and generate feedback if wrong.

    Returns dict: {is_correct, feedback, score}
    """
    state = {
        "question": question,
        "choices": choices,
        "correct_index": correct_index,
        "user_answer_index": user_answer_index,
        "transcript_context": transcript_context,
    }
    final = _comprehension_check_graph.invoke(state)
    return final["result"]
