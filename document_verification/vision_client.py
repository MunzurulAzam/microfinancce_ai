"""Cloud vision transport and response parsers."""
import base64
import json as _json
import re
from typing import Optional
from core.cloud import generate


def encode_image(path):
    with open(path, 'rb') as image:
        return base64.b64encode(image.read()).decode('ascii')


def call_vision(image_b64, prompt, *, num_predict=1024, temperature=0.1, timeout=60, json_mode=False):
    return generate(prompt, task='vision', images=[image_b64], num_predict=num_predict,
                    temperature=temperature, timeout=timeout, json_mode=json_mode)


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
