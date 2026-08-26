import os
import tempfile
import numpy as np
from PIL import Image, ImageEnhance


def preprocess_id_image(input_path: str) -> str:
    """Crop, upscale and lightly enhance an ID photo. Returns a temp JPEG the caller must delete."""
    img = Image.open(input_path).convert('RGB')

    arr = np.array(img.convert('L'))
    mask = arr > 30
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if rows.any() and cols.any():
        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]
        pad = 10
        rmin = max(0, rmin - pad)
        rmax = min(arr.shape[0], rmax + pad)
        cmin = max(0, cmin - pad)
        cmax = min(arr.shape[1], cmax + pad)
        img = img.crop((cmin, rmin, cmax, rmax))

    if max(img.size) < 1000:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)

    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(1.2)

    max_dim = 1600
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize(
            (int(img.width * ratio), int(img.height * ratio)),
            Image.LANCZOS,
        )

    fd, out_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd)
    img.save(out_path, 'JPEG', quality=92)
    return out_path
