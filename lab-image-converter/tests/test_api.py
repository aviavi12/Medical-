import io
import numpy as np
import tifffile
from PIL import Image


def _make_png_bytes(width=64, height=64):
    img = Image.new("RGB", (width, height), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(width=64, height=64):
    img = Image.new("RGB", (width, height), (0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_tiff_bytes(width=64, height=64, dtype=np.uint8):
    data = np.random.randint(0, 255, (height, width, 3), dtype=dtype)
    buf = io.BytesIO()
    tifffile.imwrite(buf, data)
    return buf.getvalue()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_inspect_png(client):
    data = _make_png_bytes()
    resp = client.post("/api/inspect", files={"file": ("test.png", data, "image/png")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "PNG"
    assert body["width"] == 64
    assert body["height"] == 64


def test_inspect_jpeg(client):
    data = _make_jpeg_bytes()
    resp = client.post("/api/inspect", files={"file": ("test.jpg", data, "image/jpeg")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "JPEG"


def test_inspect_tiff(client):
    data = _make_tiff_bytes()
    resp = client.post(
        "/api/inspect", files={"file": ("test.tif", data, "image/tiff")}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "TIFF"


def test_inspect_unsupported(client):
    resp = client.post(
        "/api/inspect",
        files={"file": ("test.xyz", b"random data", "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_convert_png(client):
    data = _make_png_bytes()
    resp = client.post(
        "/api/convert",
        files={"file": ("test.png", data, "image/png")},
        data={"quality": "95"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["filename"].endswith(".jpg")
    assert body["download_url"].startswith("/api/download/")


def test_convert_jpeg(client):
    data = _make_jpeg_bytes()
    resp = client.post(
        "/api/convert",
        files={"file": ("photo.jpeg", data, "image/jpeg")},
        data={"quality": "90"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


def test_convert_tiff(client):
    data = _make_tiff_bytes()
    resp = client.post(
        "/api/convert",
        files={"file": ("scan.tif", data, "image/tiff")},
        data={"quality": "95"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


def test_convert_unsupported(client):
    resp = client.post(
        "/api/convert",
        files={"file": ("test.bmp", b"\x42\x4d" + b"\x00" * 100, "image/bmp")},
        data={"quality": "95"},
    )
    assert resp.status_code == 400


def test_download_success(client):
    data = _make_png_bytes()
    resp = client.post(
        "/api/convert",
        files={"file": ("test.png", data, "image/png")},
        data={"quality": "95"},
    )
    body = resp.json()
    dl_resp = client.get(body["download_url"])
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "image/jpeg"


def test_download_not_found(client):
    resp = client.get("/api/download/nonexistent")
    assert resp.status_code == 404


def test_convert_tiff_16bit(client):
    data = _make_tiff_bytes(dtype=np.uint16)
    resp = client.post(
        "/api/convert",
        files={"file": ("micro.tiff", data, "image/tiff")},
        data={"quality": "95"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
