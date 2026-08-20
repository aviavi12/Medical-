"""End-to-end pipeline test (§86), run with mock ML adapters.

upload → metadata → detection → tracking → gallery → select person →
mouth extraction → lip reading → gaze → transcript → export → tts.

The mock adapters are deterministic and clearly synthetic; this verifies the
plumbing and honesty envelope end to end, not model accuracy.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_full_flow(client, sample_video):
    # 1. upload
    with open(sample_video, "rb") as fh:
        up = client.post("/api/videos", files={"file": ("clear.mp4", fh, "video/mp4")})
    assert up.status_code == 201
    vid = up.json()["id"]

    # 2. coarse scan (Stage A)
    assert client.post(f"/api/videos/{vid}/analyze").status_code == 202
    status = client.get(f"/api/videos/{vid}/status").json()
    assert status["status"] == "READY_FOR_SELECTION", status

    # 3. person gallery — mock yields multiple people, incl. one near the edge
    people = client.get(f"/api/videos/{vid}/people").json()
    assert people["status"] == "READY_FOR_SELECTION"
    assert len(people["people"]) >= 2
    selectable = [p for p in people["people"] if p["selectable"]]
    assert selectable, people["people"]
    person = selectable[0]
    pid = person["id"]
    assert person["thumbnail_url"]  # thumbnail generated
    assert person["lip_readiness"] >= 0

    # 4. Stage B analysis for the selected person
    res = client.post(f"/api/videos/{vid}/people/{pid}/analyze").json()
    assert res["state"] == "REAL_RESULT", res
    assert res["segments"] >= 1
    assert res["gaze"] >= 1

    # 5. transcript synchronised + honest availability + uncertainty fields
    tr = client.get(f"/api/videos/{vid}/people/{pid}/transcript").json()
    assert tr["availability"]["state"] == "REAL_RESULT"
    assert tr["segments"]
    assert "mock" in tr["segments"][0]["text"].lower()  # never a fake English sentence

    # 6. gaze timeline
    gz = client.get(f"/api/videos/{vid}/people/{pid}/gaze").json()
    assert gz["segments"]

    # 7. exports
    for fmt in ("srt", "txt", "json", "report"):
        r = client.get(f"/api/videos/{vid}/people/{pid}/export/{fmt}")
        assert r.status_code == 200, (fmt, r.text)
        assert r.content

    # 8. optional generic TTS (mock writes a real WAV placeholder)
    tts = client.post(f"/api/videos/{vid}/people/{pid}/tts", json={"voice": "generic"}).json()
    assert tts["availability"]["state"] == "REAL_RESULT"
    assert "Synthetic audio" in tts["label"]
    assert tts["url"]

    # 9. cleanup / privacy
    assert client.delete(f"/api/videos/{vid}").status_code == 204


def test_tts_blocks_unauthorized_voice(client, sample_video):
    with open(sample_video, "rb") as fh:
        vid = client.post("/api/videos", files={"file": ("clear.mp4", fh, "video/mp4")}).json()["id"]
    client.post(f"/api/videos/{vid}/analyze")
    people = client.get(f"/api/videos/{vid}/people").json()["people"]
    pid = next(p["id"] for p in people if p["selectable"])
    client.post(f"/api/videos/{vid}/people/{pid}/analyze")

    # A non-generic voice without explicit permission is rejected (§43).
    r = client.post(
        f"/api/videos/{vid}/people/{pid}/tts",
        json={"voice": "someone_real", "authorized_voice_confirmation": False},
    )
    assert r.status_code == 400
    assert "permission" in r.text.lower()
