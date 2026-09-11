from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent / ".env")

from flask import Flask, jsonify, request
from config import Config
from portfolio import data_bp, analysis_bp
from assistant import ask_bp
from evaluation import evaluation_bp
from document_verification import doc_verify_bp
from document_verification.NID_VoterID_scanner import nid_scanner_bp
from reports.api import reports_bp
from ask_ai.api import ask_ai_bp
from ask_ai.dify import dify_kb_bp


def create_app(config_class=Config):
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    config_class.init_app(app)
    from core.cloud import configuration_status
    cloud_status = configuration_status()
    if not cloud_status['configured']:
        app.logger.warning('Ollama Cloud configuration unavailable (%s); warehouse AI SQL requires server setup. Fixed reports remain available.', cloud_status['code'])

    allowed_origins = config_class.CORS_ORIGINS
    print(f"CORS ALLOWED ORIGINS: {allowed_origins}")

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin', '')
        if origin in allowed_origins or '*' in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = origin
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'

        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response

    @app.before_request
    def handle_preflight():
        if request.method == 'OPTIONS':
            response = app.make_default_options_response()
            return response
    
    from portfolio.csv_store import data_processor
    data_processor.auto_load()
    
    app.register_blueprint(data_bp, url_prefix='/api')
    app.register_blueprint(analysis_bp, url_prefix='/api/analyze')
    app.register_blueprint(ask_bp, url_prefix='/api')
    app.register_blueprint(evaluation_bp, url_prefix='/api')
    app.register_blueprint(doc_verify_bp, url_prefix='/api')
    app.register_blueprint(nid_scanner_bp, url_prefix='/api')
    app.register_blueprint(ask_ai_bp, url_prefix='/api')
    app.register_blueprint(reports_bp, url_prefix='/api')
    app.register_blueprint(dify_kb_bp, url_prefix='/api')

    from ask_ai import schema as ask_ai_schema
    ask_ai_schema.warm()
    
    @app.route('/')
    def index():
        return jsonify({
            'message': 'Microfinance AI Analysis API',
            'version': '1.0.0',
            'endpoints': {
                'conversational': {
                    'POST /api/ask': 'Ask any question in natural language (RECOMMENDED)'
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
                },
                'document_verification': {
                    'POST /api/verify-document': 'Verify if image is NID, Passport, or neither (JPEG only)',
                    'POST /api/scan-id': 'Scan NID/VoterID card — extracts name + ID number (JPEG/PNG/WebP)'
                },
                'ask_ai': {
                    'POST /api/ask-ai': 'Natural-language Q&A over the DW warehouse, all 4 countries (UG/KY/ZM/TZ) — text-to-SQL',
                    'POST /api/dify/retrieval': 'Dify external knowledge API (knowledge_id: dw-live | dw-schema)'
                }
            },
            'documentation': 'See README.md for detailed API documentation'
        })
    
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'service': 'Microfinance AI API',
            'cloud': configuration_status()
        })
    
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
    print("MICROFINANCE AI ANALYSIS API")
    print("=" * 60)
    print("Starting Flask server...")
    print("Server will run on: http://localhost:5001")
    print("API Documentation: http://localhost:5001/")
    print("Health check: http://localhost:5001/health")
    print("=" * 60)
    
    app = create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)
