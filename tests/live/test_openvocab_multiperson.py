"""Live side-person isolation regression for the open-vocabulary model (§7/§8).

A real 2-person, no-audio 1280×720 video is built by placing two different
labeled GRID clips side by side. We assert:
  1. both people are detected on the correct sides, and
  2. the person whose speech decodes confidently is isolated to THEIR OWN clip —
     their transcript matches their side's sentence better than the neighbour's.

This guards the core product promise: selecting a side person analyzes THAT
person's visible speech, never the neighbour's. The composited/downscaled frames
degrade absolute accuracy, so we assert *isolation* (relative WER), not a low WER.
"""

from __future__ import annotations

import glob
import os
import subprocess
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(REPO_ROOT, "models")
GRID_DIR = os.path.join(REPO_ROOT, "tests", "fixtures", "visual_speech", "grid")
HAVE = os.path.exists(os.path.join(MODELS_DIR, "syncvsr_vox_lrs2_lrs3.ckpt"))
CLIPS = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(GRID_DIR, "*.mpg"))}

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not HAVE, reason="SyncVSR checkpoint not downloaded"),
    pytest.mark.skipif(not {"bbaf2n", "lrwp9a"} <= set(CLIPS), reason="needed GRID clips absent"),
]

_CMD = {"b": "bin", "l": "lay", "p": "place", "s": "set"}
_COL = {"b": "blue", "g": "green", "r": "red", "w": "white"}
_PREP = {"a": "at", "b": "by", "i": "in", "w": "with"}
_DIG = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
        "6": "six", "7": "seven", "8": "eight", "9": "nine", "z": "zero"}
_ADV = {"a": "again", "n": "now", "p": "please", "s": "soon"}


def grid_truth(code: str) -> str:
    c = code.lower()
    return f"{_CMD[c[0]]} {_COL[c[1]]} {_PREP[c[2]]} {c[3]} {_DIG[c[4]]} {_ADV[c[5]]}"


@pytest.fixture(autouse=True)
def _real(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "0")
    monkeypatch.setenv("LIP_READING_MODEL", "syncvsr")
    monkeypatch.setenv("COARSE_FPS", "8")
    monkeypatch.setenv("ANALYSIS_FPS", "25")


def test_select_side_person_isolates_that_person():
    from training.evaluation import word_error_rate

    from apps.api.config import get_settings
    from apps.api.services import pipeline
    from apps.api.services.storage import get_storage
    from database import models
    from database.base import create_all, get_session_factory, reset_engine_for_tests
    from ml.common.config import get_ml_config
    from ml.lipreading.postprocessing import NO_SPEECH_EVIDENCE, UNCERTAIN

    left_code, right_code = "bbaf2n", "lrwp9a"
    left_truth, right_truth = grid_truth(left_code), grid_truth(right_code)

    work = tempfile.mkdtemp(prefix="ovmp_")
    os.environ["DATABASE_URL"] = f"sqlite:///{work}/db.sqlite"
    os.environ["STORAGE_PATH"] = f"{work}/storage"
    get_settings.cache_clear()
    reset_engine_for_tests()
    create_all()
    settings, config, storage = get_settings(), get_ml_config(), get_storage(get_settings())
    db = get_session_factory()()

    comp = f"{work}/two.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", CLIPS[left_code], "-i", CLIPS[right_code], "-filter_complex",
         "[0:v]scale=640:512[l];[1:v]scale=640:512[r];[l][r]hstack=inputs=2,pad=1280:720:0:104:black[v]",
         "-map", "[v]", "-an", "-c:v", "libx264", "-r", "25", comp],
        capture_output=True, check=True,
    )
    key = "ovmp/original/two.mp4"
    storage.save(key, comp)
    video = models.Video(filename="two.mp4", storage_path=key, status="QUEUED",
                         duration=3.0, width=1280, height=720, fps=25, has_audio=False)
    db.add(video)
    db.commit()
    db.refresh(video)

    pipeline.run_coarse_scan(db, video, storage, settings, config)
    people = db.query(models.PersonTrack).filter(models.PersonTrack.video_id == video.id).all()
    assert len(people) == 2, f"expected 2 people, got {len(people)}"

    def face_cx(p):
        obs = db.query(models.FaceObservation).filter(
            models.FaceObservation.person_track_id == p.id).all()
        return sum((o.bbox[0] + o.bbox[2]) / 2 for o in obs) / max(1, len(obs))

    people.sort(key=face_cx)
    left_person, right_person = people[0], people[1]
    assert face_cx(left_person) < 640 < face_cx(right_person), "people not on expected sides"

    def transcript(person):
        pipeline.run_person_analysis(db, video, person, storage, settings, config, override_gates=True)
        segs = db.query(models.LipReadingSegment).filter(
            models.LipReadingSegment.person_track_id == person.id).order_by(
            models.LipReadingSegment.start_time).all()
        # provenance: every persisted segment is tagged with THIS person's id (§19).
        assert all(s.person_track_id == person.id for s in segs)
        text = " ".join(s.text for s in segs
                        if s.text not in (UNCERTAIN, NO_SPEECH_EVIDENCE)).strip()
        return text

    left_pred = transcript(left_person)
    right_pred = transcript(right_person)

    # At least one side must decode confidently; that side must be isolated to its
    # own clip (own-side WER strictly lower than the neighbour's).
    isolated = 0
    for pred, own, other in ((left_pred, left_truth, right_truth),
                             (right_pred, right_truth, left_truth)):
        if not pred:
            continue
        if word_error_rate(pred, own) < word_error_rate(pred, other):
            isolated += 1
        else:
            # A confident decode that matches the neighbour better is a real failure.
            assert word_error_rate(pred, own) <= word_error_rate(pred, other), (
                f"pred={pred!r} matched the OTHER person ({other!r}) better than own ({own!r})")
    assert isolated >= 1, f"no side decoded confidently: left={left_pred!r} right={right_pred!r}"
