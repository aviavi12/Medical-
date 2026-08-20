"""Gaze estimator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ml.common.results import Availability
from ml.common.types import FaceLandmarks, GazeResult


class BaseGazeEstimator(ABC):
    name = "gaze"

    @abstractmethod
    def availability(self) -> Availability: ...

    @abstractmethod
    def estimate(self, landmarks: FaceLandmarks | None, timestamp: float = 0.0) -> GazeResult: ...
