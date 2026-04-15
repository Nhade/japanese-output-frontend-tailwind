"""
AI Service facade — re-exports shared utilities from ai_core and
workflow functions from graphs/.

app.py imports from this module, so the public API is preserved.
"""
from ai_core import (
    ErrorType,
    calculate_score,
    query_llm,
    query_llm_json,
    _parse_json_safe,
    check_safety,
    build_learner_context,
    SAFETY_POLICY,
)
from graphs.eval_graph import evaluate_submission, get_detailed_feedback
from graphs.chat_graph import chat_with_ai
