"""
AI Service facade — re-exports shared utilities from ai_core and
workflow functions from graphs/.

app.py imports from this module, so the public API is preserved.
"""
from graphs.chat_graph import chat_with_ai as chat_with_ai
from graphs.eval_graph import evaluate_submission as evaluate_submission
from graphs.eval_graph import get_detailed_feedback as get_detailed_feedback
