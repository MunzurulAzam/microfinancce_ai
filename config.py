import os

class Config:
    """Application configuration"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = True
    
    # CORS — read from env var on Render (comma-separated), fall back to localhost for local dev
    _cors_env = os.environ.get('CORS_ORIGINS', '')
    # Strip spaces AND trailing slashes for exact origin matching
    CORS_ORIGINS = [o.strip().rstrip('/') for o in _cors_env.split(',') if o.strip()] or \
                   ['http://localhost:5173', 'http://localhost:3000', 'http://localhost:5001']
    
    # Data
    DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    UPLOAD_FOLDER = os.path.join(DATA_FOLDER, 'uploads')
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
    
    # Model
    MODEL_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
    MODEL_PATH = os.path.join(MODEL_FOLDER, 'llama-model.gguf')
    MODEL_URL = 'https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf'
    USE_AI_MODEL = True  # Set to False to use fallback analysis
    
    # AI Model settings
    MODEL_N_CTX = 2048
    MODEL_N_THREADS = 2
    MODEL_MAX_TOKENS = 500
    MODEL_TEMPERATURE = 0.7
    
    # MSSQL Database (Credit Scoring)
    MSSQL_SERVER = os.environ.get('MSSQL_SERVER', '192.129.248.10')
    MSSQL_PORT = int(os.environ.get('MSSQL_PORT', 1543))
    MSSQL_USER = os.environ.get('MSSQL_USER', 'umissa')
    MSSQL_PASSWORD = os.environ.get('MSSQL_PASSWORD', 'm9X3f1S>C6@:E)BI')
    MSSQL_DATABASE = os.environ.get('MSSQL_DATABASE', 'db_UMISv2_ug')
    
    # Ollama (Local LLM for Credit Scoring AI)
    OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'deepseek-coder:6.7b')

    # Ollama Vision — shared by Document Verification + NID/Voter scanner.
    OLLAMA_VISION_MODEL = os.environ.get('OLLAMA_VISION_MODEL', 'minimax-m3:cloud')
    # Comma-separated fallback vision models, tried if the primary is overloaded
    # for keeps accuracy high instead of dropping to offline OCR.
    OLLAMA_VISION_FALLBACKS = os.environ.get(
        'OLLAMA_VISION_FALLBACKS', 'gemma3:27b-cloud'
    )
    DOC_VERIFY_UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'temp_uploads', 'doc_verify'
    )
    DOC_VERIFY_MAX_FILE_SIZE_MB = int(os.environ.get('DOC_VERIFY_MAX_FILE_SIZE_MB', 10))

    # # NID/VoterID Scanner (Claude Vision primary, Ollama fallback when key is absent)
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    NID_SCAN_UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'temp_uploads', 'nid_scan'
    )
    NID_SCAN_MAX_FILE_SIZE_MB = int(os.environ.get('NID_SCAN_MAX_FILE_SIZE_MB', 10))

    @staticmethod
    def init_app(app):
        """Initialize app with config"""
        os.makedirs(Config.DATA_FOLDER, exist_ok=True)
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.MODEL_FOLDER, exist_ok=True)
        os.makedirs(Config.DOC_VERIFY_UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.NID_SCAN_UPLOAD_FOLDER, exist_ok=True)
