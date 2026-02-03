"""Routes package initialization"""
from routes.data import data_bp
from routes.analysis import analysis_bp
from routes.ask import ask_bp

__all__ = ['data_bp', 'analysis_bp', 'ask_bp']
