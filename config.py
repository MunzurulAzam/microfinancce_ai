import os

class Config:
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = True
    
    _cors_env = os.environ.get('CORS_ORIGINS', '')
    CORS_ORIGINS = [o.strip().rstrip('/') for o in _cors_env.split(',') if o.strip()] or \
                   ['http://localhost:5173', 'http://localhost:3000', 'http://localhost:5001']
    
    DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    UPLOAD_FOLDER = os.path.join(DATA_FOLDER, 'uploads')
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
    
    MODEL_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
    MODEL_PATH = os.path.join(MODEL_FOLDER, 'llama-model.gguf')
    MODEL_URL = 'https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf'
    USE_AI_MODEL = True
    
    MODEL_N_CTX = 2048
    MODEL_N_THREADS = 2
    MODEL_MAX_TOKENS = 500
    MODEL_TEMPERATURE = 0.7
    
    MSSQL_SERVER = os.environ.get('MSSQL_SERVER', '192.129.248.10')
    MSSQL_PORT = int(os.environ.get('MSSQL_PORT', 1543))
    MSSQL_USER = os.environ.get('MSSQL_USER', 'umissa')
    MSSQL_PASSWORD = os.environ.get('MSSQL_PASSWORD', 'm9X3f1S>C6@:E)BI')
    MSSQL_DATABASE = os.environ.get('MSSQL_DATABASE', 'db_UMISv2_ug')
    
    OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'deepseek-coder:6.7b')

    OLLAMA_VISION_MODEL = os.environ.get('OLLAMA_VISION_MODEL', 'minimax-m3:cloud')
    OLLAMA_VISION_FALLBACKS = os.environ.get(
        'OLLAMA_VISION_FALLBACKS', 'gemma3:27b-cloud'
    )
    DOC_VERIFY_UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'temp_uploads', 'doc_verify'
    )
    DOC_VERIFY_MAX_FILE_SIZE_MB = int(os.environ.get('DOC_VERIFY_MAX_FILE_SIZE_MB', 10))

    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    NID_SCAN_UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'temp_uploads', 'nid_scan'
    )
    NID_SCAN_MAX_FILE_SIZE_MB = int(os.environ.get('NID_SCAN_MAX_FILE_SIZE_MB', 10))

    @staticmethod
    def init_app(app):
        os.makedirs(Config.DATA_FOLDER, exist_ok=True)
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.MODEL_FOLDER, exist_ok=True)
        os.makedirs(Config.DOC_VERIFY_UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.NID_SCAN_UPLOAD_FOLDER, exist_ok=True)
