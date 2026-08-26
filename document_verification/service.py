import os
import tempfile
import numpy as np
from PIL import Image, ImageEnhance
from document_verification.vision_client import call_vision, encode_image


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
    """Crop, sharpen and resize to 1024px. Returns a temp JPEG the caller must delete."""
    img = Image.open(input_path).convert('RGB')

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

    if max(img.size) < 1000:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)

    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(1.2)

    max_dim = 1600
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize(
            (int(img.width * ratio), int(img.height * ratio)),
            Image.LANCZOS,
        )

    fd, out_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd)
    img.save(out_path, 'JPEG', quality=92)
    return out_path


def analyze_document(image_path: str) -> dict:
    """Two-step document classification using llava:7b vision model."""
    preprocessed_path = None
    try:
        preprocessed_path = preprocess_image(image_path)
        image_b64 = encode_image(preprocessed_path)
    except Exception:
        try:
            image_b64 = encode_image(image_path)
        except (OSError, IOError) as e:
            return {'success': False, 'document_type': None,
                    'error': f'Could not read image file: {e}'}
    finally:
        if preprocessed_path and os.path.exists(preprocessed_path):
            os.remove(preprocessed_path)

    r1 = call_vision(image_b64, _PROMPT_STEP1, num_predict=10)
    if not r1['success']:
        return {'success': False, 'document_type': None, 'error': r1['error']}

    is_document = 'YES' in r1['text'].strip().upper()

    if not is_document:
        return {
            'success': True,
            'document_type': 'Does not match NID or Passport format',
            'error': None,
        }

    r2 = call_vision(image_b64, _PROMPT_STEP2, num_predict=15)
    if not r2['success']:
        return {'success': False, 'document_type': None, 'error': r2['error']}

    answer2 = r2['text'].strip().upper()
    doc_type = 'Passport' if 'PASSPORT' in answer2 else 'NID'

    return {'success': True, 'document_type': doc_type, 'error': None}
