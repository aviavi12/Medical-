import uuid
import shutil
import logging
from pathlib import Path
from typing import Optional

from app.config import UPLOAD_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)

_conversion_registry: dict[str, Path] = {}


def generate_conversion_id() -> str:
    return uuid.uuid4().hex


def save_upload(content: bytes, filename: str) -> Path:
    upload_id = uuid.uuid4().hex
    upload_path = UPLOAD_DIR / f"{upload_id}_{filename}"
    upload_path.write_bytes(content)
    return upload_path


def register_output(conversion_id: str, output_path: Path) -> None:
    _conversion_registry[conversion_id] = output_path


def get_output_path(conversion_id: str) -> Optional[Path]:
    path = _conversion_registry.get(conversion_id)
    if path and path.exists():
        return path
    return None


def cleanup_file(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError as e:
        logger.warning(f"Failed to clean up {path}: {e}")


def cleanup_upload(upload_path: Path) -> None:
    cleanup_file(upload_path)


def get_output_dir() -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR
