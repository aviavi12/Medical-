"""Detection subsystem: PersonDetector and FaceDetector with pluggable adapters."""

from ml.detection.person_detector import PersonDetector, get_person_detector
from ml.detection.face_detector import FaceDetector, get_face_detector

__all__ = [
    "PersonDetector",
    "get_person_detector",
    "FaceDetector",
    "get_face_detector",
]
