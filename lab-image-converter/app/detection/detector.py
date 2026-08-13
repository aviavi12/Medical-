import mimetypes
from pathlib import Path

from app.models.schemas import FileDetectionResult

_SIGNATURES = {
    "CZI": [b"ZISRAWFILE"],
    "TIFF": [b"II\x2a\x00", b"MM\x00\x2a", b"II\x2b\x00", b"MM\x00\x2b"],
    "PNG": [b"\x89PNG\r\n\x1a\n"],
    "JPEG": [b"\xff\xd8\xff"],
}

_EXT_MAP = {
    ".czi": "CZI",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
}

_FORMAT_MIME = {
    "CZI": "application/octet-stream",
    "TIFF": "image/tiff",
    "PNG": "image/png",
    "JPEG": "image/jpeg",
}


def _check_signature(data: bytes) -> str | None:
    for fmt, sigs in _SIGNATURES.items():
        for sig in sigs:
            if data[: len(sig)] == sig:
                return fmt
    return None


def detect_file_type(file_path: str | Path) -> FileDetectionResult:
    file_path = Path(file_path)
    ext = file_path.suffix.lower()
    ext_format = _EXT_MAP.get(ext)

    header = b""
    try:
        with open(file_path, "rb") as f:
            header = f.read(64)
    except OSError:
        pass

    sig_format = _check_signature(header) if header else None

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type is None:
        mime_type = "application/octet-stream"

    if sig_format and ext_format and sig_format == ext_format:
        return FileDetectionResult(
            format=sig_format,
            extension=ext,
            mime_type=_FORMAT_MIME.get(sig_format, mime_type),
            confidence=0.99,
        )

    if sig_format:
        return FileDetectionResult(
            format=sig_format,
            extension=ext,
            mime_type=_FORMAT_MIME.get(sig_format, mime_type),
            confidence=0.90,
        )

    if ext_format:
        return FileDetectionResult(
            format=ext_format,
            extension=ext,
            mime_type=_FORMAT_MIME.get(ext_format, mime_type),
            confidence=0.70,
        )

    return FileDetectionResult(
        format="UNKNOWN",
        extension=ext,
        mime_type=mime_type,
        confidence=0.0,
    )
