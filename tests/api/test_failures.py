"""API tests: failure handling (§64, §87)."""

from __future__ import annotations


def test_corrupted_video_rejected(client, corrupted_video):
    with open(corrupted_video, "rb") as fh:
        r = client.post("/api/videos", files={"file": ("corrupted.mp4", fh, "video/mp4")})
    # ffprobe cannot read it → clear 400, not a fabricated success.
    assert r.status_code == 400


def test_missing_model_reports_unavailable(client, sample_video, monkeypatch):
    """With mock inference OFF, analysis fails honestly naming the missing model."""
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "0")
    with open(sample_video, "rb") as fh:
        up = client.post("/api/videos", files={"file": ("clear.mp4", fh, "video/mp4")}).json()
    vid = up["id"]

    client.post(f"/api/videos/{vid}/analyze")
    status = client.get(f"/api/videos/{vid}/status").json()
    assert status["status"] == "FAILED"
    assert status["error"]  # names the missing dependency
    assert "unavailable" in status["error"].lower() or "install" in status["error"].lower()


def test_get_unknown_video_404(client):
    assert client.get("/api/videos/does-not-exist").status_code == 404
