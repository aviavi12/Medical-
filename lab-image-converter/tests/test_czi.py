"""
CZI converter tests.

Real CZI files are required for full integration testing.
Place .czi test fixtures in tests/fixtures/czi/ and uncomment
the integration tests below.

Without real CZI files, we test that the CZI converter class
is properly structured and importable. The unit tests verify
that the supporting image processing pipeline (normalization,
array conversion, JPEG encoding) works correctly — those are
covered in test_jpeg.py and test_tiff.py.

To add a real CZI fixture:
1. Copy a .czi file into tests/fixtures/czi/
2. Uncomment the integration tests below
3. Adjust expected dimensions to match your file
"""
import pytest
from pathlib import Path

from app.converters.czi_converter import CZIConverter


@pytest.fixture
def converter():
    return CZIConverter()


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures" / "czi"


def test_converter_has_inspect(converter):
    assert hasattr(converter, "inspect")
    assert callable(converter.inspect)


def test_converter_has_convert(converter):
    assert hasattr(converter, "convert")
    assert callable(converter.convert)


def test_czi_fixture_dir_exists(fixtures_dir):
    assert fixtures_dir.exists(), (
        "CZI fixtures directory missing. "
        "Create tests/fixtures/czi/ and add .czi test files."
    )


# --- Integration tests (uncomment when fixtures are available) ---
#
# def test_inspect_real_czi(converter, fixtures_dir):
#     czi_files = list(fixtures_dir.glob("*.czi"))
#     if not czi_files:
#         pytest.skip("No CZI fixture files available")
#     result = converter.inspect(czi_files[0])
#     assert result.format == "CZI"
#     assert result.width > 0
#     assert result.height > 0
#
#
# def test_convert_real_czi(converter, fixtures_dir, tmp_path):
#     czi_files = list(fixtures_dir.glob("*.czi"))
#     if not czi_files:
#         pytest.skip("No CZI fixture files available")
#     out = tmp_path / "output.jpg"
#     converter.convert(czi_files[0], out, quality=95)
#     assert out.exists()
#     from PIL import Image
#     with Image.open(out) as img:
#         assert img.format == "JPEG"
