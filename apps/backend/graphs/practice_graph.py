"""
Practice graph — generates a single typed exercise for a user, range,
and (for now) a single strategy: pattern_use.

Layout (matching chat_graph.py / eval_graph.py style):

    gather → plan → fetch_target → execute → verify → persist
                                              ↑ ↓
                                          fallback (after retry budget)

Design principles:
  - Planner and verifier are deterministic about *what* — agents only
    pick from candidates the planner was given. target_pattern_id and
    strategy are constrained by Pydantic structured output.
  - Executor produces the *surface* — at moderate temperature.
  - Verifier calls deterministic tools (detect_pattern); on failure it
    returns to the executor with the failure reason in context. Bounded
    retries (default 2). After exhaustion, the fallback node serves a
    canonical example as a translation task so the user never gets
    nothing.

Public API:
  - generate_exercise(db_path, user_id, range_id, locale, llm_fn=None)
"""
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Callable, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field, ValidationError

from ai_core import query_llm_json
from tools.detect_pattern import detect_pattern
from tools.lookup import (
    learner_weak_points,
    lookup_pattern,
    search_examples,
    srs_due,
)

MAX_RETRIES = 2

LOCALE_LABELS = {
    "en": "English",
    "zh-tw": "Traditional Chinese",
    "zh-TW": "Traditional Chinese",
    "ja": "Japanese",
}

# Localized fallback templates. Each takes (pattern_name, translation)
# via str.format. The pattern name is the only Japanese token in
# non-Japanese locales.
_FALLBACK_TEMPLATES = {
    "en":    ("Translate this sentence into Japanese using the pattern "
              "「{pattern_name}」.\n\n{translation}"),
    "zh-tw": ("請使用「{pattern_name}」這個句型，將下面的句子翻譯成日文。"
              "\n\n{translation}"),
    "zh-TW": ("請使用「{pattern_name}」這個句型，將下面的句子翻譯成日文。"
              "\n\n{translation}"),
    "ja":    ("「{pattern_name}」を使って、次の文を日本語に訳してください。"
              "\n\n{translation}"),
}


# ---------------------------------------------------------------------------
# Structured outputs
# ---------------------------------------------------------------------------

class PracticePlan(BaseModel):
    """What the planner chooses. target_pattern_id is constrained by the
    candidate set passed in the prompt; the validator double-checks it."""
    target_pattern_id: str = Field(..., min_length=1)
    strategy: Literal["pattern_use"] = "pattern_use"
    difficulty: int = Field(3, ge=1, le=5)
    variant_hint: str = Field("", max_length=200)


class ExerciseDraft(BaseModel):
    """Executor output — both fields required."""
    prompt_locale_text: str = Field(..., min_length=1)
    reference_answer_jp: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

LLMFn = Callable[[list[dict], float], dict]


class PracticeState(TypedDict, total=False):
    # Inputs
    user_id: str
    range_id: str
    locale: str
    db_path: str
    llm_fn: Optional[LLMFn]   # injected for tests; None → use ai_core

    # Intermediate
    weak_points: list[str]
    candidates: list[dict]
    plan: Optional[dict]
    pattern: Optional[dict]
    examples: list[dict]
    draft: Optional[dict]
    verifier: Optional[dict]
    retries: int
    used_fallback: bool
    verifier_feedback: list[str]

    # Output
    error: Optional[str]
    exercise: Optional[dict]


# ---------------------------------------------------------------------------
# LLM adapter
# ---------------------------------------------------------------------------

def _default_llm(messages: list[dict], temperature: float) -> dict:
    """Adapter to query_llm_json with a uniform call signature."""
    result = query_llm_json(messages, retries=2, temperature=temperature)
    if result.get("data") is None:
        raise RuntimeError(result.get("error") or "LLM returned no JSON")
    return result["data"]


def _call_llm(state: PracticeState, messages: list[dict],
              temperature: float) -> dict:
    fn = state.get("llm_fn") or _default_llm
    return fn(messages, temperature)


def _open_conn(state: PracticeState) -> sqlite3.Connection:
    conn = sqlite3.connect(state["db_path"])
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def gather(state: PracticeState) -> dict:
    """Pull SRS-due patterns and learner weak points from the catalog."""
    conn = _open_conn(state)
    try:
        candidates = srs_due(conn, state["user_id"], state["range_id"])
        weak = learner_weak_points(conn, state["user_id"])
    finally:
        conn.close()

    if not candidates:
        return {
            "candidates": [],
            "weak_points": weak,
            "error": "no_published_patterns_in_range",
        }
    return {
        "candidates": candidates,
        "weak_points": weak,
        "retries": 0,
        "verifier_feedback": [],
        "used_fallback": False,
    }


_PLANNER_PROMPT = """You are a Japanese practice planner.

You are given:
  - candidates: a list of grammar patterns due for practice. Each has a
    `pattern_id`, `name`, and `jlpt`.
  - learner_weak_points: tags from the learner's profile (may be empty).

Pick exactly one pattern from candidates and decide:
  - target_pattern_id: MUST be one of the given pattern_ids verbatim.
    Do not invent ids.
  - strategy: always "pattern_use" for this version.
  - difficulty: 1..5. Pick lower (1-2) for low-JLPT or weak-point matches,
    higher (4-5) for strong patterns / high JLPT.
  - variant_hint: a short, concrete situation the executor can dramatize
    (e.g. "expressing regret about food", "weather + condition"). Keep
    it under 20 words. Do NOT include Japanese in this field.

Return strict JSON:
{
  "target_pattern_id": "...",
  "strategy": "pattern_use",
  "difficulty": 1..5,
  "variant_hint": "..."
}
"""


def plan(state: PracticeState) -> dict:
    candidates = state["candidates"]
    weak = state.get("weak_points", [])
    user_msg = json.dumps({
        "candidates": [
            {"pattern_id": c["pattern_id"], "name": c["name"],
             "jlpt": c.get("jlpt")}
            for c in candidates
        ],
        "learner_weak_points": weak,
    }, ensure_ascii=False)

    try:
        raw = _call_llm(state, [
            {"role": "system", "content": _PLANNER_PROMPT},
            {"role": "user", "content": user_msg},
        ], temperature=0.0)
        plan_obj = PracticePlan.model_validate(raw)
    except (ValidationError, RuntimeError, ValueError) as e:
        return {"error": f"plan_failed: {e}"}

    valid_ids = {c["pattern_id"] for c in candidates}
    if plan_obj.target_pattern_id not in valid_ids:
        return {"error": "plan_invented_pattern_id"}

    return {"plan": plan_obj.model_dump()}


def fetch_target(state: PracticeState) -> dict:
    pid = state["plan"]["target_pattern_id"]
    conn = _open_conn(state)
    try:
        pattern = lookup_pattern(conn, pid)
        examples = search_examples(conn, pid, k=3)
    finally:
        conn.close()

    if not pattern:
        return {"error": "target_pattern_missing"}
    return {"pattern": pattern, "examples": examples}


def _executor_prompt(locale: str) -> str:
    locale_label = LOCALE_LABELS.get(locale, "English")
    is_japanese_locale = locale in ("ja",)

    if is_japanese_locale:
        prompt_rule = (
            "the prompt the learner sees, written entirely in Japanese."
        )
    else:
        prompt_rule = (
            f"the prompt the learner sees, in {locale_label}. The target "
            f"pattern name itself MUST appear (e.g. 「〜てしまう」), but no "
            f"other Japanese — vocabulary and the situation are described "
            f"in {locale_label}. Do not include a sample answer."
        )

    return f"""You are a Japanese exercise writer.

Construct ONE pattern_use exercise. The learner will write a Japanese
sentence that uses the target pattern.

You will receive:
  - pattern: name, formation_rule, meaning_locale, jlpt, examples.
  - difficulty: 1..5 (use simpler vocab and shorter sentences for low
    difficulty).
  - variant_hint: a short situational nudge (English only — for your
    eyes; do not echo it verbatim).
  - feedback (optional): why a previous attempt failed verification.
    Read it and avoid the same mistake.

Output JSON exactly:
{{
  "prompt_locale_text": "{prompt_rule}",
  "reference_answer_jp": "a single natural Japanese sentence that uses "
                          "the pattern correctly."
}}

Hard rules:
  - reference_answer_jp MUST contain a conjugation of the target pattern.
  - reference_answer_jp MUST be plain Japanese — no romaji, no English.
  - Do NOT echo the pattern name into prompt_locale_text more than once.
"""


def execute(state: PracticeState) -> dict:
    pattern = state["pattern"]
    plan_obj = state["plan"]
    examples = state.get("examples", [])
    feedback = state.get("verifier_feedback", [])

    user_payload = {
        "pattern": {
            "name": pattern["name"],
            "formation_rule": pattern.get("formation_rule"),
            "meaning_locale": pattern.get("meaning_locale"),
            "jlpt": pattern.get("jlpt"),
            "examples": [
                {"sentence": ex["sentence"],
                 "translation": ex.get("translation")}
                for ex in examples
            ],
        },
        "difficulty": plan_obj["difficulty"],
        "variant_hint": plan_obj["variant_hint"],
    }
    if feedback:
        user_payload["feedback"] = feedback[-2:]  # last two reasons

    try:
        raw = _call_llm(state, [
            {"role": "system",
             "content": _executor_prompt(state.get("locale", "en"))},
            {"role": "user",
             "content": json.dumps(user_payload, ensure_ascii=False)},
        ], temperature=0.7)
        draft = ExerciseDraft.model_validate(raw)
    except (ValidationError, RuntimeError, ValueError) as e:
        return {
            "verifier_feedback": feedback + [f"executor_error: {e}"],
            "retries": state.get("retries", 0) + 1,
        }

    return {"draft": draft.model_dump()}


def verify(state: PracticeState) -> dict:
    draft = state.get("draft")
    if not draft:
        # Executor failed; verify becomes a no-op signalling retry.
        return {"verifier": {"detected": False, "reason": "no_draft"}}

    pid = state["plan"]["target_pattern_id"]
    conn = _open_conn(state)
    try:
        result = detect_pattern(conn, draft["reference_answer_jp"], pid)
    finally:
        conn.close()

    if result["detected"]:
        return {"verifier": result}

    feedback = state.get("verifier_feedback", []) + [
        f"reference_answer_jp did not contain pattern: {result['reason']}"
    ]
    return {
        "verifier": result,
        "verifier_feedback": feedback,
        "retries": state.get("retries", 0) + 1,
    }


def fallback(state: PracticeState) -> dict:
    """Serve a canonical example as a translation task.

    Triggered when the executor + verifier loop has used its retry
    budget. Always succeeds as long as the pattern has any example;
    if not, propagates an error.
    """
    examples = state.get("examples", [])
    pattern = state["pattern"]
    if not examples:
        return {"error": "no_examples_for_fallback"}

    canonical = next(
        (e for e in examples if e.get("is_canonical")),
        examples[0],
    )
    locale = state.get("locale", "en")
    template = _FALLBACK_TEMPLATES.get(locale, _FALLBACK_TEMPLATES["en"])
    translation = (canonical.get("translation") or "").strip()
    if not translation:
        # No translation available — use the canonical sentence itself
        # as the prompt source so the user still has something concrete.
        translation = canonical["sentence"]

    prompt = template.format(
        pattern_name=pattern["name"],
        translation=translation,
    )
    return {
        "draft": {
            "prompt_locale_text": prompt,
            "reference_answer_jp": canonical["sentence"],
        },
        "used_fallback": True,
    }


def persist(state: PracticeState) -> dict:
    if state.get("error"):
        return {}
    draft = state["draft"]
    plan_obj = state["plan"]
    pattern = state["pattern"]

    exercise_id = str(uuid.uuid4())
    seed = str(uuid.uuid4())[:8]
    expected = {
        "reference_answer_jp": draft["reference_answer_jp"],
        "target_pattern_id": pattern["pattern_id"],
        "target_pattern_name": pattern["name"],
    }
    rubric = {
        "must_use_pattern": True,
        "max_score": 1.0,
    }
    source = "fallback_canonical" if state.get("used_fallback") else "graph"
    now = datetime.now().isoformat()

    conn = _open_conn(state)
    try:
        conn.execute('''
            INSERT INTO exercises
            (exercise_id, user_id, range_id, type, target_pattern_id,
             difficulty, prompt, expected_json, rubric_json, seed,
             source, created_timestamp)
            VALUES (?, ?, ?, 'pattern_use', ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (exercise_id, state["user_id"], state["range_id"],
              pattern["pattern_id"], plan_obj["difficulty"],
              draft["prompt_locale_text"], json.dumps(expected),
              json.dumps(rubric), seed, source, now))
        conn.commit()
    finally:
        conn.close()

    return {
        "exercise": {
            "exercise_id": exercise_id,
            "type": "pattern_use",
            "target_pattern_id": pattern["pattern_id"],
            "target_pattern_name": pattern["name"],
            "difficulty": plan_obj["difficulty"],
            "prompt": draft["prompt_locale_text"],
            "source": source,
            "retries": state.get("retries", 0),
        }
    }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_after_gather(state: PracticeState) -> str:
    return END if state.get("error") else "plan"


def route_after_plan(state: PracticeState) -> str:
    return END if state.get("error") else "fetch_target"


def route_after_fetch(state: PracticeState) -> str:
    return END if state.get("error") else "execute"


def route_after_verify(state: PracticeState) -> str:
    verifier = state.get("verifier") or {}
    if verifier.get("detected"):
        return "persist"
    if state.get("retries", 0) >= MAX_RETRIES:
        return "fallback"
    return "execute"


# ---------------------------------------------------------------------------
# Compiled graph
# ---------------------------------------------------------------------------

def _build_practice_graph():
    graph = StateGraph(PracticeState)
    graph.add_node("gather", gather)
    graph.add_node("plan", plan)
    graph.add_node("fetch_target", fetch_target)
    graph.add_node("execute", execute)
    graph.add_node("verify", verify)
    graph.add_node("fallback", fallback)
    graph.add_node("persist", persist)

    graph.set_entry_point("gather")
    graph.add_conditional_edges("gather", route_after_gather,
                                {END: END, "plan": "plan"})
    graph.add_conditional_edges("plan", route_after_plan,
                                {END: END, "fetch_target": "fetch_target"})
    graph.add_conditional_edges("fetch_target", route_after_fetch,
                                {END: END, "execute": "execute"})
    graph.add_edge("execute", "verify")
    graph.add_conditional_edges("verify", route_after_verify, {
        "persist": "persist",
        "execute": "execute",
        "fallback": "fallback",
    })
    graph.add_edge("fallback", "persist")
    graph.add_edge("persist", END)

    return graph.compile()


_practice_graph = _build_practice_graph()


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

def generate_exercise(db_path: str, user_id: str, range_id: str,
                      locale: str = "en",
                      llm_fn: Optional[LLMFn] = None) -> dict:
    """Run the practice graph for one exercise.

    Returns a dict shaped like:
      {"exercise": {...}}                    — happy path
      {"error": "<reason>", "stage": ...}    — graph short-circuited
    """
    initial: PracticeState = {
        "user_id": user_id,
        "range_id": range_id,
        "locale": locale,
        "db_path": db_path,
        "llm_fn": llm_fn,
    }
    final = _practice_graph.invoke(initial)
    if final.get("exercise"):
        return {"exercise": final["exercise"]}
    return {
        "error": final.get("error") or "unknown_error",
        "candidates": len(final.get("candidates") or []),
        "retries": final.get("retries", 0),
    }
