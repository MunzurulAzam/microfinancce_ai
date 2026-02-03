import os

class Config:
    """Application configuration"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = True
    
    # CORS
    CORS_ORIGINS = ['http://localhost:5173', 'http://localhost:3000', 'http://localhost:5000']
    
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
    
    @staticmethod
    def init_app(app):
        """Initialize app with config"""
        os.makedirs(Config.DATA_FOLDER, exist_ok=True)
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.MODEL_FOLDER, exist_ok=True)
