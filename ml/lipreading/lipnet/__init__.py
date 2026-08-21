"""Real LipNet visual speech recognition (English, GRID corpus).

- ``model``: the LipNet 3D-CNN + Bi-GRU + CTC architecture.
- ``preprocess``: VisualSpeechPreprocessor — dlib-68 alignment → 128x64 mouth ROI,
  matching the exact preprocessing the checkpoints were trained with (§11).
- ``decode``: CTC greedy decoding with per-word timestamps and confidence.

Model + weights: Fengdalu/LipNet-PyTorch (MIT). Architecture: Assael et al.,
"LipNet: End-to-End Sentence-level Lipreading" (2016). See docs/model-selection.md.
"""

from ml.lipreading.lipnet.model import LipNet, GRID_LETTERS
from ml.lipreading.lipnet.preprocess import VisualSpeechPreprocessor
from ml.lipreading.lipnet.decode import ctc_greedy_decode

__all__ = ["LipNet", "GRID_LETTERS", "VisualSpeechPreprocessor", "ctc_greedy_decode"]
