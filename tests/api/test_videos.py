"""API tests: upload → validation → metadata → storage → CRUD (Milestone 2)."""

from __future__ import annotations


def _upload(client, path, filename="clear_720p.mp4", content_type="video/mp4"):
    with open(path, "rb") as fh:
        return client.post("/api/videos", files={"file": (filename, fh, content_type)})


def test_upload_real_video_extracts_metadata(client, sample_video):
    r = _upload(client, sample_video)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"]
    assert body["metadata"]["width"] == 1280
    assert body["metadata"]["height"] == 720
    assert body["metadata"]["has_audio"] is False
    assert body["metadata"]["duration"] and body["metadata"]["duration"] > 0
    assert body["media_url"].startswith("/media/")


def test_upload_with_audio_flagged(client, sample_video_with_audio):
    r = _upload(client, sample_video_with_audio, filename="audio.mp4")
    assert r.status_code == 201
    assert r.json()["metadata"]["has_audio"] is True


def test_reject_unsupported_extension(client, sample_video):
    r = _upload(client, sample_video, filename="clip.exe", content_type="application/octet-stream")
    assert r.status_code == 400
    assert "Unsupported" in r.text


def test_reject_empty_file(client, tmp_root):
    empty = tmp_root / "empty.mp4"
    empty.write_bytes(b"")
    with open(empty, "rb") as fh:
        r = client.post("/api/videos", files={"file": ("empty.mp4", fh, "video/mp4")})
    assert r.status_code == 400


def test_list_get_delete_lifecycle(client, sample_video):
    up = _upload(client, sample_video).json()
    vid = up["id"]

    lst = client.get("/api/videos").json()
    assert any(v["id"] == vid for v in lst["videos"])

    assert client.get(f"/api/videos/{vid}").status_code == 200
    assert client.get(f"/api/videos/{vid}/status").status_code == 200

    assert client.delete(f"/api/videos/{vid}").status_code == 204
    assert client.get(f"/api/videos/{vid}").status_code == 404


def test_media_serving(client, sample_video):
    up = _upload(client, sample_video).json()
    r = client.get(up["media_url"])
    assert r.status_code == 200
    assert len(r.content) > 0
