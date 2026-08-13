import numpy as np
import tifffile
import pytest
from PIL import Image

from app.converters.tiff_converter import TIFFConverter


@pytest.fixture
def converter():
    return TIFFConverter()


def _make_tiff(path, data):
    tifffile.imwrite(str(path), data)
    return path


def test_inspect_grayscale_8bit(tmp_path, converter):
    data = np.random.randint(0, 255, (100, 200), dtype=np.uint8)
    p = _make_tiff(tmp_path / "gray8.tif", data)
    result = converter.inspect(p)
    assert result.format == "TIFF"
    assert result.width == 200
    assert result.height == 100
    assert result.bit_depth == 8


def test_inspect_grayscale_16bit(tmp_path, converter):
    data = np.random.randint(0, 65535, (50, 80), dtype=np.uint16)
    p = _make_tiff(tmp_path / "gray16.tif", data)
    result = converter.inspect(p)
    assert result.bit_depth == 16


def test_convert_grayscale_8bit(tmp_path, converter):
    data = np.random.randint(0, 255, (64, 64), dtype=np.uint8)
    p = _make_tiff(tmp_path / "gray8.tif", data)
    out = tmp_path / "out.jpg"
    converter.convert(p, out, quality=95)
    with Image.open(out) as img:
        assert img.format == "JPEG"
        assert img.size == (64, 64)


def test_convert_grayscale_16bit(tmp_path, converter):
    data = np.random.randint(0, 65535, (64, 64), dtype=np.uint16)
    p = _make_tiff(tmp_path / "gray16.tif", data)
    out = tmp_path / "out.jpg"
    converter.convert(p, out, quality=95)
    with Image.open(out) as img:
        assert img.format == "JPEG"


def test_convert_rgb(tmp_path, converter):
    data = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    p = _make_tiff(tmp_path / "rgb.tif", data)
    out = tmp_path / "out.jpg"
    converter.convert(p, out, quality=95)
    with Image.open(out) as img:
        assert img.format == "JPEG"
        assert img.mode == "RGB"


def test_convert_rgba(tmp_path, converter):
    data = np.random.randint(0, 255, (64, 64, 4), dtype=np.uint8)
    p = _make_tiff(tmp_path / "rgba.tif", data)
    out = tmp_path / "out.jpg"
    converter.convert(p, out, quality=95)
    with Image.open(out) as img:
        assert img.format == "JPEG"
        assert img.mode == "RGB"


def test_multi_page_inspect(tmp_path, converter):
    pages = [np.random.randint(0, 255, (32, 32), dtype=np.uint8) for _ in range(5)]
    p = tmp_path / "multi.tif"
    with tifffile.TiffWriter(str(p)) as tw:
        for page in pages:
            tw.write(page)
    result = converter.inspect(p)
    assert result.pages == 5


def test_multi_page_select(tmp_path, converter):
    pages = [np.zeros((32, 32), dtype=np.uint8) + i * 50 for i in range(3)]
    p = tmp_path / "multi.tif"
    with tifffile.TiffWriter(str(p)) as tw:
        for page in pages:
            tw.write(page)
    out = tmp_path / "out.jpg"
    converter.convert(p, out, page=2, quality=95)
    with Image.open(out) as img:
        assert img.format == "JPEG"


def test_invalid_page(tmp_path, converter):
    data = np.random.randint(0, 255, (32, 32), dtype=np.uint8)
    p = _make_tiff(tmp_path / "single.tif", data)
    with pytest.raises(ValueError):
        converter.convert(p, tmp_path / "out.jpg", page=5)
