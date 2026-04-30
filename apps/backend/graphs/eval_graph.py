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


# ---------------------------------------------------------------------------
# pattern_use evaluator — used by /api/practice/submit
# ---------------------------------------------------------------------------

import json as _json
import sqlite3 as _sqlite3
from typing import Callable as _Callable, Optional as _Optional

from tools.detect_pattern import detect_pattern as _detect_pattern
from tools.morphological_diff import morphological_diff as _morph_diff

_PATTERN_USE_LOCALE_LABELS = {
    "en": "English",
    "zh-tw": "Traditional Chinese",
    "zh-TW": "Traditional Chinese",
    "ja": "Japanese",
}

# The rubric is intentionally explicit. Earlier prompts said "naturalness
# + situation fit (20%)" and the judge invented criteria each call,
# producing opposite scores for opposite-meaning sentences. Each check
# below is a concrete yes/no so the judgement is reproducible.
_PATTERN_USE_RUBRIC_PROMPT = """You are evaluating a learner's open-form
Japanese answer. Be reproducible: every score must trace to one of the
listed checks. Do not invent additional criteria.

You will receive:
  - pattern_name, pattern_meaning_locale
  - target_register: one of "polite", "plain", "casual", "formal",
    "neutral". This is the register the exercise is testing. Do NOT
    deduct for matching it. "neutral" allows either.
  - reference_answer: a model answer. Do NOT require the learner to
    match it verbatim, but use it as an anchor (see check 4).
  - user_answer
  - detector_result.detected: deterministic check for pattern usage —
    source of truth.
  - morph_diff: deterministic morphological comparison between
    reference_answer and user_answer. Includes shared verb lemmas,
    verb_form_match (do shared lemmas use the same form category),
    particle_jaccard (0..1 over distinct particles), negation_match.

Score = sum of these four signals, each 0.0..0.25:

  1) PATTERN (0.25). detector_result.detected == true → 0.25, else 0.
  2) PARSEABILITY + CONJUGATION (0.25). Does the sentence parse as a
     single Japanese sentence (subject + predicate, ends with a verb,
     adjective, or copula)? Are verb endings well-formed (no truncated
     conjugations, no kana-mixed errors)? Score 0.25 / 0.15 / 0.05 / 0
     for clean / minor-typo / one-real-error / unparseable.
  3) PARTICLES + TOPIC (0.25). Are particles consistent (no を with
     intransitive verbs, no double topic markers)? Does the sentence
     refer to the situation in the prompt? Score in 0.05 increments.
  4) REGISTER + NATURALNESS (0.25). Does the verb-final form match
     target_register? AND: if morph_diff.verb_form_match is true,
     morph_diff.particle_jaccard >= 0.5, AND morph_diff.negation_match
     is true, the user matches the reference's grammatical shape —
     score this check at >= 0.20 unless there is a concrete error you
     can cite. Otherwise judge on whether a native speaker would write
     this naturally.

Output JSON:
{
  "score": 0.0..1.0,
  "used_pattern": true|false,
  "feedback_text": "short, focused feedback in {locale_label}. Cite the
                    specific span of user_answer (in 「…」) for any
                    error you note. If the answer is correct, say so
                    briefly and stop.",
  "issues": ["pattern", "conjugation", "particle", "register",
             "topic", "naturalness"]   # zero or more, only those that
                                       # actually applied
}

Hard rules:
  - If detector_result.detected is false, used_pattern = false AND
    score <= 0.4.
  - Do NOT deduct for the user matching target_register.
  - Do NOT mark a sentence "unnatural" purely on stylistic preference
    when morph_diff shows it shares the reference's shape.
"""


def _default_pattern_use_llm(messages: list[dict]) -> dict:
    result = query_llm_json(messages, retries=2, temperature=0.0)
    if result.get("data") is None:
        raise RuntimeError(result.get("error") or "LLM returned no JSON")
    return result["data"]


def evaluate_pattern_use_submission(
        db_path: str, exercise_id: str, user_id: str, user_response: str,
        locale: str = "en",
        llm_fn: _Optional[_Callable[[list[dict]], dict]] = None) -> dict:
    """Evaluate an open-form pattern_use exercise.

    Reads the exercise + its target pattern from the DB, runs
    detect_pattern (deterministic), then asks an LLM rubric judge to
    score correctness + naturalness, grounded in the detector result.
    Persists an exercise_attempts row.

    Returns:
        {
          "score": float 0..1,
          "is_correct": bool,
          "used_pattern": bool,
          "feedback_text": str,
          "issues": list[str],
          "detector": dict,            # raw detect_pattern output
          "attempt_id": str,
        }
    """
    fn = llm_fn or _default_pattern_use_llm
    response = (user_response or "").strip()
    if not response:
        raise ValueError("user_response must not be empty")

    conn = _sqlite3.connect(db_path)
    conn.row_factory = _sqlite3.Row
    try:
        ex_row = conn.execute(
            "SELECT exercise_id, type, target_pattern_id, prompt, "
            "expected_json FROM exercises WHERE exercise_id = ?",
            (exercise_id,)
        ).fetchone()
        if not ex_row:
            raise ValueError(f"exercise {exercise_id} not found")
        if ex_row["type"] != "pattern_use":
            raise ValueError(
                f"evaluator only handles type=pattern_use, got "
                f"{ex_row['type']!r}"
            )

        expected = _json.loads(ex_row["expected_json"] or "{}")
        target_pattern_id = expected.get("target_pattern_id") \
            or ex_row["target_pattern_id"]
        target_register = expected.get("target_register") or "neutral"
        reference_answer = expected.get("reference_answer_jp", "")

        pattern_row = conn.execute(
            "SELECT name, meaning_locale, register FROM grammar_patterns "
            "WHERE pattern_id = ?", (target_pattern_id,)
        ).fetchone()
        pattern_name = pattern_row["name"] if pattern_row else "?"
        pattern_meaning = (pattern_row["meaning_locale"]
                           if pattern_row else "")
        # Pattern row's register is authoritative; the exercise's stored
        # value is fallback for legacy rows that pre-date the field.
        if pattern_row and pattern_row["register"]:
            target_register = pattern_row["register"]

        # Deterministic checks: pattern detection + morphological diff.
        # Both feed the rubric so it has concrete evidence to score
        # against instead of inventing naturalness criteria.
        detector = _detect_pattern(conn, response, target_pattern_id)
        morph = _morph_diff(reference_answer, response) if reference_answer \
            else None

        # Rubric LLM judge (temp 0).
        locale_label = _PATTERN_USE_LOCALE_LABELS.get(locale, "English")
        system_prompt = _PATTERN_USE_RUBRIC_PROMPT.replace(
            "{locale_label}", locale_label
        )
        user_payload = {
            "pattern_name": pattern_name,
            "pattern_meaning_locale": pattern_meaning,
            "target_register": target_register,
            "reference_answer": reference_answer,
            "user_answer": response,
            "detector_result": {
                "detected": bool(detector.get("detected")),
                "matched": detector.get("matched", []),
                "reason": detector.get("reason", ""),
            },
            "morph_diff": (
                {
                    "shared_verb_bases": morph["shared_verb_bases"],
                    "verb_form_match": morph["verb_form_match"],
                    "particle_jaccard": morph["particle_jaccard"],
                    "negation_match": morph["negation_match"],
                    "summary": morph["summary"],
                } if morph else None
            ),
        }

        try:
            raw = fn([
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": _json.dumps(user_payload, ensure_ascii=False)},
            ])
            score = float(raw.get("score", 0.0))
            score = max(0.0, min(1.0, score))
            used_pattern = bool(raw.get("used_pattern", False))
            feedback_text = (raw.get("feedback_text") or "").strip()
            issues = raw.get("issues") or []
            if not isinstance(issues, list):
                issues = []
        except (RuntimeError, ValueError, TypeError, KeyError):
            # LLM failed — fall back to detector-only score.
            used_pattern = bool(detector.get("detected"))
            score = 0.4 if used_pattern else 0.0
            feedback_text = (
                "Automatic grading unavailable; pattern usage "
                f"{'detected' if used_pattern else 'not detected'}."
            )
            issues = []

        # Enforce the rubric's hard rule defensively.
        if not detector.get("detected"):
            used_pattern = False
            score = min(score, 0.4)

        is_correct = score >= 0.7

        attempt_id = __import__("uuid").uuid4().hex
        feedback_blob = _json.dumps({
            "feedback_text": feedback_text,
            "issues": issues,
            "detector": detector,
            "morph_diff": morph,
            "target_register": target_register,
        }, ensure_ascii=False)
        conn.execute('''
            INSERT INTO exercise_attempts
            (attempt_id, exercise_id, user_id, response, score,
             is_correct, feedback_json, answered_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (attempt_id, exercise_id, user_id, response, score,
              1 if is_correct else 0, feedback_blob,
              __import__("datetime").datetime.now().isoformat()))
        conn.commit()

        return {
            "attempt_id": attempt_id,
            "score": score,
            "is_correct": is_correct,
            "used_pattern": used_pattern,
            "feedback_text": feedback_text,
            "issues": issues,
            "detector": detector,
            "morph_diff": morph,
            "target_register": target_register,
        }
    finally:
        conn.close()
