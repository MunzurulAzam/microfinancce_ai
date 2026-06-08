import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from config import Config
from document_verification.validator import validate_image_upload, verify_jpeg_magic_bytes
from document_verification.service import analyze_document

doc_verify_bp = Blueprint('document_verification', __name__)


@doc_verify_bp.route('/verify-document', methods=['POST'])
def verify_document():
    """
    POST /api/verify-document
    Accepts: multipart/form-data with field 'document' (JPEG image)
    Returns: { success, document_type } or { success: false, error }
    """
    if 'document' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No file uploaded. Send the image in a form field named "document".'
        }), 400

    file = request.files['document']

    valid, error_msg = validate_image_upload(file)
    if not valid:
        return jsonify({'success': False, 'error': error_msg}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(Config.DOC_VERIFY_UPLOAD_FOLDER, filename)
    file.save(file_path)

    try:
        if not verify_jpeg_magic_bytes(file_path):
            return jsonify({
                'success': False,
                'error': 'File content is not a valid JPEG image.'
            }), 400

        result = analyze_document(file_path)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    if not result['success']:
        return jsonify({'success': False, 'error': result['error']}), 503

    return jsonify({
        'success': True,
        'document_type': result['document_type']
    }), 200
