import os
import base64
import tempfile
import requests
import numpy as np
from PIL import Image, ImageEnhance
from config import Config

# ── Two focused prompts (simple YES/NO — far more reliable than 3-way) ───────

_PROMPT_STEP1 = (
    "Look at this image carefully. Is there a government-issued identity document "
    "(such as a national ID card, voter ID, or passport) with a person's photograph "
    "visible in this image? "
    "Answer with ONLY the word: YES or NO"
)

_PROMPT_STEP2 = (
    "Look at this document carefully. Is this document a PASSPORT "
    "(a booklet or data page with machine-readable zone containing <<< symbols) "
    "or a NATIONAL ID CARD (a card-sized document with a person's photo and an ID number)? "
    "Answer with ONLY: PASSPORT or NID"
)


def preprocess_image(input_path: str) -> str:
    """
    Preprocess the image before sending to the vision model:
    1. Auto-crop dark borders so the document fills the frame
    2. Boost contrast + sharpness so text/photo/emblem is clearer
    3. Resize to max 1024px on the longest side
    Returns path to a new temp JPEG. Caller is responsible for deleting it.
    """
    img = Image.open(input_path).convert('RGB')

    # Auto-crop: pixels darker than 25 are treated as background
    arr = np.array(img.convert('L'))
    mask = arr > 25
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if rows.any() and cols.any():
        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]
        pad = 15
        rmin = max(0, rmin - pad)
        rmax = min(arr.shape[0], rmax + pad)
        cmin = max(0, cmin - pad)
        cmax = min(arr.shape[1], cmax + pad)
        img = img.crop((cmin, rmin, cmax, rmax))

    # Boost contrast and sharpness
    img = ImageEnhance.Contrast(img).enhance(1.6)
    img = ImageEnhance.Sharpness(img).enhance(1.8)

    # Resize to max 1024px
    max_dim = 1024
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize(
            (int(img.width * ratio), int(img.height * ratio)),
            Image.LANCZOS,
        )

    fd, out_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd)
    img.save(out_path, 'JPEG', quality=90)
    return out_path


def analyze_document(image_path: str) -> dict:
    """
    Two-step document classification using llava:7b vision model.

    Step 1: Is there a government ID document with a person's photo? → YES / NO
    Step 2 (only if YES): Is it a Passport or a National ID card? → PASSPORT / NID

    Returns: { success, document_type, error }
    """
    # ── Preprocess: crop dark borders + enhance ───────────────────────────
    preprocessed_path = None
    try:
        preprocessed_path = preprocess_image(image_path)
        image_b64 = _encode_image(preprocessed_path)
    except Exception:
        # Preprocessing failed — fall back to original image
        try:
            image_b64 = _encode_image(image_path)
        except (OSError, IOError) as e:
            return {'success': False, 'document_type': None,
                    'error': f'Could not read image file: {e}'}
    finally:
        if preprocessed_path and os.path.exists(preprocessed_path):
            os.remove(preprocessed_path)

    # ── Step 1: Is there a government identity document with a photo? ─────
    r1 = _call_ollama(image_b64, _PROMPT_STEP1, num_predict=10)
    if not r1['success']:
        return {'success': False, 'document_type': None, 'error': r1['error']}

    is_document = 'YES' in r1['text'].strip().upper()

    if not is_document:
        return {
            'success': True,
            'document_type': 'Does not match NID or Passport format',
            'error': None,
        }

    # ── Step 2: Passport or National ID card? ────────────────────────────
    r2 = _call_ollama(image_b64, _PROMPT_STEP2, num_predict=15)
    if not r2['success']:
        return {'success': False, 'document_type': None, 'error': r2['error']}

    answer2 = r2['text'].strip().upper()
    doc_type = 'Passport' if 'PASSPORT' in answer2 else 'NID'

    return {'success': True, 'document_type': doc_type, 'error': None}


def _call_ollama(image_b64: str, prompt: str, num_predict: int) -> dict:
    """Single Ollama vision API call. Returns {'success', 'text', 'error'}."""
    payload = {
        'model': Config.OLLAMA_VISION_MODEL,
        'prompt': prompt,
        'images': [image_b64],
        'stream': False,
        'options': {'temperature': 0.1, 'num_predict': num_predict},
    }
    try:
        resp = requests.post(
            f"{Config.OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=90,
        )
    except requests.exceptions.ConnectionError:
        return {
            'success': False, 'text': None,
            'error': (
                f'Ollama is not running. Please start Ollama and ensure the vision model is loaded. '
                f'Run: ollama pull {Config.OLLAMA_VISION_MODEL}'
            ),
        }
    except requests.exceptions.Timeout:
        return {
            'success': False, 'text': None,
            'error': 'Ollama took too long to respond. The vision model may still be loading.',
        }

    if resp.status_code != 200:
        body = resp.text[:400]
        if 'not found' in body.lower() or resp.status_code == 404:
            return {
                'success': False, 'text': None,
                'error': (
                    f'Vision model "{Config.OLLAMA_VISION_MODEL}" is not installed. '
                    f'Run: ollama pull {Config.OLLAMA_VISION_MODEL}'
                ),
            }
        return {
            'success': False, 'text': None,
            'error': f'Ollama returned HTTP {resp.status_code}: {body}',
        }

    return {'success': True, 'text': resp.json().get('response', ''), 'error': None}


def _encode_image(path: str) -> str:
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')
