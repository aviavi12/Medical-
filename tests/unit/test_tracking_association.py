"""Unit tests: IoU tracker stability + face/person association."""

from __future__ import annotations

from ml.association import associate
from ml.common.types import BBox, FaceDetection, PersonDetection
from ml.tracking import SimpleIoUTracker


def _person(x1, y1, x2, y2, conf=0.9, frame=0):
    return PersonDetection(bbox=BBox(x1, y1, x2, y2), confidence=conf, frame_index=frame, timestamp=frame * 0.1)


def test_tracker_keeps_stable_id_across_frames():
    tracker = SimpleIoUTracker()
    ids = []
    for f in range(5):
        # person drifts slightly to the right each frame
        dets = [_person(100 + f * 5, 100, 200 + f * 5, 300, frame=f)]
        tracks = tracker.update(dets, f, f * 0.1)
        assert len(tracks) == 1
        ids.append(tracks[0].track_id)
    assert len(set(ids)) == 1  # same id throughout


def test_tracker_new_person_gets_new_id():
    tracker = SimpleIoUTracker()
    tracker.update([_person(0, 0, 50, 100)], 0, 0.0)
    tracks = tracker.update(
        [_person(0, 0, 50, 100), _person(400, 0, 450, 100)], 1, 0.1
    )
    assert len({t.track_id for t in tracks}) == 2


def test_tracker_survives_short_gap():
    tracker = SimpleIoUTracker(max_age=8)
    t0 = tracker.update([_person(100, 100, 200, 300)], 0, 0.0)
    original_id = t0[0].track_id
    # miss a frame (no detections)
    tracker.update([], 1, 0.1)
    t2 = tracker.update([_person(102, 100, 202, 300)], 2, 0.2)
    assert t2[0].track_id == original_id


def test_association_prefers_containing_person():
    face = FaceDetection(bbox=BBox(120, 110, 170, 160), confidence=0.9, frame_index=0, timestamp=0.0)
    from ml.common.types import Track

    p1 = Track(track_id=1, bbox=BBox(100, 100, 200, 300), frame_index=0, timestamp=0.0)
    p2 = Track(track_id=2, bbox=BBox(400, 100, 500, 300), frame_index=0, timestamp=0.0)
    result = associate([face], [p1, p2])
    assert len(result) == 1
    assert result[0].person_track_id == 1
    assert not result[0].uncertain


def test_association_marks_uncertain_when_no_overlap():
    face = FaceDetection(bbox=BBox(900, 900, 950, 950), confidence=0.9, frame_index=0, timestamp=0.0)
    from ml.common.types import Track

    p1 = Track(track_id=1, bbox=BBox(0, 0, 100, 200), frame_index=0, timestamp=0.0)
    result = associate([face], [p1])
    assert result[0].uncertain
    assert result[0].person_track_id is None
