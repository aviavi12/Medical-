"""OpenVocabularyLipReadingModel — SyncVSR adapter (Phase 4).

Real open-vocabulary English visual speech recognition. Implements the
LipReadingModel interface (load / preprocess / predict / decode / confidence /
model_info) and reports MODEL_UNAVAILABLE with the exact reachable source when
the checkpoint/deps are missing — it never falls back to GRID or fabricates text.

Visual-only: `transcribe` accepts only frames; there is no audio path.
"""

from __future__ import annotations

import os
from typing import Any

from ml.common.config import MLConfig, get_ml_config
from ml.common.device import resolve_device
from ml.common.results import Availability, ModelInfo, available, model_unavailable, no_signal
from ml.common.types import LipReadingResult, LipReadingSegment, LipReadingWord
from ml.lipreading.base import InputContract, LipReadingModel
from ml.lipreading.openvocab.preprocess import CropMode, OpenVocabPreprocessor
from ml.lipreading.postprocessing import apply_postprocessing

# Windowing for long video: SyncVSR handles variable length; we cap a window and
# overlap so a 5-minute video is processed in bounded chunks (Phase 14/18).
WINDOW_FRAMES = 375   # ~15s at 25fps
STRIDE_FRAMES = 350   # ~1s overlap
MIN_FRAMES = 5
CONF_THRESHOLD = 0.4

CHECKPOINT_SOURCE = (
    "https://github.com/KAIST-AILab/SyncVSR/releases/download/weight-audio-v1/Vox%2BLRS2%2BLRS3.ckpt"
)


class OpenVocabularyLipReadingModel(LipReadingModel):
    name = "lip_reading"
    supports_frame_transcription = True

    def __init__(self, config: MLConfig) -> None:
        self.config = config
        self.device = resolve_device(config.device)
        self.crop_mode = CropMode(getattr(config, "openvocab_crop_mode", "lower_face"))
        self.beam_size = int(getattr(config, "openvocab_beam_size", 10) or 10)
        self.checkpoint = getattr(config, "openvocab_weights", "") or os.path.join(
            config.models_dir, "syncvsr_vox_lrs2_lrs3.ckpt"
        )
        self._model = None
        self._pre: OpenVocabPreprocessor | None = None
        self._missing = self._check_requirements()

    # ── availability ─────────────────────────────────────────────────────────
    def _check_requirements(self) -> list[str]:
        missing: list[str] = []
        for mod in ("torch", "sentencepiece", "omegaconf", "transformers", "timm", "mediapipe"):
            try:
                __import__(mod)
            except Exception:
                missing.append(mod)
        if not os.path.exists(self.checkpoint):
            missing.append(f"checkpoint {os.path.basename(self.checkpoint)}")
        return missing

    def availability(self) -> Availability:
        if self._missing:
            return model_unavailable(
                "Open-vocabulary VSR (SyncVSR) is not installed. Run "
                "scripts/download_models.py to fetch the checkpoint, and install "
                "requirements-ml.txt. Checkpoint source (reachable GitHub release): "
                f"{CHECKPOINT_SOURCE}",
                self._missing,
                model=self.get_model_info(),
            )
        return available(self.get_model_info())

    def input_contract(self) -> InputContract:
        return InputContract(required_fps=25.0, sequence_length=WINDOW_FRAMES, input_size=(96, 96),
                             normalization="grayscale_syncvsr(0.421,0.165)")

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            name="syncvsr-vox-lrs2-lrs3",
            version="weight-audio-v1",
            framework="pytorch/espnet(conformer)",
            device=self.device,
            checkpoint=self.checkpoint if os.path.exists(self.checkpoint) else None,
            license="MIT (SyncVSR); ESPnet Apache-2.0",
            configuration={
                "vocabulary": "open (SentencePiece unigram5000)",
                "trained_on": "VoxCeleb2 + LRS2 + LRS3",
                "crop_mode": self.crop_mode.value,
                "fps": 25, "input": "96x96 grayscale", "beam_size": self.beam_size,
                "decoder": "CTC(0.1)+attention beam search",
            },
        )

    # ── lazy load (once per worker) ──────────────────────────────────────────
    def load(self) -> None:
        self._ensure_loaded()

    def _ensure_loaded(self):
        if self._model is not None:
            return
        from ml.common.registry import REGISTRY
        from ml.lipreading.openvocab.model import SyncVSRModel

        self._model = REGISTRY.get(
            f"syncvsr::{self.checkpoint}::{self.device}::{self.beam_size}",
            lambda: SyncVSRModel(self.checkpoint, device=self.device, beam_size=self.beam_size),
        )
        self._pre = OpenVocabPreprocessor(mode=self.crop_mode)

    @property
    def preprocessor(self) -> OpenVocabPreprocessor:
        self._ensure_loaded()
        assert self._pre is not None
        return self._pre

    def crop_for_frame(self, frame, roi=None):
        self._ensure_loaded()
        return self._pre.crop_frame(frame, roi)  # type: ignore[union-attr]

    def model_info(self) -> dict:
        return self.get_model_info().as_dict()

    # ── inference ─────────────────────────────────────────────────────────────
    def _infer_window(self, gray_crops: list, timestamps: list[float]) -> LipReadingSegment:
        sample = self._pre.to_tensor(gray_crops)  # type: ignore[union-attr]
        nbest = self._model.nbest(sample, n=3)
        text, conf = (nbest[0] if nbest else ("", 0.0))
        alts = [(t, c) for (t, c) in nbest[1:]] if len(nbest) > 1 else []
        return LipReadingSegment(
            start_time=round(timestamps[0], 3) if timestamps else 0.0,
            end_time=round(timestamps[-1], 3) if timestamps else 0.0,
            text=text, confidence=conf, raw_text=text, alternatives=alts,
        )

    def transcribe_crops(self, gray_crops: list, timestamps: list[float]) -> LipReadingResult:
        av = self.availability()
        if not av.is_available:
            return LipReadingResult(availability=av, segments=[])
        self._ensure_loaded()
        if len(gray_crops) < MIN_FRAMES:
            return LipReadingResult(
                availability=no_signal(
                    f"Only {len(gray_crops)} usable face frames were found; insufficient "
                    "visual signal for lip reading."
                ),
                segments=[],
            )
        segments: list[LipReadingSegment] = []
        if len(gray_crops) <= WINDOW_FRAMES:
            segments.append(self._infer_window(gray_crops, timestamps))
        else:
            i = 0
            while i < len(gray_crops):
                wc = gray_crops[i:i + WINDOW_FRAMES]
                wt = timestamps[i:i + WINDOW_FRAMES]
                if len(wc) < MIN_FRAMES:
                    break
                segments.append(self._infer_window(wc, wt))
                if i + WINDOW_FRAMES >= len(gray_crops):
                    break
                i += STRIDE_FRAMES
        segments = apply_postprocessing(segments, threshold=CONF_THRESHOLD)
        return LipReadingResult(availability=available(self.get_model_info()), segments=segments)

    def transcribe(self, frames: list[tuple[float, Any, list | None]]) -> LipReadingResult:
        av = self.availability()
        if not av.is_available:
            return LipReadingResult(availability=av, segments=[])
        self._ensure_loaded()
        crops, timestamps = self._pre.build_crops(frames)  # type: ignore[union-attr]
        return self.transcribe_crops(crops, timestamps)

    def predict(self, sequence) -> LipReadingResult:
        """Interface method for a prebuilt TemporalMouthSequence of gray crops."""
        crops = [c.data for c in sequence.crops if c.data is not None]
        ts = [c.timestamp for c in sequence.crops if c.data is not None]
        return self.transcribe_crops(crops, ts)


def get_openvocab(config: MLConfig | None = None) -> OpenVocabularyLipReadingModel:
    return OpenVocabularyLipReadingModel(config or get_ml_config())
