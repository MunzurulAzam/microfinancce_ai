"""
Assistant feature — the rule-based conversational endpoint (POST /api/ask) that
orchestrates portfolio + credit-scoring features.
"""
from assistant.routes import ask_bp

__all__ = ['ask_bp']
