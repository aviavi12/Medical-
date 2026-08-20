"""High-level inference helper.

Runs a model over one or more temporal sequences and applies post-processing.
The honesty state from the model flows straight through unchanged.
"""

from __future__ import annotations

from ml.common.results import AvailabilityState
from ml.common.types import LipReadingResult
from ml.lipreading.base import LipReadingModel
from ml.lipreading.postprocessing import apply_postprocessing
from ml.mouth.sequence import TemporalMouthSequence


def run_inference(
    model: LipReadingModel,
    sequences: list[TemporalMouthSequence],
    confidence_threshold: float = 0.5,
) -> LipReadingResult:
    availability = model.availability()
    if availability.state == AvailabilityState.MODEL_UNAVAILABLE:
        return LipReadingResult(availability=availability, segments=[])

    all_segments = []
    last_availability = availability
    for seq in sequences:
        result = model.predict(seq)
        last_availability = result.availability
        all_segments.extend(result.segments)

    processed = apply_postprocessing(all_segments, threshold=confidence_threshold)
    return LipReadingResult(availability=last_availability, segments=processed)
