import os
from document_verification.NID_VoterID_scanner.preprocessor import preprocess_id_image
from document_verification.NID_VoterID_scanner.extractor import extract_id_data
from document_verification.NID_VoterID_scanner.country_patterns import (
    detect_country, validate_id_number, GENERIC_FALLBACK
)


def scan_id_card(image_path: str) -> dict:
    """Full scan pipeline: preprocess, vision extract, detect country, validate ID number."""
    preprocessed_path = None
    try:
        preprocessed_path = preprocess_id_image(image_path)
        working_path = preprocessed_path
    except Exception as e:
        print(f'[NIDScanner] Preprocessing failed ({e}), using original image.')
        working_path = image_path

    try:
        extraction = extract_id_data(working_path)

        if not extraction['success']:
            return {
                'success': False,
                'data': None,
                'error': extraction.get('error', 'Vision extraction failed.'),
            }

        name = extraction.get('name')
        id_number = extraction.get('id_number')
        country_hint = extraction.get('country_hint') or ''
        id_type_hint = extraction.get('id_type_hint') or ''
        raw_text_sample = extraction.get('raw_text_sample')
        confidence = extraction.get('confidence', 'unknown')
        extractor = extraction.get('extractor', 'unknown')

        combined_text = ' '.join(filter(None, [country_hint, id_type_hint, raw_text_sample or '']))
        country = detect_country(combined_text)

        id_valid = validate_id_number(id_number or '', country)
        if not id_valid and id_number:
            id_valid = validate_id_number(id_number, GENERIC_FALLBACK)

        return {
            'success': True,
            'data': {
                'name': name,
                'id_number': id_number,
                'id_valid': id_valid,
                'country': country['name'],
                'country_code': country['code'],
                'id_type': id_type_hint if id_type_hint else country['id_type'],
                'confidence': confidence,
                'extractor': extractor,
                'raw_text_sample': raw_text_sample,
            },
            'error': None,
        }

    finally:
        if preprocessed_path and os.path.exists(preprocessed_path):
            os.remove(preprocessed_path)
