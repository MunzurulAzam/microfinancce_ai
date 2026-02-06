"""
Main Flask Application
Microfinance AI Analysis API
"""

from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from routes import data_bp, analysis_bp, ask_bp, evaluation_bp


def create_app(config_class=Config):
    """Create and configure Flask application"""
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize config
    config_class.init_app(app)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": config_class.CORS_ORIGINS}})
    
    # Auto-load data if available
    from services.data_processor import data_processor
    data_processor.auto_load()
    
    # Register blueprints
    app.register_blueprint(data_bp, url_prefix='/api')
    app.register_blueprint(analysis_bp, url_prefix='/api/analyze')
    app.register_blueprint(ask_bp, url_prefix='/api')  # Conversational endpoint
    app.register_blueprint(evaluation_bp, url_prefix='/api')
    
    # Root endpoint
    @app.route('/')
    def index():
        return jsonify({
            'message': 'Microfinance AI Analysis API',
            'version': '1.0.0',
            'endpoints': {
                'conversational': {
                    'POST /api/ask': '🤖 Ask any question in natural language (RECOMMENDED)'
                },
                'data': {
                    'POST /api/upload': 'Upload CSV file',
                    'GET /api/stats': 'Get basic statistics',
                    'GET /api/clients': 'List all clients',
                    'GET /api/groups': 'List all groups'
                },
                'analysis': {
                    'POST /api/analyze/client': 'Analyze specific client',
                    'POST /api/analyze/group': 'Analyze specific group',
                    'GET /api/analyze/insights': 'Get quick insights',
                    'GET /api/analyze/top-clients': 'Get top clients',
                    'GET /api/analyze/top-groups': 'Get top groups',
                    'GET /api/analyze/risk-analysis': 'Get risk analysis',
                    'GET /api/analyze/business-performance': 'Get business performance'
                }
            },
            'documentation': 'See README.md for detailed API documentation'
        })
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'service': 'Microfinance AI API'
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Endpoint not found'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
    
    return app


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 MICROFINANCE AI ANALYSIS API")
    print("=" * 60)
    print("Starting Flask server...")
    print("📡 Server will run on: http://localhost:5000")
    print("📚 API Documentation: http://localhost:5000/")
    print("💊 Health check: http://localhost:5000/health")
    print("=" * 60)
    
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
