"""Unit tests: postprocessing uncertainty, gaze classification, sampling timestamps."""

from __future__ import annotations

from ml.common.types import BBox, GazeDirection, LipReadingSegment
from ml.gaze import get_gaze_estimator
from ml.landmarks.mock_landmarker import MockLandmarker
from ml.lipreading.postprocessing import UNCERTAIN, apply_postprocessing, mask_low_confidence


def test_low_confidence_is_masked_as_uncertain():
    seg = LipReadingSegment(0.0, 1.0, "some words", confidence=0.2)
    out = mask_low_confidence(seg, threshold=0.5)
    assert out.text == UNCERTAIN
    assert out.raw_text == "some words"  # raw preserved for transparency


def test_high_confidence_is_kept_and_cleaned():
    seg = LipReadingSegment(0.0, 1.0, "hello world", confidence=0.9)
    out = apply_postprocessing([seg], threshold=0.5)[0]
    assert out.text == "hello world"
    assert out.processed_text.endswith(".")
    assert out.processed_text[0].isupper()


def test_gaze_unknown_without_landmarks():
    est = get_gaze_estimator()
    result = est.estimate(None, timestamp=1.0)
    assert result.direction == GazeDirection.UNKNOWN
    assert result.availability is not None
    assert not result.availability.is_available


def test_gaze_classifies_with_mock_landmarks():
    est = get_gaze_estimator()
    lm = MockLandmarker().landmarks(None, BBox(100, 100, 292, 292))
    result = est.estimate(lm, timestamp=1.0)
    assert result.direction in set(GazeDirection)
    assert result.head_pose is not None
    assert result.availability.is_available


def test_gaze_toward_another_person_is_possible_not_certain():
    est = get_gaze_estimator()
    from ml.common.types import GazeResult, HeadPose

    gaze = GazeResult(timestamp=0.0, direction=GazeDirection.RIGHT, confidence=0.8,
                      head_pose=HeadPose(20, 0, 0, 0.6))
    src = BBox(100, 100, 200, 200)
    others = [(4, BBox(500, 100, 600, 200))]  # to the right
    pid, conf = est.gaze_toward(src, gaze, others)
    assert pid == 4
    assert conf <= 0.75  # capped: 'possible', never certainty


def test_sampling_preserves_timestamps(sample_video):
    from ml.common.sampling import FrameSampler

    sampler = FrameSampler(target_fps=4.0)
    frames = list(sampler.iter_frames(sample_video, decode=False))
    assert len(frames) > 0
    # timestamps strictly increasing and consistent with source frame indices
    ts = [f.timestamp_seconds for f in frames]
    assert ts == sorted(ts)
    assert frames[0].sample_index == 0
    # sampled index differs from source frame index (subsampling happened)
    assert frames[-1].source_frame_index >= frames[-1].sample_index
