"""Associate detected faces with detected people (§12).

Uses spatial overlap, containment, and centre distance. A face that cannot be
confidently associated is marked uncertain rather than forced onto a person.
This is deterministic geometry — not an ML inference — so it always runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from ml.common.types import FaceDetection, PersonDetection, Track


@dataclass
class Association:
    face_index: int
    person_track_id: int | None
    confidence: float
    uncertain: bool

    def as_dict(self) -> dict:
        return {
            "face_index": self.face_index,
            "person_track_id": self.person_track_id,
            "confidence": round(self.confidence, 4),
            "uncertain": self.uncertain,
        }


def _score(face: FaceDetection, person_bbox) -> float:
    """Blend containment (dominant), IoU, and centre proximity into 0..1."""
    containment = person_bbox.contains_fraction(face.bbox)
    iou = person_bbox.iou(face.bbox)

    fcx, fcy = face.bbox.center
    pcx, pcy = person_bbox.center
    diag = (person_bbox.width ** 2 + person_bbox.height ** 2) ** 0.5 or 1.0
    dist = ((fcx - pcx) ** 2 + (fcy - pcy) ** 2) ** 0.5
    proximity = max(0.0, 1.0 - dist / diag)

    return 0.6 * containment + 0.25 * iou + 0.15 * proximity


class FacePersonAssociator:
    def __init__(self, min_confidence: float = 0.35) -> None:
        self.min_confidence = min_confidence

    def associate(
        self, faces: list[FaceDetection], tracks: list[Track]
    ) -> list[Association]:
        results: list[Association] = []
        for fi, face in enumerate(faces):
            best_id: int | None = None
            best_score = 0.0
            for t in tracks:
                s = _score(face, t.bbox)
                if s > best_score:
                    best_score = s
                    best_id = t.track_id
            uncertain = best_score < self.min_confidence or best_id is None
            results.append(
                Association(
                    face_index=fi,
                    person_track_id=None if uncertain else best_id,
                    confidence=best_score,
                    uncertain=uncertain,
                )
            )
        return results


def associate(
    faces: list[FaceDetection],
    tracks: list[Track],
    min_confidence: float = 0.35,
) -> list[Association]:
    return FacePersonAssociator(min_confidence).associate(faces, tracks)
