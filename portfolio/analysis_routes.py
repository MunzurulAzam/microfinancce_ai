from flask import Blueprint, request, jsonify
from portfolio.analyzer import analyze_client, analyze_group
from portfolio.performance import (
    get_top_performers,
    get_risk_analysis,
    get_quick_insights,
    get_business_performance
)

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/client', methods=['POST'])
def analyze_client_endpoint():
    """POST — {"client_name": str} in, client analysis with AI insights out."""
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
    """POST — {"group_name": str} in, group analysis with AI insights out."""
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
    """Portfolio-wide insights: top performers and risks."""
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
    """Top performing clients; ?limit= defaults to 10."""
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
    """Top performing groups; ?limit= defaults to 10."""
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
    """High-risk clients; ?threshold= is the overdue count, default 5."""
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
    """Performance metrics per business type."""
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
