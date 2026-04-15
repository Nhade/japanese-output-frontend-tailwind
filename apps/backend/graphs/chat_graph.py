"""
Chat workflow as a LangGraph StateGraph.

Graph: safety_check → build_context → call_llm → END
       (violation shortcircuits to END)
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph

from ai_core import (
    build_learner_context,
    check_safety,
    query_llm_json,
)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ChatState(TypedDict, total=False):
    # Inputs
    message: str
    history: list
    locale: str
    learner_profile: dict
    # Intermediate
    safety_result: dict
    is_violation: bool
    learner_context: str
    max_corrections: int
    messages: list
    # Output
    result: dict


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def safety_check(state: ChatState) -> dict:
    safety_result = check_safety(state["message"])
    is_violation = safety_result.get("violation", 0) == 1

    update: dict = {
        "safety_result": safety_result,
        "is_violation": is_violation,
    }

    if is_violation:
        print(f"Safety Violation Detected: {safety_result.get('rationale')}")
        update["result"] = {
            "response": "申し訳ありませんが、そのリクエストにはお答えできません。（日本語学習に関連しない、またはポリシー違反の可能性があります）",
            "feedback": {
                "overall": "Safety violation detected. Please stick to Japanese learning topics.",
                "corrections": [],
            },
            "retry_count": 0,
        }

    return update


def build_context(state: ChatState) -> dict:
    history = state.get("history", [])
    locale = state.get("locale", "en")
    learner_profile = state.get("learner_profile")

    # Sliding window — keep last 20 turns
    trimmed_history = history[-20:] if len(history) > 20 else history

    # Determine feedback language
    if locale == "en":
        feedback_intro = "Reply in Japanese (Natural). Feedback/Explanations MUST be in English."
        feedback_lang = "English"
    else:
        feedback_intro = "Reply in Japanese (Natural). Feedback/Explanations MUST be in Traditional Chinese (繁體中文)."
        feedback_lang = "Traditional Chinese"

    # Build learner context
    if learner_profile:
        context_data = build_learner_context(learner_profile)
        learner_context = context_data["summary"]
        max_corrections = context_data["max_corrections"]
    else:
        learner_context = "Learner profile: User is a beginner. Treat as N5 level."
        max_corrections = 2

    system_prompt = f"""
    You are a friendly and helpful Japanese language tutor.

    Your goal is to have a natural conversation with the user in Japanese,
    while providing focused, level-appropriate feedback based on their learning profile.

    {learner_context}

    Instructions:

    1. Role
    - Act as a native Japanese speaker.
    - Be polite, encouraging, and supportive.
    - Match your Japanese difficulty to the learner's estimated level.
      - N5: short sentences, common words, です／ます form
      - N4: slightly longer sentences, simple casual allowed if user uses it
      - N3+: more natural expressions allowed

    2. Language rules
    - Your reply ("response") MUST be in Japanese only.
    - All feedback content MUST be written in {feedback_lang}.
    - {feedback_intro}

    3. Feedback rules
    - You MUST prioritize corrections related to the learner's weak points.
    - Do NOT correct everything.
    - Focus on errors that affect clarity or sound unnatural.
    - Limit the number of corrections to AT MOST {max_corrections}.
    - If the learner's Japanese is acceptable, keep feedback encouraging and minimal.

    4. Correction format rules
    - In each correction, quote ONLY the minimal incorrect part.
    - Use clear and simple explanations suitable for the learner's level.

    5. Non-Japanese input handling
    - If the user writes mostly in English or Chinese:
      - Respond politely in Japanese encouraging them to try Japanese.
      - Still provide brief feedback in {feedback_lang} if possible.

    6. Output format (STRICT)
    - You MUST return a VALID JSON object.
    - DO NOT output any text outside the JSON.
    - DO NOT include markdown or explanations outside JSON.

    JSON Structure:
    {{
      "response": "Your natural Japanese reply.",
      "feedback": {{
        "overall": "Brief evaluation or encouragement (in {feedback_lang}).",
        "corrections": [
          {{
            "type": "particle | conjugation | word_choice | politeness | word_order | other",
            "original": "incorrect part only",
            "corrected": "corrected Japanese",
            "explanation": "explanation in {feedback_lang}"
          }}
        ]
      }}
    }}

    If the user's Japanese is correct or natural enough, return an empty list for "corrections".
    """

    messages = [{"role": "system", "content": system_prompt}]

    # Append history
    for msg in trimmed_history:
        role = "assistant" if msg.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": msg.get("content", "")})

    # Append current message
    messages.append({"role": "user", "content": state["message"]})

    return {
        "learner_context": learner_context,
        "max_corrections": max_corrections,
        "messages": messages,
    }


def call_llm(state: ChatState) -> dict:
    try:
        result = query_llm_json(state["messages"], temperature=0.7)
        retry_count = result["retry_count"]

        if result["error"]:
            return {
                "result": {
                    "response": "すみません、エラーが発生しました。",
                    "feedback": {
                        "overall": f"AI 服務暫時無法回應 (格式錯誤, retried {retry_count} times)",
                        "corrections": [],
                    },
                    "retry_count": retry_count,
                }
            }

        result_json = result["data"]

        # Validate keys
        if "response" not in result_json:
            result_json["response"] = "申し訳ありません、もう一度お願いします。"

        if "feedback" not in result_json:
            result_json["feedback"] = {
                "overall": "無法取得回饋",
                "corrections": [],
            }

        result_json["retry_count"] = retry_count
        return {"result": result_json}

    except Exception as e:
        print(f"Chat error: {e}")
        return {
            "result": {
                "response": "すみません、エラーが発生しました。",
                "feedback": {
                    "overall": f"AI 服務暫時無法回應 ({str(e)})",
                    "corrections": [],
                },
                "retry_count": 0,
            }
        }


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def route_after_safety(state: ChatState) -> str:
    if state.get("is_violation"):
        return END
    return "build_context"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("safety_check", safety_check)
    graph.add_node("build_context", build_context)
    graph.add_node("call_llm", call_llm)

    graph.set_entry_point("safety_check")
    graph.add_conditional_edges(
        "safety_check",
        route_after_safety,
        {END: END, "build_context": "build_context"},
    )
    graph.add_edge("build_context", "call_llm")
    graph.add_edge("call_llm", END)

    return graph.compile()


# Compile once at module load
_chat_graph = _build_chat_graph()


# ---------------------------------------------------------------------------
# Public runner function (drop-in replacement)
# ---------------------------------------------------------------------------

def chat_with_ai(message: str, history: list, locale: str = 'en', learner_profile: dict = None) -> dict:
    """
    Chat with the AI in Japanese.

    Args:
        message: The latest user message.
        history: List of dictionary {'role': 'user'|'assistant', 'content': '...'}
        locale: User's locale (e.g. 'en', 'ja', 'zh-tw').
        learner_profile: Dict containing learner stats and preferences.

    Returns:
        Dict with keys:
        - response: Japanese reply
        - feedback: Dict containing analysis of the user's Japanese
        - retry_count: Number of JSON parse retries
    """
    initial_state = {
        "message": message,
        "history": history,
        "locale": locale,
        "learner_profile": learner_profile,
    }
    final_state = _chat_graph.invoke(initial_state)
    return final_state["result"]
