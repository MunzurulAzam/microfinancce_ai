from a2wsgi import WSGIMiddleware
from app import create_app

flask_app = create_app()
app = WSGIMiddleware(flask_app)
