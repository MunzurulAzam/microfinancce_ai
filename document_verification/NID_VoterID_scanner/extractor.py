from typing import Optional

from document_verification.vision_client import call_vision, encode_image, extract_json_dict

def extract_id_data(image_path: str) -> dict:
    """Try the vision model first (any country, any language, stylized fonts, glare/blur)."""
    try:
        result = _extract_with_vision(image_path)
        if result['success'] and (result.get('name') or result.get('id_number')):
            return {**result, 'extractor': 'vision'}
        vision_error = result.get('error')
    except Exception as e:
        vision_error = f'{type(e).__name__}: {e}'
        print(f'[NIDScanner] Vision extraction crashed ({vision_error}).')

    return _error_result(vision_error or 'Cloud vision unavailable. Please retry.')


_VISION_PROMPT = (
    "You are reading a government-issued identity card (national ID or voter ID) "
    "from ANY country. Extract the fields below and respond with ONLY a single "
    "valid JSON object — no markdown, no commentary:\n"
    '{"name": "<full name: surname + given names joined with a space>",'
    '"id_number": "<the national ID / NIN / NRC / voter / registration number>",'
    '"country": "<issuing country>",'
    '"id_type": "<document type exactly as printed>",'
    '"dob": "<date of birth as printed, or null>",'
    '"raw_text_sample": "<at most 2 short lines, max 80 characters total>",'
    '"confidence": "<high|medium|low>"}\n'
    "Rules:\n"
    "- Copy every character EXACTLY as printed. Do not guess or normalise.\n"
    "- Read the COMPLETE id_number including ALL letters, digits, hyphens and "
    "slashes (e.g. '19851210-14121-00002-16' or 'CM37173109PE1D'). Never stop "
    "at a hyphen or drop a trailing letter.\n"
    "- Field labels may be in any language (e.g. Swahili JINA = name, JINA LA "
    "MWISHO = surname, French NOM/PRENOM). Read the VALUES, not the labels.\n"
    "- The id_number is the personal identity/registration number, NOT the card "
    "serial number.\n"
    "- Use null for any field you genuinely cannot read."
)


def _extract_with_vision(image_path: str) -> dict:
    image_b64 = encode_image(image_path)
    resp = call_vision(image_b64, _VISION_PROMPT, num_predict=1024, temperature=0.05, json_mode=True)
    if not resp['success']:
        return {
            **_error_result(resp['error']),
            'overloaded': resp.get('overloaded', False),
            'unavailable': resp.get('unavailable', False),
        }

    parsed = extract_json_dict(resp['text'] or '')
    if parsed is None:
        return _error_result(
            f'Vision model did not return JSON. Raw: {(resp["text"] or "")[:200]}'
        )

    return {
        'success': True,
        'name': _clean(parsed.get('name')),
        'id_number': _clean(parsed.get('id_number')),
        'country_hint': _clean(parsed.get('country')) or '',
        'id_type_hint': _clean(parsed.get('id_type')),
        'raw_text_sample': _clean(parsed.get('raw_text_sample')),
        'confidence': (parsed.get('confidence') or 'unknown').lower(),
        'error': None,
    }


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _error_result(msg: str) -> dict:
    return {
        'success': False,
        'error': msg,
        'name': None,
        'id_number': None,
        'country_hint': None,
        'id_type_hint': None,
        'raw_text_sample': None,
        'confidence': 'unknown',
    }
