"""Shared vision-LLM client for the passport/NID classifier and the NID/VoterID scanner."""
import base64
import json as _json
import re
import time
from typing import Optional

import requests
from config import Config

# Free Ollama Cloud briefly returns 503/429 under load — retry with a short backoff.
_RETRY_STATUSES = {429, 503}
_MAX_RETRIES = 3
_RETRY_BACKOFF_SEC = 4


def encode_image(path: str) -> str:
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def _vision_models() -> list:
    """OLLAMA_VISION_MODEL first, then the comma-separated OLLAMA_VISION_FALLBACKS."""
    models = [Config.OLLAMA_VISION_MODEL]
    fallbacks = getattr(Config, 'OLLAMA_VISION_FALLBACKS', '') or ''
    for m in fallbacks.split(','):
        m = m.strip()
        if m and m not in models:
            models.append(m)
    return models


def call_vision(
    image_b64: str,
    prompt: str,
    *,
    num_predict: int = 256,
    temperature: float = 0.1,
    timeout: int = 120,
) -> dict:
    """Vision call against {OLLAMA_BASE_URL}/api/chat."""
    last_error = None
    overloaded = False
    any_reachable = False
    for model in _vision_models():
        result = _call_one_model(model, image_b64, prompt, num_predict, temperature, timeout)
        if result['success']:
            return result
        last_error = result['error']
        overloaded = overloaded or result.get('overloaded', False)
        if result.get('fatal'):
            return {'success': False, 'text': None, 'error': last_error,
                    'overloaded': False, 'unavailable': True}
        if not result.get('not_found'):
            any_reachable = True
    return {'success': False, 'text': None, 'error': last_error,
            'overloaded': overloaded, 'unavailable': not any_reachable}


def _call_one_model(model, image_b64, prompt, num_predict, temperature, timeout) -> dict:
    payload = {
        'model': model,
        'messages': [
            {'role': 'user', 'content': prompt, 'images': [image_b64]},
        ],
        'stream': False,
        'options': {'temperature': temperature, 'num_predict': num_predict},
    }

    last_status_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(
                f'{Config.OLLAMA_BASE_URL}/api/chat',
                json=payload,
                timeout=timeout,
            )
        except requests.exceptions.ConnectionError:
            return {
                'success': False, 'text': None, 'fatal': True,
                'error': (
                    'Ollama is not running. Start Ollama and ensure the vision '
                    f'model is available. Run: ollama pull {model}{_cloud_hint(model)}'
                ),
            }
        except requests.exceptions.Timeout:
            return {
                'success': False, 'text': None, 'fatal': True,
                'error': 'The vision model took too long to respond (it may still be loading).',
            }

        if resp.status_code == 200:
            data = resp.json()
            text = (data.get('message') or {}).get('content', '')
            return {'success': True, 'text': text, 'error': None}

        body = resp.text[:400]
        if 'not found' in body.lower() or resp.status_code == 404:
            return {
                'success': False, 'text': None, 'not_found': True,
                'error': (
                    f'Vision model "{model}" is not available. '
                    f'Run: ollama pull {model}{_cloud_hint(model)}'
                ),
            }

        last_status_error = f'[{model}] Ollama HTTP {resp.status_code}: {body}'
        if resp.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
            time.sleep(_RETRY_BACKOFF_SEC * (attempt + 1))
            continue
        overloaded = resp.status_code in _RETRY_STATUSES
        return {'success': False, 'text': None,
                'error': last_status_error, 'overloaded': overloaded}

    return {'success': False, 'text': None, 'error': last_status_error}


def _cloud_hint(model: str) -> str:
    if model.endswith('-cloud') or model.endswith(':cloud'):
        return ' (cloud model — also run `ollama signin` once)'
    return ''


def parse_possibly_truncated_json(candidate: str) -> Optional[dict]:
    """Parse a JSON object that may be cut off mid-generation (no closing brace, or an unterminated string)."""
    e = candidate.rfind('}')
    if e != -1:
        try:
            return _json.loads(candidate[:e + 1])
        except _json.JSONDecodeError:
            pass

    for cut in _truncation_candidates(candidate):
        repaired = cut
        if len(re.findall(r'(?<!\\)"', repaired)) % 2 == 1:
            repaired += '"'
        open_braces = repaired.count('{') - repaired.count('}')
        if open_braces > 0:
            repaired += '}' * open_braces
        try:
            return _json.loads(repaired)
        except _json.JSONDecodeError:
            continue
    return None


def _truncation_candidates(candidate: str):
    yield candidate
    idx = candidate.rfind(',')
    while idx != -1:
        yield candidate[:idx]
        idx = candidate.rfind(',', 0, idx)


def extract_json_dict(raw: str) -> Optional[dict]:
    """Strip markdown fences, locate the first '{', and parse (with repair)."""
    cleaned = re.sub(r'```(?:json)?\s*', '', raw).strip().rstrip('`')
    s = cleaned.find('{')
    if s == -1:
        return None
    return parse_possibly_truncated_json(cleaned[s:])
