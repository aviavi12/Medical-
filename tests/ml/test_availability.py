"""ML honesty-envelope tests.

These are deterministic regardless of what is installed: "unavailable" is forced
by pointing config at missing weights, and "real" paths are skipped when the
downloaded models are absent (so CI without weights still passes).
"""

from __future__ import annotations

import os

import pytest

from ml.common.results import AvailabilityState

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(REPO_ROOT, "models")
HAVE_LIPNET = os.path.exists(os.path.join(MODELS_DIR, "lipnet_overlap.pt")) and os.path.exists(
    os.path.join(MODELS_DIR, "shape_predictor_68_face_landmarks.dat")
)


@pytest.fixture()
def no_mock(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "0")


@pytest.fixture()
def with_mock(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "1")


# ── MODEL_UNAVAILABLE is honest and names the gap (forced via missing weights) ──
def test_lipnet_unavailable_when_weights_missing(no_mock, monkeypatch):
    monkeypatch.setenv("MODELS_DIR", "/nonexistent-models-dir")
    monkeypatch.setenv("LIP_READING_WEIGHTS", "/nonexistent/lipnet.pt")
    monkeypatch.setenv("DLIB_LANDMARKS", "/nonexistent/pred.dat")
    from ml.common.config import get_ml_config
    from ml.lipreading import get_lip_reading_model

    model = get_lip_reading_model(get_ml_config())
    av = model.availability()
    assert av.state == AvailabilityState.MODEL_UNAVAILABLE
    assert av.missing  # names weights / predictor
    # Never fabricates a transcript when unavailable.
    from ml.mouth.sequence import TemporalMouthSequence

    assert model.predict(TemporalMouthSequence(crops=[])).segments == []


def test_tts_unavailable_when_piper_absent(no_mock):
    # Piper is not installed in this environment → honest MODEL_UNAVAILABLE.
    from ml.common.config import get_ml_config
    from ml.tts import get_tts_provider

    av = get_tts_provider(get_ml_config()).availability()
    assert av.state == AvailabilityState.MODEL_UNAVAILABLE


# ── Mock adapters only with the flag, and never look like real transcripts ──
def test_mock_adapters_only_with_flag(with_mock):
    from ml.common.config import get_ml_config
    from ml.detection import get_face_detector, get_person_detector
    from ml.lipreading import get_lip_reading_model

    cfg = get_ml_config()
    assert cfg.allow_mock is True
    assert get_person_detector(cfg).availability().is_real
    assert get_face_detector(cfg).availability().is_real
    assert get_lip_reading_model(cfg).availability().is_real


def test_lipreading_mock_output_is_obviously_synthetic(with_mock):
    from ml.common.config import get_ml_config
    from ml.mouth.sequence import TemporalMouthSequence

    model = get_lip_reading_model_or_skip(get_ml_config())
    result = model.predict(TemporalMouthSequence(crops=[], required_fps=25))
    assert result.segments
    assert "mock" in result.segments[0].text.lower()  # never plausible English (§97)


def get_lip_reading_model_or_skip(cfg):
    from ml.lipreading import get_lip_reading_model

    return get_lip_reading_model(cfg)


# ── Real models are available when the weights are present ──
@pytest.mark.skipif(not HAVE_LIPNET, reason="LipNet weights not downloaded")
def test_lipnet_real_when_weights_present(no_mock):
    from ml.common.config import get_ml_config
    from ml.lipreading import get_lip_reading_model

    model = get_lip_reading_model(get_ml_config())
    av = model.availability()
    assert av.state == AvailabilityState.REAL_RESULT
    assert model.supports_frame_transcription is True
    assert model.get_model_info().name == "lipnet-grid"
