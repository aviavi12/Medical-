"""API tests: health + system info (Milestone 1)."""

from __future__ import annotations


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"]
    assert body["database"] == "sqlite"
    assert body["ffmpeg"] is True  # ffmpeg installed in this environment
    assert body["device"]["device"] in ("cpu", "cuda", "mps")


def test_root_and_docs(client):
    assert client.get("/").status_code == 200
    assert client.get("/openapi.json").status_code == 200
