"""LipNet adapter — real English visual speech recognition (§10, §12, §23).

Wraps the LipNet model + VisualSpeechPreprocessor + CTC decoder behind the
LipReadingModel interface. Loads real pretrained GRID weights (MIT, Fengdalu)
and reports MODEL_UNAVAILABLE with the exact missing piece if weights/deps are
absent — it never fabricates a transcript.

Domain: GRID-corpus English (6-word command grammar). This is the "suitable
English video" domain for this checkpoint; see docs/lipreading-model-comparison.md.
"""

from __future__ import annotations

from typing import Any

from ml.common.config import MLConfig, get_ml_config
from ml.common.device import resolve_device
from ml.common.results import Availability, ModelInfo, available, model_unavailable, no_signal
from ml.common.types import LipReadingResult, LipReadingSegment, LipReadingWord
from ml.lipreading.base import InputContract, LipReadingModel
from ml.lipreading.lipnet.decode import ctc_greedy_decode
from ml.lipreading.lipnet.preprocess import PreprocessorUnavailable, VisualSpeechPreprocessor
from ml.lipreading.postprocessing import apply_postprocessing
from ml.mouth.sequence import TemporalMouthSequence

WINDOW = 75          # frames (~3s at 25fps) — LipNet's training clip length
CONF_THRESHOLD = 0.5  # below this a segment's text is masked [uncertain]


class LipNetAdapter(LipReadingModel):
    name = "lip_reading"
    supports_frame_transcription = True

    def __init__(self, config: MLConfig) -> None:
        self.config = config
        self.device = resolve_device(config.device)
        self._model = None
        self._preprocessor: VisualSpeechPreprocessor | None = None
        self._missing = self._check_requirements()

    # ── requirements / availability ─────────────────────────────────────────
    def _check_requirements(self) -> list[str]:
        import os

        missing: list[str] = []
        try:
            import torch  # type: ignore  # noqa: F401
        except Exception:
            missing.append("torch")
        try:
            import dlib  # type: ignore  # noqa: F401
        except Exception:
            missing.append("dlib (pip install dlib-bin)")
        if not self.config.lip_reading_weights or not os.path.exists(self.config.lip_reading_weights):
            missing.append(f"LipNet weights ({self.config.lip_reading_weights or 'LIP_READING_WEIGHTS'})")
        if not self.config.dlib_landmarks or not os.path.exists(self.config.dlib_landmarks):
            missing.append(f"dlib 68-landmark predictor ({self.config.dlib_landmarks or 'DLIB_LANDMARKS'})")
        return missing

    def availability(self) -> Availability:
        if self._missing:
            return model_unavailable(
                "LipNet visual speech model is unavailable. Run scripts/download_models.py "
                "to fetch weights + the landmark predictor, and install ML deps.",
                self._missing,
                model=self.get_model_info(),
            )
        return available(self.get_model_info())

    def input_contract(self) -> InputContract:
        return InputContract(required_fps=25.0, sequence_length=WINDOW, input_size=(128, 64),
                             normalization="bgr_div255")

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            name="lipnet-grid",
            version="fengdalu-mit",
            framework="pytorch",
            device=self.device,
            checkpoint=self.config.lip_reading_weights or None,
            license="MIT (code+weights); dlib predictor: research-only; GRID: research",
            configuration={"input": "128x64 BGR", "fps": 25, "grammar": "GRID 6-word",
                           "domain": "GRID English"},
        )

    # ── lazy heavy-object loading (once per worker) ──────────────────────────
    def _ensure_loaded(self):
        if self._model is not None:
            return
        import torch  # type: ignore

        from ml.common.registry import REGISTRY
        from ml.lipreading.lipnet.model import LipNet

        weights = self.config.lip_reading_weights

        def build():
            m = LipNet()
            state = torch.load(weights, map_location=self.device)
            m.load_state_dict(state)
            m.to(self.device).eval()
            return m

        self._model = REGISTRY.get(f"lipnet::{weights}::{self.device}", build)
        self._preprocessor = VisualSpeechPreprocessor(self.config.dlib_landmarks)

    @property
    def preprocessor(self) -> VisualSpeechPreprocessor:
        self._ensure_loaded()
        assert self._preprocessor is not None
        return self._preprocessor

    # ── inference ────────────────────────────────────────────────────────────
    def _infer_window(self, crops: list[Any], timestamps: list[float]) -> LipReadingSegment:
        import numpy as np  # type: ignore
        import torch  # type: ignore

        arr = np.stack(crops, axis=0).astype("float32")          # (T, 64, 128, 3) BGR
        x = torch.FloatTensor(arr.transpose(3, 0, 1, 2)) / 255.0  # (3, T, 64, 128)
        with torch.no_grad():
            logits = self._model(x[None, ...].to(self.device))[0]  # (T, 28)
        decoded = ctc_greedy_decode(logits, timestamps)
        return LipReadingSegment(
            start_time=round(timestamps[0], 3) if timestamps else 0.0,
            end_time=round(timestamps[-1], 3) if timestamps else 0.0,
            text=decoded.text,
            confidence=decoded.confidence,
            raw_text=decoded.text,
            words=[LipReadingWord(w.word, w.start, w.end, w.confidence) for w in decoded.words],
        )

    def transcribe(self, frames: list[tuple[float, Any, list[float] | None]]) -> LipReadingResult:
        """Convenience path: raw (timestamp, bgr_frame, face_roi) → real transcript.

        Used by the CLI/tests on short clips. For long videos the pipeline streams
        crops via ``transcribe_crops`` to bound memory."""
        av = self.availability()
        if not av.is_available:
            return LipReadingResult(availability=av, segments=[])
        self._ensure_loaded()
        try:
            crops, timestamps = self._preprocessor.build_frames(frames)  # type: ignore[union-attr]
        except PreprocessorUnavailable as exc:
            return LipReadingResult(
                availability=model_unavailable(str(exc), ["dlib / landmark predictor"]),
                segments=[],
            )
        return self.transcribe_crops(crops, timestamps)

    def transcribe_crops(self, crops: list[Any], timestamps: list[float]) -> LipReadingResult:
        """Window prebuilt 128x64 BGR mouth crops (~3s windows) → timestamped
        segments. Applies confidence masking + light LM cleanup. Never pads/fakes
        a too-short trailing window."""
        av = self.availability()
        if not av.is_available:
            return LipReadingResult(availability=av, segments=[])
        self._ensure_loaded()
        if len(crops) < 8:
            return LipReadingResult(
                availability=no_signal(
                    f"Only {len(crops)} usable mouth frames were found; "
                    "insufficient visual signal for lip reading."
                ),
                segments=[],
            )
        segments: list[LipReadingSegment] = []
        for i in range(0, len(crops), WINDOW):
            w_crops = crops[i:i + WINDOW]
            w_ts = timestamps[i:i + WINDOW]
            if len(w_crops) < 8:
                break
            segments.append(self._infer_window(w_crops, w_ts))
        segments = apply_postprocessing(segments, threshold=CONF_THRESHOLD)
        return LipReadingResult(availability=available(self.get_model_info()), segments=segments)

    def predict(self, sequence: TemporalMouthSequence) -> LipReadingResult:
        """Interface method: infer from a prebuilt sequence of LipNet-format crops."""
        av = self.availability()
        if not av.is_available:
            return LipReadingResult(availability=av, segments=[])
        self._ensure_loaded()
        crops = [c.data for c in sequence.crops if c.data is not None]
        timestamps = [c.timestamp for c in sequence.crops if c.data is not None]
        if len(crops) < 8:
            return LipReadingResult(
                availability=no_signal("Insufficient mouth frames for lip reading."), segments=[]
            )
        seg = self._infer_window(crops, timestamps)
        seg = apply_postprocessing([seg], threshold=CONF_THRESHOLD)[0]
        return LipReadingResult(availability=available(self.get_model_info()), segments=[seg])


def get_lipnet(config: MLConfig | None = None) -> LipNetAdapter:
    return LipNetAdapter(config or get_ml_config())
