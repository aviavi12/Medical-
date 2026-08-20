"""Mock lip-reading adapter — UNIT TESTS ONLY (§24, §97).

Deliberately emits an OBVIOUSLY synthetic placeholder (containing the word
"mock") rather than a plausible English sentence, so it can never be mistaken for
a real transcript. Guarded by ALLOW_MOCK_INFERENCE and marked mock=True. It
exercises the confidence/uncertainty and n-best code paths only.
"""

from __future__ import annotations

from ml.common.results import ModelInfo, available
from ml.common.types import LipReadingResult, LipReadingSegment
from ml.lipreading.base import InputContract, LipReadingModel
from ml.mouth.sequence import TemporalMouthSequence


class MockLipReadingModel(LipReadingModel):
    name = "lip_reading"

    def input_contract(self) -> InputContract:
        return InputContract()

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name="mock-vsr", version="test", framework="mock",
                         configuration={"mock": True})

    def availability(self):
        return available(self.get_model_info())

    def predict(self, sequence: TemporalMouthSequence) -> LipReadingResult:
        n = len(sequence)
        # Deterministic confidence so tests can drive both confident and
        # uncertain branches by controlling sequence length.
        confidence = round(min(0.95, 0.30 + 0.03 * n), 4)
        seg = LipReadingSegment(
            start_time=sequence.start_time,
            end_time=sequence.end_time,
            text=f"[mock-vsr tokens={n}]",
            confidence=confidence,
            raw_text=f"[mock-vsr tokens={n}]",
            alternatives=[(f"[mock-alt-a tokens={n}]", confidence * 0.6),
                          (f"[mock-alt-b tokens={n}]", confidence * 0.3)],
        )
        return LipReadingResult(availability=available(self.get_model_info()), segments=[seg])
