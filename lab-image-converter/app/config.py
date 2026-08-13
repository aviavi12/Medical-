import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "2048"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

DEFAULT_JPEG_QUALITY = int(os.getenv("DEFAULT_JPEG_QUALITY", "95"))

CLEANUP_AFTER_DOWNLOAD = os.getenv("CLEANUP_AFTER_DOWNLOAD", "false").lower() == "true"

SUPPORTED_EXTENSIONS = {".czi", ".tif", ".tiff", ".png", ".jpg", ".jpeg"}
