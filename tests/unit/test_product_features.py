"""Unit tests for the browser-product features: combined-score readiness status
(§10/§11/§25), overlapping-window merge (§16), visual speaking-activity estimate
(§17) and NO_SPEECH_EVIDENCE silence handling (§18)."""

from __future__ import annotations

import numpy as np

from ml.common.types import LipReadingSegment
from ml.lipreading.activity import (
    NOT_SPEAKING,
    SPEAKING_LIKELY,
    UNCERTAIN,
    estimate_activity,
    motion_score,
)
from ml.lipreading.merge import joined_transcript, merge_overlapping_segments
from ml.lipreading.postprocessing import NO_SPEECH_EVIDENCE, apply_postprocessing
from ml.quality.readiness import (
    INSUFFICIENT,
    READY,
    WARNING,
    readiness_status,
)


# ── readiness status (§10/§11/§25) ──────────────────────────────────────────
def test_readiness_status_ready_warning_insufficient():
    good = readiness_status(
        readiness_score=78, avg_face_width_px=180, avg_mouth_visibility=0.8,
        avg_sharpness=0.7, avg_pose_quality=0.85, tracking_stability=0.95,
        usable_duration=6.0, face_quality_score=80, visible_ratio=1.0,
    )
    assert good.status == READY and not good.reasons

    warn = readiness_status(
        readiness_score=60, avg_face_width_px=90, avg_mouth_visibility=0.7,
        avg_sharpness=0.6, avg_pose_quality=0.7, tracking_stability=0.8,
        usable_duration=4.0, face_quality_score=60, visible_ratio=0.9,
    )
    assert warn.status == WARNING
    assert any("small" in r.lower() for r in warn.reasons)  # 90px < recommended 130

    bad = readiness_status(
        readiness_score=18, avg_face_width_px=30, avg_mouth_visibility=0.2,
        avg_sharpness=0.15, avg_pose_quality=0.3, tracking_stability=0.3,
        usable_duration=0.3, face_quality_score=20, visible_ratio=0.3,
    )
    assert bad.status == INSUFFICIENT
    assert bad.reasons  # specific reasons, not a generic failure


def test_readiness_report_serialises_full_metrics():
    r = readiness_status(
        readiness_score=70, avg_face_width_px=150, avg_mouth_visibility=0.75,
        avg_sharpness=0.6, avg_pose_quality=0.8, tracking_stability=0.9,
        usable_duration=5.0, face_quality_score=65, visible_ratio=1.0,
    )
    d = r.as_dict()
    for key in ("status", "readiness_score", "face_quality_score", "usable_duration",
                "avg_face_width_px", "avg_mouth_visibility_pct", "avg_sharpness",
                "avg_pose_quality", "tracking_stability", "reasons"):
        assert key in d


# ── overlapping-window merge (§16) ──────────────────────────────────────────
def _seg(text, s, e, fs, fe, wi):
    return LipReadingSegment(start_time=s, end_time=e, text=text, confidence=0.8,
                             raw_text=text, frame_start=fs, frame_end=fe, window_index=wi)


def test_merge_removes_boundary_duplicates():
    segs = [
        _seg("the quick brown fox jumps", 0, 15, 0, 374, 0),
        _seg("fox jumps over the lazy dog", 14, 29, 350, 724, 1),
    ]
    merged = merge_overlapping_segments(segs)
    assert [s.text for s in merged] == ["the quick brown fox jumps", "over the lazy dog"]
    assert joined_transcript(merged) == "the quick brown fox jumps over the lazy dog"


def test_merge_drops_window_that_adds_nothing():
    segs = [
        _seg("hello world", 0, 15, 0, 374, 0),
        _seg("hello world", 14, 29, 350, 724, 1),
    ]
    merged = merge_overlapping_segments(segs)
    assert len(merged) == 1
    assert merged[0].end_time == 29  # span folded in


def test_merge_preserves_metadata():
    segs = [
        _seg("alpha beta gamma", 0, 15, 0, 374, 0),
        _seg("gamma delta epsilon", 14, 29, 350, 724, 1),
    ]
    merged = merge_overlapping_segments(segs)
    assert merged[1].window_index == 1
    assert merged[1].frame_start == 350


# ── speaking-activity estimate + silence (§17/§18) ──────────────────────────
def _still(n=20):
    return [np.full((96, 96), 120, dtype=np.uint8) for _ in range(n)]


def _talking(n=20):
    frames = []
    for i in range(n):
        f = np.full((96, 96), 120, dtype=np.uint8)
        openness = int(28 * abs(np.sin(i)))
        f[62:62 + openness, 30:66] = 40
        frames.append(f)
    return frames


def test_activity_still_vs_talking():
    assert estimate_activity(_still())[0] == NOT_SPEAKING
    assert estimate_activity(_talking())[0] == SPEAKING_LIKELY
    assert estimate_activity([])[0] == UNCERTAIN
    assert motion_score(_still()) < motion_score(_talking())


def test_no_speech_evidence_not_masked_as_uncertain():
    seg = LipReadingSegment(start_time=0, end_time=3, text="", confidence=0.0,
                            speaking_activity=NOT_SPEAKING)
    out = apply_postprocessing([seg], threshold=0.5)
    assert out[0].text == NO_SPEECH_EVIDENCE
    # Never invents words for a silent window.
    assert out[0].processed_text == NO_SPEECH_EVIDENCE
