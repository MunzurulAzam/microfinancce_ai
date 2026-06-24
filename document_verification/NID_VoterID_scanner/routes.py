import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from config import Config
from document_verification.NID_VoterID_scanner.validator import (
    validate_id_image_upload, verify_magic_bytes
)
from document_verification.NID_VoterID_scanner.service import scan_id_card

nid_scanner_bp = Blueprint('nid_scanner', __name__)


@nid_scanner_bp.route('/scan-id', methods=['POST'])
def scan_id():
    """
    POST /api/scan-id
    Input:  multipart/form-data, field 'id_image' (JPEG / PNG / WebP, max 10 MB)
    Output: { success: true, data: { name, id_number, id_valid, country,
               country_code, id_type, confidence, extractor, raw_text_sample } }
            { success: false, error: '...' }
    """
    if 'id_image' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No file uploaded. Send the image in a form field named "id_image".',
        }), 400

    file = request.files['id_image']

    valid, error_msg = validate_id_image_upload(file)
    if not valid:
        return jsonify({'success': False, 'error': error_msg}), 400

    filename = f'{uuid.uuid4().hex}_{secure_filename(file.filename)}'
    file_path = os.path.join(Config.NID_SCAN_UPLOAD_FOLDER, filename)
    file.save(file_path)

    try:
        ok, format_or_error = verify_magic_bytes(file_path)
        if not ok:
            return jsonify({'success': False, 'error': format_or_error}), 400

        result = scan_id_card(file_path)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 503

    return jsonify({
        'success': True,
        'data': result['data'],
    }), 200
