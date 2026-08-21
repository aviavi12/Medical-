"""LipReadingModel interface (§23, §24).

Every adapter declares its temporal input contract (required_fps, sequence
length, input size, normalization) and returns a LipReadingResult whose
``availability`` state is the single source of truth for whether the output is a
real model prediction. Missing weights/deps/license ⇒ MODEL_UNAVAILABLE with the
exact gap; the pipeline never fabricates a transcript.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ml.common.config import MLConfig, get_ml_config
from ml.common.results import Availability, ModelInfo
from ml.common.types import LipReadingResult
from ml.mouth.sequence import TemporalMouthSequence


@dataclass
class InputContract:
    required_fps: float = 25.0
    sequence_length: int = 75
    input_size: tuple[int, int] = (96, 96)
    normalization: str = "grayscale_0_1"


class LipReadingModel(ABC):
    name = "lip_reading"

    # A model that can run its own frame-level preprocessing (face align → mouth
    # ROI) sets this True and implements ``transcribe``. Models that only accept a
    # prebuilt TemporalMouthSequence leave it False (the pipeline then uses the
    # generic landmarker + MouthExtractor path).
    supports_frame_transcription: bool = False

    def load(self) -> None:
        """Optional explicit load; adapters may lazy-load in __init__."""

    def transcribe(self, frames):
        """Real path from raw frames: [(timestamp, bgr_frame, face_roi|None), ...]
        → LipReadingResult. Default: not supported."""
        from ml.common.results import model_unavailable
        from ml.common.types import LipReadingResult

        return LipReadingResult(
            availability=model_unavailable(
                "This lip-reading model has no frame-level preprocessor.", []
            ),
            segments=[],
        )

    @abstractmethod
    def input_contract(self) -> InputContract: ...

    @abstractmethod
    def availability(self) -> Availability: ...

    @abstractmethod
    def get_model_info(self) -> ModelInfo: ...

    @abstractmethod
    def predict(self, sequence: TemporalMouthSequence) -> LipReadingResult:
        """Run visual speech recognition over a temporal mouth sequence."""


def get_lip_reading_model(config: MLConfig | None = None) -> LipReadingModel:
    config = config or get_ml_config()

    if config.allow_mock:
        from ml.lipreading.adapters.mock_adapter import MockLipReadingModel

        return MockLipReadingModel()

    name = config.lip_reading_model
    if name == "lipnet":
        from ml.lipreading.adapters.lipnet_adapter import LipNetAdapter

        return LipNetAdapter(config)
    if name == "avhubert":
        from ml.lipreading.adapters.avhubert_adapter import AVHubertAdapter

        return AVHubertAdapter(config)

    # Default to the real, runnable LipNet adapter.
    from ml.lipreading.adapters.lipnet_adapter import LipNetAdapter

    return LipNetAdapter(config)
