from werkzeug.datastructures import FileStorage
from config import Config

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/jpg',
    'image/png',
    'image/webp',
}


def validate_id_image_upload(file: FileStorage) -> tuple:
    if not file or file.filename == '':
        return False, 'No file selected.'

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return False, (
            f'Invalid file type ".{ext}". '
            'Accepted formats: JPG, JPEG, PNG, WebP.'
        )

    if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
        return False, (
            f'MIME type "{file.content_type}" is not accepted. '
            'Send JPEG, PNG, or WebP images only.'
        )

    max_bytes = Config.NID_SCAN_MAX_FILE_SIZE_MB * 1024 * 1024
    file.stream.seek(0, 2)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > max_bytes:
        return False, f'File exceeds {Config.NID_SCAN_MAX_FILE_SIZE_MB} MB limit.'

    return True, ''


def verify_magic_bytes(file_path: str) -> tuple:
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)
    except OSError as e:
        return False, f'Cannot read file: {e}'

    if header[:3] == b'\xff\xd8\xff':
        return True, 'jpeg'
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return True, 'png'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return True, 'webp'

    return False, (
        'File content does not match a valid JPEG, PNG, or WebP image. '
        'The file may be corrupted or mislabeled.'
    )
