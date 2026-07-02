

from flask import Blueprint, request, jsonify

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

    # Optional country hint (UG/KY/ZM/TZ) — used by the member-analysis branch.
    country = (data.get('country') or '').strip().upper() or None
    if country in ('ALL', ''):
        country = None
    # Set summary=false for the fastest response (raw table only, no NL phrasing).
    with_summary = bool(data.get('summary', True))

    # Router picks: member analysis (score + decision + amount) OR text-to-SQL.
    result = route(question, country=country, with_summary=with_summary)
    return jsonify(result), (200 if result.get('success') else 500)
