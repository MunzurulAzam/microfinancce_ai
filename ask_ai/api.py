

from flask import Blueprint, request, jsonify

from ask_ai.config import COUNTRY_CODES
from ask_ai.engine import route
from core.conversation import resolve, attach, ContextError

ask_ai_bp = Blueprint('ask_ai', __name__)


@ask_ai_bp.route('/ask-ai', methods=['POST'])
def ask_ai_endpoint():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('question', ''), str) or (data.get('country') is not None and not isinstance(data.get('country'), str)) or not isinstance(data.get('summary', True), bool):
        return jsonify({'success': False, 'error': 'Expected a JSON object with question string, optional country string and summary boolean.'}), 400
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

    try:
        resolved, effective, response = resolve(question, data.get('context'), data.get('country'))
    except ContextError as error:
        return jsonify({'success': False, 'code': 'invalid_context', 'error': str(error)}), 400
    country = None if effective == 'ALL' else effective
    result = response if response is not None else route(resolved, country=country, with_summary=with_summary)
    result = attach(result, resolved, effective)

    if result.get('success'):
        return jsonify(result), 200
    # An untranslatable question is the caller's problem — only real faults are 500.
    return jsonify(result), result.get('http_status', 400 if result.get('bad_request') else 500)
