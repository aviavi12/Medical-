"""Live tests: real LipNet visual speech recognition on labeled GRID clips.

Requires the downloaded models + GRID fixtures (scripts/download_models.py); the
whole module is skipped otherwise, so CI without weights still passes. These are
the real WER/CER (§16) and no-audio acceptance (§13/§14) tests.
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

HAVE_MODELS = os.path.exists(os.path.join(MODELS_DIR, "lipnet_overlap.pt")) and os.path.exists(
    os.path.join(MODELS_DIR, "shape_predictor_68_face_landmarks.dat")
)
GRID_CLIPS = sorted(glob.glob(os.path.join(GRID_DIR, "*.mpg")))

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not HAVE_MODELS, reason="models not downloaded (scripts/download_models.py)"),
    pytest.mark.skipif(not GRID_CLIPS, reason="GRID fixtures not present"),
]


@pytest.fixture(autouse=True)
def _force_real_inference(monkeypatch):
    # conftest enables mock ML globally; live tests must exercise the real models.
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "0")

_CMD = {"b": "bin", "l": "lay", "p": "place", "s": "set"}
_COL = {"b": "blue", "g": "green", "r": "red", "w": "white"}
_PREP = {"a": "at", "b": "by", "i": "in", "w": "with"}
_DIG = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
        "6": "six", "7": "seven", "8": "eight", "9": "nine", "z": "zero"}
_ADV = {"a": "again", "n": "now", "p": "please", "s": "soon"}


def grid_truth(code: str) -> str:
    c = code.lower()
    return f"{_CMD[c[0]]} {_COL[c[1]]} {_PREP[c[2]]} {c[3]} {_DIG[c[4]]} {_ADV[c[5]]}".upper()


def _frames(path):
    import cv2

    cap = cv2.VideoCapture(path)
    out = []
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        out.append((i / 25.0, f, None))
        i += 1
    cap.release()
    return out


def test_lipnet_grid_wer():
    """Aggregate WER/CER across all labeled GRID clips must be low (real eval)."""
    from training.evaluation import evaluate

    from ml.common.config import get_ml_config
    from ml.lipreading import get_lip_reading_model

    model = get_lip_reading_model(get_ml_config())
    assert model.availability().is_real

    preds, refs = [], []
    for clip in GRID_CLIPS:
        code = os.path.splitext(os.path.basename(clip))[0]
        res = model.transcribe(_frames(clip))
        assert res.availability.is_real
        preds.append(res.segments[0].text if res.segments else "")
        refs.append(grid_truth(code))

    result = evaluate(preds, refs)
    # Measured ≈0.017; assert a comfortable ceiling so a real regression is caught.
    assert result.wer < 0.12, f"WER too high: {result.wer} preds={preds}"
    assert result.cer < 0.05
    assert result.sentence_accuracy >= 0.7


def test_no_audio_pipeline_end_to_end():
    """Strip audio, run the full pipeline, and check the transcript matches the
    ground truth — proving the transcript is visual-only (§13/§14)."""
    clip = GRID_CLIPS[0]
    code = os.path.splitext(os.path.basename(clip))[0]
    truth = grid_truth(code)

    work = tempfile.mkdtemp(prefix="live_")
    os.environ["DATABASE_URL"] = f"sqlite:///{work}/db.sqlite"
    os.environ["STORAGE_PATH"] = f"{work}/storage"
    os.environ["ALLOW_MOCK_INFERENCE"] = "0"
    os.environ["COARSE_FPS"] = "8"
    os.environ["ANALYSIS_FPS"] = "25"

    from apps.api.config import get_settings
    from apps.api.services import pipeline
    from apps.api.services.storage import get_storage
    from database import models
    from database.base import create_all, get_session_factory, reset_engine_for_tests
    from ml.common.config import get_ml_config

    get_settings.cache_clear()
    reset_engine_for_tests()
    create_all()
    settings = get_settings()
    config = get_ml_config()
    storage = get_storage(settings)
    db = get_session_factory()()

    noaudio = f"{work}/noaudio.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", clip, "-an", "-c:v", "libx264", "-r", "25", noaudio],
                   capture_output=True, check=True)
    # Prove there is no audio stream.
    astreams = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", noaudio], capture_output=True, text=True).stdout.strip()
    assert astreams == ""

    key = "live/original/noaudio.mp4"
    storage.save(key, noaudio)
    video = models.Video(filename="noaudio.mp4", storage_path=key, status="QUEUED",
                         duration=3.0, width=360, height=288, fps=25, has_audio=False)
    db.add(video)
    db.commit()
    db.refresh(video)

    pipeline.run_coarse_scan(db, video, storage, settings, config)
    people = db.query(models.PersonTrack).filter(models.PersonTrack.video_id == video.id).all()
    assert people, "no person detected from a clear face"

    person = max(people, key=lambda p: p.lip_readiness_score)
    result = pipeline.run_person_analysis(db, video, person, storage, settings, config)
    assert result["state"] == "REAL_RESULT", result
    segs = db.query(models.LipReadingSegment).filter(
        models.LipReadingSegment.person_track_id == person.id).all()
    assert segs
    assert segs[0].model_version and "lipnet" in segs[0].model_version
    transcript = " ".join(s.text for s in segs).strip()

    from training.evaluation import word_error_rate
    assert word_error_rate(transcript, truth) == 0.0, f"{transcript!r} != {truth!r}"
