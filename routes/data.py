"""
Data management routes
Handles file upload and data queries
"""

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
from config import Config
from services.data_processor import data_processor

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
    Get basic statistics about the dataset
    
    Response: Statistical summary
    """
    try:
        stats = data_processor.get_basic_stats()
        
        if stats is None:
            return jsonify({
                'success': False,
                'error': 'No data loaded. Please upload a CSV file first.'
            }), 400
        
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
    Get list of clients with pagination and search
    
    Query params:
        - limit: Number of results (default: 100)
        - offset: Starting position (default: 0)
        - search: Search term for client name
    
    Response: List of clients
    """
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        search = request.args.get('search', None)
        
        clients = data_processor.get_all_clients(limit=limit, offset=offset, search=search)
        
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
    Get list of groups with pagination and search
    
    Query params:
        - limit: Number of results (default: 100)
        - offset: Starting position (default: 0)
        - search: Search term for group name
    
    Response: List of groups
    """
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        search = request.args.get('search', None)
        
        groups = data_processor.get_all_groups(limit=limit, offset=offset, search=search)
        
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
