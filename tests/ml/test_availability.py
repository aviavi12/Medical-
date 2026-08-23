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
    monkeypatch.setenv("LIP_READING_MODEL", "lipnet")
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


def test_tts_unavailable_for_unknown_provider(no_mock, monkeypatch):
    # An unconfigured provider reports MODEL_UNAVAILABLE (deterministic).
    monkeypatch.setenv("TTS_PROVIDER", "does-not-exist")
    from ml.common.config import get_ml_config
    from ml.tts import get_tts_provider

    assert get_tts_provider(get_ml_config()).availability().state == AvailabilityState.MODEL_UNAVAILABLE


def test_tts_espeak_real_when_installed(no_mock, tmp_path):
    # eSpeak NG is a real, offline generic voice; available when the binary is present.
    import shutil
    import wave

    import pytest as _pytest

    from ml.common.config import get_ml_config
    from ml.tts import get_tts_provider
    from ml.tts.base import VoicePermissionError

    provider = get_tts_provider(get_ml_config())
    av = provider.availability()
    if not (shutil.which("espeak-ng") or shutil.which("espeak")):
        assert av.state == AvailabilityState.MODEL_UNAVAILABLE
        return

    assert av.state == AvailabilityState.REAL_RESULT
    # Transcript → real synthetic audio (M13).
    out = tmp_path / "out.wav"
    art = provider.synthesize("bin blue at f two now", out, voice="generic")
    assert out.exists() and out.stat().st_size > 0
    with wave.open(str(out)) as wf:
        assert wf.getnframes() > 0  # real audio, not silence-only
    assert "Synthetic audio" in art.label
    # A non-generic voice requires explicit permission (§43).
    with _pytest.raises(VoicePermissionError):
        provider.synthesize("x", out, voice="someone_real", authorized_voice_confirmation=False)


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
def test_lipnet_real_when_weights_present(no_mock, monkeypatch):
    monkeypatch.setenv("LIP_READING_MODEL", "lipnet")  # benchmark model
    from ml.common.config import get_ml_config
    from ml.lipreading import get_lip_reading_model

    model = get_lip_reading_model(get_ml_config())
    av = model.availability()
    assert av.state == AvailabilityState.REAL_RESULT
    assert model.supports_frame_transcription is True
    assert model.get_model_info().name == "lipnet-grid"
