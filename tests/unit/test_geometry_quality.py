"""Unit tests: geometry, quality scoring, readiness weights, quality gates."""

from __future__ import annotations

import numpy as np

from ml.common.config import QualityGates, ReadinessWeights
from ml.common.types import BBox
from ml.quality.face_quality import FaceQualityEstimator
from ml.quality.readiness import PersonAggregate, lip_reading_readiness, passes_quality_gates


def test_bbox_iou_and_containment():
    a = BBox(0, 0, 10, 10)
    b = BBox(0, 0, 10, 10)
    assert a.iou(b) == 1.0
    c = BBox(5, 5, 15, 15)
    assert 0 < a.iou(c) < 1
    inner = BBox(2, 2, 4, 4)
    assert a.contains_fraction(inner) == 1.0  # fully inside
    assert a.area == 100


def test_bbox_roundtrip():
    a = BBox(1, 2, 3, 4)
    assert BBox.from_list(a.as_list()) == a


def test_readiness_weights_normalize_to_one():
    w = ReadinessWeights().normalized()
    assert abs(w.total() - 1.0) < 1e-9


def test_readiness_score_monotonic():
    low = PersonAggregate(face_quality=30, mouth_visibility=0.2, face_resolution=0.2,
                          tracking_stability=0.2, pose_quality=0.2, sharpness=0.2)
    high = PersonAggregate(face_quality=95, mouth_visibility=0.9, face_resolution=0.9,
                           tracking_stability=0.9, pose_quality=0.9, sharpness=0.9)
    assert lip_reading_readiness(low) < lip_reading_readiness(high)
    assert 0 <= lip_reading_readiness(high) <= 100


def test_quality_gates_fail_and_pass():
    gates = QualityGates(min_face_width=80, min_face_quality=60, min_mouth_visibility=0.6,
                         min_tracking_stability=0.6)
    ok, failures = passes_quality_gates(face_width=40, face_quality=50, mouth_visibility=0.3,
                                        tracking_stability=0.3, gates=gates)
    assert not ok and len(failures) == 4

    ok2, failures2 = passes_quality_gates(face_width=120, face_quality=80, mouth_visibility=0.8,
                                          tracking_stability=0.8, gates=gates)
    assert ok2 and failures2 == []


def test_quality_gate_override_records_failures_but_passes():
    gates = QualityGates()
    ok, failures = passes_quality_gates(face_width=10, face_quality=10, mouth_visibility=0.1,
                                        tracking_stability=0.1, gates=gates, override=True)
    assert ok is True
    assert failures  # still reported


def test_face_quality_real_metrics_on_synthetic_frame():
    # A sharp, well-lit synthetic frame should score higher than a flat gray one.
    est = FaceQualityEstimator()
    h, w = 300, 300
    sharp = np.random.default_rng(0).integers(0, 255, (h, w, 3), dtype=np.uint8)
    flat = np.full((h, w, 3), 10, dtype=np.uint8)  # dark + no texture
    bbox = BBox(50, 50, 250, 250)  # 200px face
    q_sharp = est.score(sharp, bbox)
    q_flat = est.score(flat, bbox)
    assert 0 <= q_sharp.score <= 100
    assert q_sharp.score > q_flat.score
    assert q_sharp.face_width == 200
