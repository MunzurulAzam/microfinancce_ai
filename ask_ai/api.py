

from flask import Blueprint, request, jsonify

from ask_ai.config import COUNTRY_CODES
from ask_ai.engine import route

ask_ai_bp = Blueprint('ask_ai', __name__)


@ask_ai_bp.route('/ask-ai', methods=['POST'])
def ask_ai_endpoint():
    data = request.get_json(silent=True) or {}
    question = data.get('question', '').strip()

    if not question:
        return jsonify({
            'success': False,
            'error': 'Please provide a "question" field.',
            'example': {'question': 'Total loan portfolio across all countries?'},
        }), 400

    country = (data.get('country') or '').strip().upper() or None
    if country == 'ALL':
        country = None
    if country and country not in COUNTRY_CODES:
        return jsonify({
            'success': False,
            'error': f'Unknown country "{country}". Use one of: '
                     f'{", ".join(COUNTRY_CODES)}, or omit for all countries.',
        }), 400

    with_summary = bool(data.get('summary', True))

    result = route(question, country=country, with_summary=with_summary)

    if result.get('success'):
        return jsonify(result), 200
    # An untranslatable question is the caller's problem — only real faults are 500.
    return jsonify(result), (400 if result.get('bad_request') else 500)
