"""API tests: failure handling (§64, §87)."""

from __future__ import annotations


def test_corrupted_video_rejected(client, corrupted_video):
    with open(corrupted_video, "rb") as fh:
        r = client.post("/api/videos", files={"file": ("corrupted.mp4", fh, "video/mp4")})
    # ffprobe cannot read it → clear 400, not a fabricated success.
    assert r.status_code == 400


def test_missing_model_reports_unavailable(monkeypatch):
    """When lip-reading weights are absent, the model reports MODEL_UNAVAILABLE
    naming the gap — it never fabricates a transcript (§31, §93)."""
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "0")
    monkeypatch.setenv("MODELS_DIR", "/nonexistent-models-dir")
    monkeypatch.setenv("LIP_READING_WEIGHTS", "/nonexistent/lipnet.pt")
    monkeypatch.setenv("DLIB_LANDMARKS", "/nonexistent/pred.dat")
    from ml.common.config import get_ml_config
    from ml.common.results import AvailabilityState
    from ml.lipreading import get_lip_reading_model

    av = get_lip_reading_model(get_ml_config()).availability()
    assert av.state == AvailabilityState.MODEL_UNAVAILABLE
    assert av.missing
    assert "install" in (av.detail or "").lower() or "download" in (av.detail or "").lower()


def test_get_unknown_video_404(client):
    assert client.get("/api/videos/does-not-exist").status_code == 404
