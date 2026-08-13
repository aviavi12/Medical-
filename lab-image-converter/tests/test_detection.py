import pytest
from pathlib import Path
from app.detection.detector import detect_file_type


@pytest.fixture
def sample_dir(tmp_path):
    return tmp_path


def _write(path, content):
    path.write_bytes(content)
    return path


def test_detect_jpeg_signature(sample_dir):
    p = _write(sample_dir / "test.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    result = detect_file_type(p)
    assert result.format == "JPEG"
    assert result.confidence >= 0.9


def test_detect_png_signature(sample_dir):
    p = _write(sample_dir / "test.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    result = detect_file_type(p)
    assert result.format == "PNG"
    assert result.confidence >= 0.9


def test_detect_tiff_le_signature(sample_dir):
    p = _write(sample_dir / "test.tif", b"II\x2a\x00" + b"\x00" * 100)
    result = detect_file_type(p)
    assert result.format == "TIFF"
    assert result.confidence >= 0.9


def test_detect_tiff_be_signature(sample_dir):
    p = _write(sample_dir / "test.tiff", b"MM\x00\x2a" + b"\x00" * 100)
    result = detect_file_type(p)
    assert result.format == "TIFF"
    assert result.confidence >= 0.9


def test_detect_czi_signature(sample_dir):
    p = _write(sample_dir / "test.czi", b"ZISRAWFILE" + b"\x00" * 100)
    result = detect_file_type(p)
    assert result.format == "CZI"
    assert result.confidence >= 0.9


def test_detect_by_extension_only(sample_dir):
    p = _write(sample_dir / "test.png", b"\x00\x00\x00\x00" + b"\x00" * 100)
    result = detect_file_type(p)
    assert result.format == "PNG"
    assert result.confidence < 0.9


def test_detect_unknown(sample_dir):
    p = _write(sample_dir / "test.xyz", b"\x00\x01\x02\x03" + b"\x00" * 100)
    result = detect_file_type(p)
    assert result.format == "UNKNOWN"
    assert result.confidence == 0.0
