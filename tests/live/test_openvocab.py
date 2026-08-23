"""Live tests for the real open-vocabulary VSR model (SyncVSR).

Skipped unless the 1.14 GB checkpoint is present. Verifies the model is genuinely
open-vocabulary, runs visual-only, and actually reads lips (a near-correct
transcript on a clip with zero training overlap).
"""

from __future__ import annotations

import glob
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(REPO_ROOT, "models")
GRID_DIR = os.path.join(REPO_ROOT, "tests", "fixtures", "visual_speech", "grid")
CKPT = os.path.join(MODELS_DIR, "syncvsr_vox_lrs2_lrs3.ckpt")
HAVE = os.path.exists(CKPT)
CLIPS = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(GRID_DIR, "*.mpg"))}

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not HAVE, reason="SyncVSR checkpoint not downloaded"),
    pytest.mark.skipif("lrwp9a" not in CLIPS, reason="GRID fixture missing"),
]


@pytest.fixture(autouse=True)
def _real(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "0")
    monkeypatch.setenv("LIP_READING_MODEL", "syncvsr")


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


def test_openvocab_is_open_vocabulary_and_real():
    from ml.common.config import get_ml_config
    from ml.lipreading import get_lip_reading_model

    model = get_lip_reading_model(get_ml_config())
    assert model.availability().is_real
    assert model.supports_frame_transcription is True
    model.load()
    # Open vocabulary: thousands of subword tokens, not a 28-char closed set.
    assert len(model._model.token_list) > 1000  # unigram5000
    info = model.get_model_info()
    assert "open" in info.configuration["vocabulary"].lower()
    assert info.name == "syncvsr-vox-lrs2-lrs3"


def test_openvocab_reads_lips_zero_overlap():
    """On a GRID clip (no training overlap), the open-vocab model must produce a
    near-correct free-form transcript — proving it reads lips, not memorises."""
    from training.evaluation import word_error_rate

    from ml.common.config import get_ml_config
    from ml.lipreading import get_lip_reading_model

    model = get_lip_reading_model(get_ml_config())
    res = model.transcribe(_frames(CLIPS["lrwp9a"]))  # "lay red with p nine again"
    assert res.availability.is_real
    assert res.segments and res.segments[0].text
    wer = word_error_rate(res.segments[0].text, "lay red with p nine again")
    # Measured ~0.17; assert a comfortable ceiling (natural sentences do better).
    assert wer < 0.5, f"WER {wer}: {res.segments[0].text!r}"


def test_openvocab_transcribe_takes_only_frames():
    """Structural guarantee: the visual model's entry point accepts frames only —
    there is no audio/subtitle/text parameter (Phase 4/14)."""
    import inspect

    from ml.common.config import get_ml_config
    from ml.lipreading import get_lip_reading_model

    model = get_lip_reading_model(get_ml_config())
    params = list(inspect.signature(model.transcribe).parameters)
    assert params == ["frames"]
