from werkzeug.datastructures import FileStorage
from config import Config

ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/jpg'}


def validate_image_upload(file: FileStorage) -> tuple:
    if not file or file.filename == '':
        return False, 'No file selected.'

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return False, f'Invalid file type ".{ext}". Only JPG/JPEG images are accepted.'

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        return False, 'File MIME type is not image/jpeg. Only JPEG images are accepted.'

    max_bytes = Config.DOC_VERIFY_MAX_FILE_SIZE_MB * 1024 * 1024
    file.stream.seek(0, 2)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > max_bytes:
        return False, f'File exceeds {Config.DOC_VERIFY_MAX_FILE_SIZE_MB}MB limit.'

    return True, ''


def verify_jpeg_magic_bytes(file_path: str) -> bool:
    """JPEG files must start with FF D8 FF."""
    try:
        with open(file_path, 'rb') as f:
            return f.read(3) == b'\xff\xd8\xff'
    except OSError:
        return False
