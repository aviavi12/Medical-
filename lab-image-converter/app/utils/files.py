import uuid
import zipfile
import logging
from pathlib import Path
from typing import Optional

from app.config import UPLOAD_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)

_conversion_registry: dict[str, Path] = {}
_batch_registry: dict[str, list[Path]] = {}


def generate_conversion_id() -> str:
    return uuid.uuid4().hex


def save_upload(content: bytes, filename: str) -> Path:
    upload_id = uuid.uuid4().hex
    upload_path = UPLOAD_DIR / f"{upload_id}_{filename}"
    upload_path.write_bytes(content)
    return upload_path


def register_output(conversion_id: str, output_path: Path) -> None:
    _conversion_registry[conversion_id] = output_path


def register_batch(batch_id: str, output_paths: list[Path]) -> None:
    _batch_registry[batch_id] = output_paths


def get_output_path(conversion_id: str) -> Optional[Path]:
    path = _conversion_registry.get(conversion_id)
    if path and path.exists():
        return path
    return None


def get_batch_zip(batch_id: str) -> Optional[Path]:
    paths = _batch_registry.get(batch_id)
    if not paths:
        return None
    zip_path = OUTPUT_DIR / f"{batch_id}_all.zip"
    if zip_path.exists():
        return zip_path
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            if p.exists():
                zf.write(p, p.name.split("_", 1)[-1] if "_" in p.name else p.name)
    return zip_path


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


def resolve_output_directory(user_path: str | None) -> Path | None:
    if not user_path or not user_path.strip():
        return None
    target = Path(user_path).resolve()
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
    if not target.is_dir():
        return None
    return target
