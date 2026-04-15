"""
Agent Service facade — re-exports workflow functions from graphs/.

app.py imports from this module, so the public API is preserved.
"""
from graphs.review_graph import generate_daily_review_agent
