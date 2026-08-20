"""ML honesty-envelope tests: MODEL_UNAVAILABLE names the exact missing dep, and
mock adapters are only used when explicitly allowed."""

from __future__ import annotations

import os

import pytest

from ml.common.results import AvailabilityState
from ml.detection import get_face_detector, get_person_detector
from ml.landmarks import get_landmarker
from ml.lipreading import get_lip_reading_model
from ml.tts import get_tts_provider


@pytest.fixture()
def no_mock(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "0")
    yield


@pytest.fixture()
def with_mock(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_INFERENCE", "1")
    yield


def test_person_detector_unavailable_names_missing(no_mock):
    from ml.common.config import get_ml_config

    det = get_person_detector(get_ml_config())
    av = det.availability()
    # In this environment ultralytics/torch are absent → MODEL_UNAVAILABLE.
    assert av.state == AvailabilityState.MODEL_UNAVAILABLE
    assert av.missing  # names what is missing
    assert det.detect(None) == []  # never fabricates detections


def test_lipreading_unavailable_is_honest(no_mock):
    from ml.common.config import get_ml_config

    model = get_lip_reading_model(get_ml_config())
    av = model.availability()
    assert av.state == AvailabilityState.MODEL_UNAVAILABLE
    assert "non-commercial" in (av.detail or "").lower() or av.missing


def test_landmarker_and_tts_unavailable(no_mock):
    from ml.common.config import get_ml_config

    assert get_landmarker(get_ml_config()).availability().state == AvailabilityState.MODEL_UNAVAILABLE
    assert get_tts_provider(get_ml_config()).availability().state == AvailabilityState.MODEL_UNAVAILABLE


def test_mock_adapters_only_with_flag(with_mock):
    from ml.common.config import get_ml_config

    cfg = get_ml_config()
    assert cfg.allow_mock is True
    assert get_person_detector(cfg).availability().is_real
    assert get_face_detector(cfg).availability().is_real
    assert get_lip_reading_model(cfg).availability().is_real


def test_lipreading_mock_output_is_obviously_synthetic(with_mock):
    from ml.common.config import get_ml_config
    from ml.mouth.sequence import TemporalMouthSequence

    model = get_lip_reading_model(get_ml_config())
    result = model.predict(TemporalMouthSequence(crops=[], required_fps=25))
    # Mock must never look like a real English transcript (§97).
    assert result.segments
    assert "mock" in result.segments[0].text.lower()
