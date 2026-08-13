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


# --- Batch conversion tests ---


def test_batch_convert_multiple_files(client):
    png = _make_png_bytes()
    jpg = _make_jpeg_bytes()
    tif = _make_tiff_bytes()
    resp = client.post(
        "/api/convert-batch",
        files=[
            ("files", ("img1.png", png, "image/png")),
            ("files", ("img2.jpg", jpg, "image/jpeg")),
            ("files", ("img3.tif", tif, "image/tiff")),
        ],
        data={"quality": "95"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["succeeded"] == 3
    assert body["failed"] == 0
    assert len(body["files"]) == 3
    for f in body["files"]:
        assert f["success"] is True
        assert f["download_url"].startswith("/api/download/")


def test_batch_convert_with_unsupported_file(client):
    png = _make_png_bytes()
    resp = client.post(
        "/api/convert-batch",
        files=[
            ("files", ("good.png", png, "image/png")),
            ("files", ("bad.xyz", b"not an image", "application/octet-stream")),
        ],
        data={"quality": "95"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["succeeded"] == 1
    assert body["failed"] == 1
    assert body["files"][0]["success"] is True
    assert body["files"][1]["success"] is False


def test_batch_convert_download_all_zip(client):
    png1 = _make_png_bytes(32, 32)
    png2 = _make_png_bytes(48, 48)
    resp = client.post(
        "/api/convert-batch",
        files=[
            ("files", ("a.png", png1, "image/png")),
            ("files", ("b.png", png2, "image/png")),
        ],
        data={"quality": "90"},
    )
    body = resp.json()
    assert body["download_all_url"] is not None

    dl = client.get(body["download_all_url"])
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/zip"


def test_batch_convert_with_output_directory(client, tmp_path):
    png = _make_png_bytes()
    out_dir = str(tmp_path / "my_output")
    resp = client.post(
        "/api/convert-batch",
        files=[("files", ("sample.png", png, "image/png"))],
        data={"quality": "95", "output_directory": out_dir},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["succeeded"] == 1
    assert body["output_directory"] == out_dir

    from pathlib import Path
    out = Path(out_dir)
    jpgs = list(out.glob("*.jpg"))
    assert len(jpgs) == 1


def test_batch_convert_single_file_no_zip(client):
    png = _make_png_bytes()
    resp = client.post(
        "/api/convert-batch",
        files=[("files", ("one.png", png, "image/png"))],
        data={"quality": "95"},
    )
    body = resp.json()
    assert body["succeeded"] == 1
    assert body["download_all_url"] is None


def test_batch_download_all_not_found(client):
    resp = client.get("/api/download-all/nonexistent")
    assert resp.status_code == 404
