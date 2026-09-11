

import hmac

from flask import Blueprint, current_app, jsonify, request

from ask_ai import db, dify_records
from ask_ai.config import (
    COUNTRY_CODES, DIFY_KB_API_KEY, DIFY_LIVE_KB_ID, DIFY_SCHEMA_KB_ID,
    DIFY_MAX_TOP_K,
)

dify_kb_bp = Blueprint('dify_kb', __name__)

_DEFAULT_TOP_K = 5

# Dify's own error codes — any other value shows in its UI as a generic failure.
_AUTH_FORMAT = 1001
_AUTH_FAILED = 1002
_NO_KNOWLEDGE = 2001


def _error(code, message, status):
    return jsonify({'error_code': code, 'error_msg': message}), status


def _reject_auth():
    """The error response for a bad caller, or None when it may proceed."""
    scheme, _, key = request.headers.get('Authorization', '').partition(' ')
    key = key.strip()
    if scheme.lower() != 'bearer' or not key:
        return _error(
            _AUTH_FORMAT,
            "Invalid Authorization header format. Expected 'Bearer <api-key>' format.",
            403,
        )
    # This endpoint is reachable from the public internet, so an unset server key
    # must mean "closed", never "open".
    if not DIFY_KB_API_KEY or not hmac.compare_digest(key, DIFY_KB_API_KEY):
        return _error(_AUTH_FAILED, 'Authorization failed.', 403)
    return None


def _country(metadata_condition):
    """Dify sends filters as {'conditions': [{'name': ['country'], 'value': 'UG'}]}."""
    for condition in (metadata_condition or {}).get('conditions') or []:
        names = condition.get('name') or []
        if isinstance(names, str):
            names = [names]
        if not any(str(n).lower() == 'country' for n in names):
            continue
        value = str(condition.get('value') or '').strip().upper()
        if value in COUNTRY_CODES:
            return value
    return None


def _top_k(value):
    try:
        return max(1, min(int(value), DIFY_MAX_TOP_K))
    except (TypeError, ValueError):
        return _DEFAULT_TOP_K


def _threshold(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dify_kb_bp.route('/dify/retrieval', methods=['POST'])
def dify_retrieval():
    """POST /api/dify/retrieval — Dify external knowledge API over the DW warehouse."""
    denied = _reject_auth()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    query = (data.get('query') or '').strip()
    if not query:
        return _error(_AUTH_FORMAT, 'Missing "query" in the request body.', 400)

    knowledge_id = (data.get('knowledge_id') or '').strip()
    if knowledge_id not in (DIFY_LIVE_KB_ID, DIFY_SCHEMA_KB_ID):
        return _error(
            _NO_KNOWLEDGE,
            f'The knowledge "{knowledge_id}" does not exist. '
            f'Use "{DIFY_LIVE_KB_ID}" or "{DIFY_SCHEMA_KB_ID}".',
            404,
        )

    setting = data.get('retrieval_setting') or {}
    top_k = _top_k(setting.get('top_k'))
    threshold = _threshold(setting.get('score_threshold'))

    try:
        if knowledge_id == DIFY_LIVE_KB_ID:
            records, error = dify_records.live_records(
                query, country=_country(data.get('metadata_condition')))
        else:
            records, error = dify_records.schema_records(query), None
    except db.QueryError as e:
        records, error = [], f'Warehouse unavailable: {e}'

    # Dify treats any non-200 as a hard failure, so a question we cannot answer
    # returns no context rather than breaking the caller's workflow.
    if error:
        current_app.logger.warning('[dify] %s: %s', knowledge_id, error)

    return jsonify({
        'records': [r for r in records if r['score'] >= threshold][:top_k]
    }), 200
