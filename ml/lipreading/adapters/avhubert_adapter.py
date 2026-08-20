"""AV-HuBERT lip-reading adapter (§23).

AV-HuBERT is a strong English visual-speech-recognition model, but it is
licensed CC-BY-NC (non-commercial) and needs PyTorch + downloaded weights +
(often) fairseq. This adapter checks those preconditions and reports
MODEL_UNAVAILABLE naming the exact gap when they are absent — it never returns a
fabricated transcript. When the preconditions are met, wire real inference in
``predict``.
"""

from __future__ import annotations

from ml.common.config import MLConfig
from ml.common.device import resolve_device
from ml.common.results import Availability, ModelInfo, available, model_unavailable
from ml.common.types import LipReadingResult
from ml.lipreading.base import InputContract, LipReadingModel
from ml.mouth.sequence import TemporalMouthSequence


class AVHubertAdapter(LipReadingModel):
    name = "lip_reading"

    def __init__(self, config: MLConfig) -> None:
        self.config = config
        self.device = resolve_device(config.device)
        self._missing = self._check_requirements()
        self._model = None

    def _check_requirements(self) -> list[str]:
        missing: list[str] = []
        try:
            import torch  # type: ignore  # noqa: F401
        except Exception:
            missing.append("torch")
        if not self.config.lip_reading_weights:
            missing.append("lip-reading weights (LIP_READING_WEIGHTS)")
        return missing

    def input_contract(self) -> InputContract:
        return InputContract(required_fps=25.0, sequence_length=75, input_size=(96, 96),
                             normalization="grayscale_0_1")

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            name="av-hubert",
            version="vsr-en",
            framework="pytorch/fairseq",
            device=self.device,
            checkpoint=self.config.lip_reading_weights or None,
            license="CC-BY-NC-4.0 (non-commercial)",
            configuration={"img_size": 96, "seq_len": 75},
        )

    def availability(self) -> Availability:
        if self._missing:
            return model_unavailable(
                reason=(
                    "AV-HuBERT lip-reading model is unavailable. Required checkpoint/"
                    "dependencies are missing. AV-HuBERT is CC-BY-NC (non-commercial) — "
                    "accept its license and download weights. See docs/model-selection.md."
                ),
                missing=self._missing,
                model=self.get_model_info(),
            )
        return available(self.get_model_info())  # pragma: no cover - needs weights

    def predict(self, sequence: TemporalMouthSequence) -> LipReadingResult:
        av = self.availability()
        if not av.is_available:
            return LipReadingResult(availability=av, segments=[])
        # pragma: no cover - real inference path requires weights + torch.
        raise NotImplementedError(
            "AV-HuBERT inference not wired. Install weights + torch, then implement "
            "predict() to run real VSR. Do not fabricate output."
        )
