"""
Evaluation feature — applicant evaluation from an uploaded bank statement PDF
(POST /api/evaluate).
"""
from evaluation.routes import evaluation_bp

__all__ = ['evaluation_bp']
