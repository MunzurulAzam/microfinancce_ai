"""
Analysis routes
Handles client and group analysis requests
"""

from flask import Blueprint, request, jsonify
from services.analyzer import analyze_client, analyze_group
from services.performance import (
    get_top_performers,
    get_risk_analysis,
    get_quick_insights,
    get_business_performance
)

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/client', methods=['POST'])
def analyze_client_endpoint():
    """
    Analyze a specific client
    
    Request body: {"client_name": "John Doe"}
    Response: Client analysis with AI insights
    """
    try:
        data = request.get_json()
        
        if not data or 'client_name' not in data:
            return jsonify({
                'success': False,
                'error': 'client_name is required'
            }), 400
        
        client_name = data['client_name']
        result = analyze_client(client_name)
        
        if not result['success']:
            return jsonify(result), 404
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@analysis_bp.route('/group', methods=['POST'])
def analyze_group_endpoint():
    """
    Analyze a specific group
    
    Request body: {"group_name": "Group A"}
    Response: Group analysis with AI insights
    """
    try:
        data = request.get_json()
        
        if not data or 'group_name' not in data:
            return jsonify({
                'success': False,
                'error': 'group_name is required'
            }), 400
        
        group_name = data['group_name']
        result = analyze_group(group_name)
        
        if not result['success']:
            return jsonify(result), 404
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@analysis_bp.route('/insights', methods=['GET'])
def get_insights():
    """
    Get quick insights about the portfolio
    
    Response: Comprehensive insights including top performers and risks
    """
    try:
        insights = get_quick_insights()
        
        if insights is None:
            return jsonify({
                'success': False,
                'error': 'No data loaded. Please upload a CSV file first.'
            }), 400
        
        return jsonify({
            'success': True,
            'insights': insights
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@analysis_bp.route('/top-clients', methods=['GET'])
def get_top_clients():
    """
    Get top performing clients
    
    Query params:
        - limit: Number of results (default: 10)
    
    Response: List of top performing clients
    """
    try:
        limit = int(request.args.get('limit', 10))
        
        top_clients = get_top_performers(limit=limit, performance_type='clients')
        
        return jsonify({
            'success': True,
            'top_clients': top_clients,
            'count': len(top_clients)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@analysis_bp.route('/top-groups', methods=['GET'])
def get_top_groups():
    """
    Get top performing groups
    
    Query params:
        - limit: Number of results (default: 10)
    
    Response: List of top performing groups
    """
    try:
        limit = int(request.args.get('limit', 10))
        
        top_groups = get_top_performers(limit=limit, performance_type='groups')
        
        return jsonify({
            'success': True,
            'top_groups': top_groups,
            'count': len(top_groups)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@analysis_bp.route('/risk-analysis', methods=['GET'])
def risk_analysis():
    """
    Get risk analysis for high-risk clients
    
    Query params:
        - threshold: Overdue count threshold (default: 5)
    
    Response: List of high-risk clients and statistics
    """
    try:
        threshold = int(request.args.get('threshold', 5))
        
        risk_data = get_risk_analysis(overdue_threshold=threshold)
        
        return jsonify({
            'success': True,
            'risk_analysis': risk_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@analysis_bp.route('/business-performance', methods=['GET'])
def business_performance():
    """
    Get performance analysis by business type
    
    Response: Performance metrics for each business type
    """
    try:
        business_data = get_business_performance()
        
        return jsonify({
            'success': True,
            'business_performance': business_data,
            'count': len(business_data)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
