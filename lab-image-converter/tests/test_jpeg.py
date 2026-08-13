import numpy as np
import pytest
from PIL import Image

from app.processing.image_processing import normalize_to_uint8, ensure_rgb, remove_alpha, array_to_pil
from app.processing.jpeg_encoder import encode_jpeg, validate_jpeg


def test_normalize_uint8_16bit():
    arr = np.array([[0, 32768, 65535]], dtype=np.uint16)
    result = normalize_to_uint8(arr)
    assert result.dtype == np.uint8
    assert result[0, 0] == 0
    assert result[0, 2] == 255


def test_normalize_uniform():
    arr = np.ones((10, 10), dtype=np.float32) * 42.0
    result = normalize_to_uint8(arr)
    assert result.dtype == np.uint8
    assert np.all(result == 0)


def test_normalize_nan_inf():
    arr = np.array([[np.nan, np.inf, -np.inf, 100.0]], dtype=np.float64)
    result = normalize_to_uint8(arr)
    assert result.dtype == np.uint8
    assert not np.any(np.isnan(result))


def test_ensure_rgb_from_rgba():
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
    result = ensure_rgb(img)
    assert result.mode == "RGB"


def test_ensure_rgb_from_l():
    img = Image.new("L", (10, 10), 128)
    result = ensure_rgb(img)
    assert result.mode == "RGB"


def test_ensure_rgb_passthrough():
    img = Image.new("RGB", (10, 10), (0, 255, 0))
    result = ensure_rgb(img)
    assert result.mode == "RGB"


def test_remove_alpha_white_bg():
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 0))
    result = remove_alpha(img)
    assert result.mode == "RGB"
    pixel = result.getpixel((5, 5))
    assert pixel == (255, 255, 255)


def test_encode_jpeg_rgb(tmp_path):
    img = Image.new("RGB", (100, 100), (0, 128, 255))
    out = tmp_path / "test.jpg"
    encode_jpeg(img, out, quality=95)
    assert out.exists()
    with Image.open(out) as loaded:
        assert loaded.format == "JPEG"


def test_encode_jpeg_grayscale(tmp_path):
    img = Image.new("L", (50, 50), 128)
    out = tmp_path / "test.jpg"
    encode_jpeg(img, out, quality=90)
    assert out.exists()
    with Image.open(out) as loaded:
        assert loaded.format == "JPEG"
        assert loaded.mode == "L"


def test_validate_jpeg_valid(tmp_path):
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    out = tmp_path / "valid.jpg"
    img.save(str(out), format="JPEG")
    assert validate_jpeg(out) is True


def test_validate_jpeg_invalid(tmp_path):
    out = tmp_path / "invalid.jpg"
    out.write_bytes(b"not a jpeg")
    assert validate_jpeg(out) is False


def test_validate_jpeg_missing(tmp_path):
    assert validate_jpeg(tmp_path / "nope.jpg") is False


def test_validate_jpeg_empty(tmp_path):
    out = tmp_path / "empty.jpg"
    out.write_bytes(b"")
    assert validate_jpeg(out) is False


def test_array_to_pil_2d():
    arr = np.random.randint(0, 255, (32, 32), dtype=np.uint8)
    img = array_to_pil(arr)
    assert img.mode == "L"
    assert img.size == (32, 32)


def test_array_to_pil_3d_rgb():
    arr = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
    img = array_to_pil(arr)
    assert img.mode == "RGB"


def test_array_to_pil_16bit_normalizes():
    arr = np.random.randint(0, 65535, (32, 32), dtype=np.uint16)
    img = array_to_pil(arr)
    assert img.mode == "L"
