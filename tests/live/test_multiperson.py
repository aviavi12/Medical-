"""Live multi-person test (§34): each selected person is analyzed independently.

A real 2-person, no-audio video is built by placing two different labeled GRID
clips side by side. We assert both people are detected on the correct sides and,
critically, that each person's transcript matches THEIR OWN clip's sentence more
closely than the other person's — proving selection isolates the right person.
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
HAVE = os.path.exists(os.path.join(MODELS_DIR, "lipnet_overlap.pt")) and os.path.exists(
    os.path.join(MODELS_DIR, "shape_predictor_68_face_landmarks.dat")
)
CLIPS = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(GRID_DIR, "*.mpg"))}

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not HAVE, reason="models not downloaded"),
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
    return f"{_CMD[c[0]]} {_COL[c[1]]} {_PREP[c[2]]} {c[3]} {_DIG[c[4]]} {_ADV[c[5]]}".upper()


@pytest.fixture(autouse=True)
def _real(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "0")
    monkeypatch.setenv("LIP_READING_MODEL", "lipnet")  # benchmark model for isolation test
    monkeypatch.setenv("COARSE_FPS", "8")
    monkeypatch.setenv("ANALYSIS_FPS", "25")


def test_select_side_person_analyzes_that_person():
    from training.evaluation import word_error_rate

    from apps.api.config import get_settings
    from apps.api.services import pipeline
    from apps.api.services.storage import get_storage
    from database import models
    from database.base import create_all, get_session_factory, reset_engine_for_tests
    from ml.common.config import get_ml_config

    left_code, right_code = "bbaf2n", "lrwp9a"
    left_truth, right_truth = grid_truth(left_code), grid_truth(right_code)

    work = tempfile.mkdtemp(prefix="mp_")
    os.environ["DATABASE_URL"] = f"sqlite:///{work}/db.sqlite"
    os.environ["STORAGE_PATH"] = f"{work}/storage"
    get_settings.cache_clear()
    reset_engine_for_tests()
    create_all()
    settings, config, storage = get_settings(), get_ml_config(), get_storage(get_settings())
    db = get_session_factory()()

    comp = f"{work}/two.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", CLIPS[left_code], "-i", CLIPS[right_code],
                    "-filter_complex", "hstack", "-an", "-c:v", "libx264", "-r", "25", comp],
                   capture_output=True, check=True)

    key = "mp/original/two.mp4"
    storage.save(key, comp)
    video = models.Video(filename="two.mp4", storage_path=key, status="QUEUED",
                         duration=3.0, width=720, height=288, fps=25, has_audio=False)
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
    assert face_cx(left_person) < 360 < face_cx(right_person), "people not on expected sides"

    def transcript(person):
        pipeline.run_person_analysis(db, video, person, storage, settings, config)
        segs = db.query(models.LipReadingSegment).filter(
            models.LipReadingSegment.person_track_id == person.id).all()
        return " ".join(s.text for s in segs).strip()

    left_pred = transcript(left_person)
    right_pred = transcript(right_person)

    # Each person's transcript must match their OWN clip better than the other's.
    assert word_error_rate(left_pred, left_truth) < word_error_rate(left_pred, right_truth), \
        f"left={left_pred!r} not isolated to {left_truth!r}"
    assert word_error_rate(right_pred, right_truth) < word_error_rate(right_pred, left_truth), \
        f"right={right_pred!r} not isolated to {right_truth!r}"
