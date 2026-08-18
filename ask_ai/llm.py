"""
Ollama client for ask_ai.

Talks to the local Ollama daemon (OLLAMA_BASE_URL) via /api/generate. Follows
the same contract as document_verification/vision_client.py: never raises,
always returns {'success', 'text', 'error'}, and error strings name the exact
command that fixes the problem.
"""
import time

import requests

from ask_ai.config import OLLAMA_BASE_URL, ASK_AI_MODEL, OLLAMA_KEEP_ALIVE

# A cold model, or a cloud tag under load, briefly returns 429/503.
_RETRY_STATUSES = {429, 503}
_MAX_RETRIES = 3
_RETRY_BACKOFF_SEC = 4


def generate(prompt, *, model=None, temperature=0.0, num_predict=400, timeout=120):
    """One /api/generate call. Returns {'success': bool, 'text': str|None,
    'error': str|None}, plus 'unavailable' when the daemon or model is missing."""
    model = model or ASK_AI_MODEL
    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'keep_alive': OLLAMA_KEEP_ALIVE,
        'options': {'temperature': temperature, 'num_predict': num_predict},
    }

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(
                f'{OLLAMA_BASE_URL}/api/generate', json=payload, timeout=timeout,
            )
        except requests.exceptions.ConnectionError:
            return _fail(
                f'Ollama is not running at {OLLAMA_BASE_URL}. Start it, then run: '
                f'ollama pull {model}{_cloud_hint(model)}',
                unavailable=True,
            )
        except requests.exceptions.Timeout:
            return _fail(
                f'The model took longer than {timeout}s to respond '
                '(it may still be loading).',
                unavailable=True,
            )

        if resp.status_code == 200:
            return {'success': True, 'text': resp.json().get('response', ''), 'error': None}

        body = resp.text[:400]
        if resp.status_code == 404 or 'not found' in body.lower():
            return _fail(
                f'Model "{model}" is not available. '
                f'Run: ollama pull {model}{_cloud_hint(model)}',
                unavailable=True,
            )

        last_error = f'[{model}] Ollama HTTP {resp.status_code}: {body}'
        if resp.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
            time.sleep(_RETRY_BACKOFF_SEC * (attempt + 1))
            continue
        return _fail(last_error)

    return _fail(last_error)


def _fail(error, unavailable=False):
    return {'success': False, 'text': None, 'error': error, 'unavailable': unavailable}


def _cloud_hint(model):
    if model.endswith('-cloud') or model.endswith(':cloud'):
        return ' (cloud model — also run `ollama signin` once)'
    return ''


def summarize(question, columns, rows, *, timeout=60):
    """One-line natural-language phrasing of a result set. Returns the sentence,
    or None — the data is still worth returning when phrasing fails."""
    result = generate(
        "Answer the user's question in ONE short sentence using the data.\n"
        "Use the numbers exactly as given; do not recalculate or round them.\n"
        f"Question: {question}\n"
        f"Columns: {columns}\n"
        f"Rows: {rows[:20]}\n"
        "Answer:",
        temperature=0.2,
        num_predict=120,
        timeout=timeout,
    )
    return result['text'].strip() if result['success'] and result['text'] else None
