"""
NID/VoterID text extraction.
Primary:  Ollama vision model (Config.OLLAMA_VISION_MODEL) — set to a `-cloud`
          tag (e.g. qwen3-vl:235b-cloud) for best-in-class, any-country/any-
          language document understanding via the local daemon.
Fallback: EasyOCR — local, no-network OCR used only when the vision call fails
          (e.g. offline, or the model isn't available).
"""
import re
import threading
from typing import List, Optional

from document_verification.NID_VoterID_scanner.country_patterns import COUNTRY_REGISTRY
from document_verification.vision_client import call_vision, encode_image, extract_json_dict

# ── EasyOCR reader (cached at module level — loaded once per server start) ────
_reader = None
_reader_lock = threading.Lock()


def _get_reader():
    global _reader
    if _reader is None:
        with _reader_lock:
            if _reader is None:
                import os
                import certifi
                # macOS Python framework ships without a CA bundle, so EasyOCR's
                # one-time model download fails with SSL: CERTIFICATE_VERIFY_FAILED.
                # Point SSL verification at certifi's bundle so the download works.
                os.environ.setdefault('SSL_CERT_FILE', certifi.where())
                os.environ.setdefault('SSL_CERT_DIR', os.path.dirname(certifi.where()))
                import easyocr
                _reader = easyocr.Reader(['en'], verbose=False)
    return _reader


# ── Field label vocabularies ──────────────────────────────────────────────────

_SURNAME_LABELS = frozenset({
    'SURNAME', 'SURNAMES', 'LAST NAME', 'LAST NAMES', 'FAMILY NAME',
})

_GIVEN_NAME_LABELS = frozenset({
    'GIVEN NAME', 'GIVEN NAMES', 'FIRST NAME', 'FIRST NAMES',
    'FORENAME', 'FORENAMES', 'OTHER NAMES', 'CHRISTIAN NAME',
})

_FULL_NAME_LABELS = frozenset({
    'FULL NAME', 'FULL NAMES', 'NAME', 'NAMES',
    "HOLDER'S NAME", 'HOLDERS NAME', 'CARD HOLDER',
})

_ID_LABELS = frozenset({
    'NIN', 'NID', 'NATIONAL ID', 'ID NO', 'ID NUMBER', 'ID NO.',
    'CARD NO', 'CARD NO.', 'CARD NUMBER', 'NRC NO', 'NRC NO.',
    'NIDA NO', 'VOTER NO', 'VOTER NUMBER', 'VOTER ID NO',
    'NATIONAL IDENTIFICATION NUMBER', 'NATIONAL REGISTRATION NUMBER',
    'IDENTIFICATION NUMBER',
})

_ID_TYPE_PHRASES = frozenset({
    'NATIONAL ID CARD', 'NATIONAL IDENTITY CARD', 'NATIONAL IDENTIFICATION',
    'VOTER ID CARD', 'VOTER ID', 'VOTER REGISTRATION CARD', 'VOTER CARD',
    'NATIONAL REGISTRATION CARD', 'NIN CARD', 'NID CARD',
})

# All tokens that should NOT be mistaken for a person's name value
_ALL_LABELS: frozenset = (
    _SURNAME_LABELS | _GIVEN_NAME_LABELS | _FULL_NAME_LABELS
    | _ID_LABELS | _ID_TYPE_PHRASES | frozenset({
        'NATIONALITY', 'SEX', 'GENDER', 'DATE OF BIRTH', 'DOB', 'BIRTH DATE',
        'DATE OF EXPIRY', 'EXPIRY DATE', 'EXPIRY', 'ISSUE DATE', 'DATE OF ISSUE',
        'PLACE OF BIRTH', 'HEIGHT', 'OCCUPATION', 'PROFESSION', 'DISTRICT',
        'SIGNATURE', "HOLDER'S SIGNATURE", 'HOLDERS SIGNATURE',
        'NATIONAL IDENTIFICATION AND REGISTRATION AUTHORITY',
        'REPUBLIC OF UGANDA', 'REPUBLIC OF KENYA', 'REPUBLIC OF ZAMBIA',
        'PEOPLES REPUBLIC OF BANGLADESH', 'UNITED REPUBLIC OF TANZANIA',
        'UGA', 'KEN', 'TZA', 'ZMB', 'BGD', 'RWA', 'ETH', 'GHA', 'NGA',
        'M', 'F', 'MALE', 'FEMALE',
    })
)

_DATE_RE = re.compile(r'^\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}$')
_PURE_NUM_RE = re.compile(r'^\d+$')


# ── Main entry point ──────────────────────────────────────────────────────────

def extract_id_data(image_path: str) -> dict:
    """
    Try the vision model first (any country, any language, stylized fonts,
    glare/blur). Fall back to local EasyOCR if the vision call fails.
    Returns the dict structure expected by service.py.
    """
    vision_unavailable = False
    try:
        result = _extract_with_vision(image_path)
        if result['success'] and (result.get('name') or result.get('id_number')):
            return {**result, 'extractor': 'vision'}
        vision_error = result.get('error')
        vision_unavailable = result.get('unavailable', False)
    except Exception as e:
        vision_error = f'{type(e).__name__}: {e}'
        vision_unavailable = True
        print(f'[NIDScanner] Vision extraction crashed ({vision_error}).')

    # EasyOCR is used ONLY as a genuine offline fallback (Ollama down / model not
    # pulled). For any other vision hiccup — cloud overload (503), an empty or
    # non-JSON reply — we do NOT return EasyOCR's guess, because a confidently
    # WRONG ID number is worse than asking the user to scan again.
    if not vision_unavailable:
        return _error_result(
            'Could not read the card reliably (the cloud vision model is busy '
            'or returned an unclear result). Please wait a few seconds and scan again.'
        )

    try:
        result = _extract_with_easyocr(image_path)
        return {**result, 'extractor': 'easyocr'}
    except ImportError:
        return _error_result(
            vision_error or 'Vision model unavailable and EasyOCR is not installed.'
        )
    except Exception as e:
        return _error_result(
            f'Both vision and EasyOCR extraction failed. EasyOCR: {type(e).__name__}: {e}'
        )


# ── Vision-model extraction (primary) ──────────────────────────────────────────

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
    resp = call_vision(image_b64, _VISION_PROMPT, num_predict=512, temperature=0.05)
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


# ── EasyOCR extraction ────────────────────────────────────────────────────────

def _extract_with_easyocr(image_path: str) -> dict:
    reader = _get_reader()
    raw = reader.readtext(image_path, detail=1)

    if not raw:
        return _error_result('EasyOCR could not detect any text in the image.')

    # Sort blocks top-to-bottom by the minimum Y coordinate of their bounding box
    blocks = sorted(raw, key=lambda r: min(pt[1] for pt in r[0]))

    # Keep only high-enough confidence blocks
    texts: List[str] = [b[1].strip() for b in blocks if b[2] > 0.3 and b[1].strip()]
    full_text = '\n'.join(texts)

    name         = _parse_name(texts)
    id_number    = _parse_id_number(texts, full_text)
    id_type_hint = _parse_id_type_hint(texts)

    confidence = (
        'high'   if (name and id_number) else
        'medium' if (name or id_number)  else
        'low'
    )

    return {
        'success': True,
        'name': name,
        'id_number': id_number,
        'country_hint': full_text[:400],
        'id_type_hint': id_type_hint,
        'raw_text_sample': '\n'.join(texts[:15]),
        'confidence': confidence,
        'error': None,
    }


def _parse_name(texts: List[str]) -> Optional[str]:
    """
    Three strategies tried in order:

    A) SURNAME label found → next real value block is surname;
       GIVEN NAME label found → next real value block is given names.
       Return "SURNAME GIVEN_NAMES".

    B) FULL NAME / NAME label found → next real value block is the full name.

    C) Inline colon on same block: "SURNAME: JJENGO" → split on ':'.
    """
    surname = None
    given_names = None
    full_name = None

    for i, text in enumerate(texts):
        t = text.strip()
        tu = t.upper()

        # Strategy C — inline colon (e.g. "SURNAME: JJENGO")
        if ':' in t:
            label_part, _, val_part = t.partition(':')
            lu = label_part.strip().upper()
            v = val_part.strip()
            if v and lu in _SURNAME_LABELS and surname is None:
                surname = v
                continue
            if v and lu in _GIVEN_NAME_LABELS and given_names is None:
                given_names = v
                continue
            if v and lu in _FULL_NAME_LABELS and full_name is None:
                full_name = v
                continue

        # Strategy A
        if tu in _SURNAME_LABELS and surname is None:
            surname = _next_value(texts, i)
        elif tu in _GIVEN_NAME_LABELS and given_names is None:
            given_names = _next_value(texts, i)

        # Strategy B
        elif tu in _FULL_NAME_LABELS and full_name is None:
            full_name = _next_value(texts, i)

    if surname and given_names:
        return f'{surname} {given_names}'
    return full_name or surname or given_names or None


def _next_value(texts: List[str], label_idx: int) -> Optional[str]:
    """
    Return the first text block after `label_idx` that looks like a real value:
    - Not in _ALL_LABELS
    - At least 2 characters
    - Not purely numeric
    - Not a date string
    - Contains at least one letter
    """
    for j in range(label_idx + 1, min(label_idx + 7, len(texts))):
        c = texts[j].strip()
        cu = c.upper()
        if (
            c
            and len(c) >= 2
            and cu not in _ALL_LABELS
            and not _DATE_RE.match(c)
            and not _PURE_NUM_RE.match(c)
            and any(ch.isalpha() for ch in c)
        ):
            return c
    return None


def _parse_id_number(texts: List[str], full_text: str) -> Optional[str]:
    """
    Step 1: if a NIN/NID/etc label is found, search the next few blocks.
    Step 2: global regex search across the full text (catches inline patterns).
    """
    for i, text in enumerate(texts):
        if text.strip().upper() in _ID_LABELS:
            for j in range(i + 1, min(i + 6, len(texts))):
                candidate = texts[j].strip()
                for country in COUNTRY_REGISTRY:
                    m = country['pattern'].search(candidate)
                    if m:
                        return m.group()

    for country in COUNTRY_REGISTRY:
        m = country['pattern'].search(full_text)
        if m:
            return m.group()

    return None


def _parse_id_type_hint(texts: List[str]) -> Optional[str]:
    for text in texts:
        if text.strip().upper() in _ID_TYPE_PHRASES:
            return text.strip()
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

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
