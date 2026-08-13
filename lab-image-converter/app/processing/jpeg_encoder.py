from pathlib import Path

from PIL import Image

from app.processing.image_processing import ensure_rgb


def encode_jpeg(image: Image.Image, output_path: str | Path, quality: int = 95) -> Path:
    output_path = Path(output_path)

    if image.mode == "L":
        pass
    else:
        image = ensure_rgb(image)

    image.save(str(output_path), format="JPEG", quality=quality, optimize=True)
    return output_path


def validate_jpeg(file_path: str | Path) -> bool:
    file_path = Path(file_path)

    if not file_path.exists():
        return False

    if file_path.stat().st_size == 0:
        return False

    try:
        with Image.open(file_path) as img:
            img.verify()
    except Exception:
        return False

    try:
        with Image.open(file_path) as img:
            img.load()
            if img.format != "JPEG":
                return False
            if img.width <= 0 or img.height <= 0:
                return False
            if img.mode not in ("RGB", "L"):
                return False
    except Exception:
        return False

    return True
