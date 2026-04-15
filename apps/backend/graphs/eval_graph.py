"""
Exercise evaluation workflows as LangGraph StateGraphs.

Two graphs:
  - eval_graph: evaluate_submission() — classify errors and score
  - detailed_feedback_graph: get_detailed_feedback() — grammatical explanation
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph

from ai_core import (
    ErrorType,
    calculate_score,
    check_safety,
    query_llm,
    query_llm_json,
)

# ---------------------------------------------------------------------------
# State definitions
# ---------------------------------------------------------------------------

class EvalState(TypedDict, total=False):
    # Inputs
    question: str
    user_answer: str
    correct_answer: str
    # Intermediate
    safety_result: dict
    is_violation: bool
    messages: list
    # Output
    result: dict


class DetailedFeedbackState(TypedDict, total=False):
    # Inputs
    question: str
    user_answer: str
    correct_answer: str
    # Intermediate
    safety_result: dict
    is_violation: bool
    messages: list
    # Output
    result: str


# ---------------------------------------------------------------------------
# Eval graph nodes
# ---------------------------------------------------------------------------

def eval_safety_check(state: EvalState) -> dict:
    safety_result = check_safety(state["user_answer"])
    is_violation = safety_result.get("violation", 0) == 1

    update: dict = {
        "safety_result": safety_result,
        "is_violation": is_violation,
    }

    if is_violation:
        print(f"Safety Violation in Submission: {safety_result.get('rationale')}")
        update["result"] = {
            "is_correct": False,
            "score": 0,
            "error_type": "other",
            "feedback": "Safety violation detected (Policy Rejection)",
            "deduction": 100,
            "retry_count": 0,
        }

    return update


def build_eval_prompt(state: EvalState) -> dict:
    system_prompt = """
    You are a strict Japanese language teacher.
    Analyze the user's answer based on the correct answer and the question context.

    Classify the error into one of these types:
    - NONE: Perfect match or semantically identical.
    - TYPO: Minor kana/kanji mistakes.
    - VOCAB: Wrong word choice but grammatically ok.
    - PARTICLE: Wrong particle.
    - CONJUGATION: Wrong verb/adjective conjugation.
    - UNNATURAL: Grammatically correct but contextually weird, or complete nonsense.

    Provide a concise explanation in Traditional Chinese (繁體中文), around 30-50 characters.

    Respond STRICTLY in JSON format with two keys. Do NOT output any "thinking" or conversational text.

    Example Output:
    {
        "error_type": "conjugation",
        "reasoning": "動詞「食べます」的否定形應該是「食べません」，而不是「食べくない」。"
    }
    """

    user_prompt = f"""
    Question: {state["question"]}
    Correct Answer: {state["correct_answer"]}
    User Answer: {state["user_answer"]}
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return {"messages": messages}


def call_llm_and_score(state: EvalState) -> dict:
    try:
        result = query_llm_json(state["messages"], temperature=0.1)
        retry_count = result["retry_count"]

        if result["error"]:
            print(f"Failed to evaluate submission after retries. Error: {result['error']}")
            return {
                "result": {
                    "is_correct": False,
                    "score": 0,
                    "error_type": "unknown",
                    "feedback": f"AI 回應格式錯誤 (Retried {retry_count} times)",
                    "deduction": 0,
                    "retry_count": retry_count,
                }
            }

        result_json = result["data"]
        error_type_str = result_json.get("error_type", "other").lower()
        reasoning = result_json.get("reasoning", "No feedback provided")

        try:
            error_type_enum = ErrorType(error_type_str)
        except ValueError:
            error_type_enum = ErrorType.OTHER

        deduction = calculate_score(error_type_enum)
        final_score = max(0, 100 + deduction)

        return {
            "result": {
                "is_correct": error_type_enum == ErrorType.NONE,
                "score": final_score,
                "error_type": error_type_enum.value,
                "feedback": reasoning,
                "deduction": deduction,
                "retry_count": retry_count,
            }
        }

    except Exception as e:
        print(f"Unexpected error in evaluate_submission: {e}")
        return {
            "result": {
                "is_correct": False,
                "score": 0,
                "error_type": "unknown",
                "feedback": "AI 服務發生未預期錯誤",
                "deduction": 0,
                "retry_count": 0,
            }
        }


# ---------------------------------------------------------------------------
# Detailed feedback graph nodes
# ---------------------------------------------------------------------------

def feedback_safety_check(state: DetailedFeedbackState) -> dict:
    safety_result = check_safety(state["user_answer"])
    is_violation = safety_result.get("violation", 0) == 1

    update: dict = {
        "safety_result": safety_result,
        "is_violation": is_violation,
    }

    if is_violation:
        update["result"] = "Safety violation detected. Detailed feedback is unavailable for this input."

    return update


def build_feedback_prompt(state: DetailedFeedbackState) -> dict:
    system_prompt = """
    You are a helpful Japanese language teacher.
    The user has answered a Japanese grammar question incorrectly (or partially incorrectly).

    Provide a detailed explanation in Traditional Chinese (繁體中文).
    - Analyze the user's mistake.
    - Explain the grammar point involved in the correct answer.
    - Provide 1-2 example sentences using the correct grammar.

    Keep the tone encouraging. Use Markdown formatting (bullet points, bold text) for readability.
    """

    user_prompt = f"""
    Question: {state["question"]}
    Correct Answer: {state["correct_answer"]}
    User Answer: {state["user_answer"]}
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return {"messages": messages}


def call_llm_feedback(state: DetailedFeedbackState) -> dict:
    try:
        content = query_llm(state["messages"], json_mode=False, temperature=0.7)
        return {"result": content}
    except Exception as e:
        print(f"Failed to get detailed feedback. Error: {e}")
        return {"result": "抱歉，目前無法取得詳細解說。"}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def route_after_safety(state: dict) -> str:
    if state.get("is_violation"):
        return END
    return "build_prompt"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_eval_graph():
    graph = StateGraph(EvalState)
    graph.add_node("safety_check", eval_safety_check)
    graph.add_node("build_prompt", build_eval_prompt)
    graph.add_node("call_llm_and_score", call_llm_and_score)

    graph.set_entry_point("safety_check")
    graph.add_conditional_edges(
        "safety_check",
        route_after_safety,
        {END: END, "build_prompt": "build_prompt"},
    )
    graph.add_edge("build_prompt", "call_llm_and_score")
    graph.add_edge("call_llm_and_score", END)

    return graph.compile()


def _build_detailed_feedback_graph():
    graph = StateGraph(DetailedFeedbackState)
    graph.add_node("safety_check", feedback_safety_check)
    graph.add_node("build_prompt", build_feedback_prompt)
    graph.add_node("call_llm", call_llm_feedback)

    graph.set_entry_point("safety_check")
    graph.add_conditional_edges(
        "safety_check",
        route_after_safety,
        {END: END, "build_prompt": "build_prompt"},
    )
    graph.add_edge("build_prompt", "call_llm")
    graph.add_edge("call_llm", END)

    return graph.compile()


# Compile once at module load
_eval_graph = _build_eval_graph()
_detailed_feedback_graph = _build_detailed_feedback_graph()


# ---------------------------------------------------------------------------
# Public runner functions (drop-in replacements)
# ---------------------------------------------------------------------------

def evaluate_submission(question: str, user_answer: str, correct_answer: str) -> dict:
    """
    Call Server LLM to evaluate the learner's submission against the correct answer.

    Args:
        question (str): The question being asked.
        user_answer (str): The answer provided by the user.
        correct_answer (str): The correct answer for the question.

    Returns:
        dict: Evaluation results containing:
            - "is_correct": bool
            - "score": int (0-100)
            - "error_type": str (from ErrorType)
            - "feedback": str (reasoning)
            - "deduction": int
            - "retry_count": int
    """
    initial_state = {
        "question": question,
        "user_answer": user_answer,
        "correct_answer": correct_answer,
    }
    final_state = _eval_graph.invoke(initial_state)
    return final_state["result"]


def get_detailed_feedback(question: str, user_answer: str, correct_answer: str) -> str:
    """
    Ask AI for a detailed grammatical explanation of the user's error.

    Args:
        question (str): The question context.
        user_answer (str): The user's incorrect answer.
        correct_answer (str): The correct answer.

    Returns:
        str: A detailed explanation in Traditional Chinese with Markdown formatting.
    """
    initial_state = {
        "question": question,
        "user_answer": user_answer,
        "correct_answer": correct_answer,
    }
    final_state = _detailed_feedback_graph.invoke(initial_state)
    return final_state["result"]
