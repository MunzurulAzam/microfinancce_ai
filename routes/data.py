"""
Data management routes
Handles file upload and data queries
"""

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
from config import Config
from services.mssql_data_service import get_basic_stats, get_all_clients, get_all_groups

data_bp = Blueprint('data', __name__)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@data_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload and process CSV file
    
    Request: multipart/form-data with 'file' field
    Response: Success status and data summary
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Check file type
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Only CSV files allowed.'
            }), 400
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Load and process data
        success, message = data_processor.load_data(filepath)
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 500
        
        # Get basic stats
        stats = data_processor.get_basic_stats()
        
        return jsonify({
            'success': True,
            'message': message,
            'stats': stats
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error processing file: {str(e)}'
        }), 500


@data_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    Get basic statistics from MSSQL database.
    """
    try:
        stats = get_basic_stats()

        if stats is None:
            return jsonify({
                'success': False,
                'error': 'Could not connect to database or no data found.'
            }), 500

        return jsonify({
            'success': True,
            'stats': stats
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_bp.route('/clients', methods=['GET'])
def get_clients():
    """
    Get client list from MSSQL.
    """
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        search = request.args.get('search', None)

        clients = get_all_clients(limit=limit, offset=offset, search=search)

        return jsonify({
            'success': True,
            'clients': clients,
            'count': len(clients)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_bp.route('/groups', methods=['GET'])
def get_groups():
    """
    Get group list from MSSQL.
    """
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        search = request.args.get('search', None)

        groups = get_all_groups(limit=limit, offset=offset, search=search)

        return jsonify({
            'success': True,
            'groups': groups,
            'count': len(groups)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
