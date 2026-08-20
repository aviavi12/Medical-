"""Preprocessing for lip-reading adapters.

Turns a TemporalMouthSequence into the tensor layout an adapter expects
according to its InputContract. Kept adapter-agnostic; adapters call this then
apply any model-specific normalization.
"""

from __future__ import annotations

from typing import Any

from ml.lipreading.base import InputContract
from ml.mouth.sequence import TemporalMouthSequence


def to_array(sequence: TemporalMouthSequence, contract: InputContract) -> Any:
    """Stack available mouth crops into a (T, H, W) float array.

    Returns None when no pixel data is present (e.g. geometry-only sequences),
    which adapters translate into a NO_SIGNAL / MODEL_UNAVAILABLE outcome rather
    than inventing frames.
    """
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None

    frames = [c.data for c in sequence.crops if c.data is not None]
    if not frames:
        return None
    h, w = contract.input_size
    arr = np.zeros((len(frames), h, w), dtype="float32")
    for i, f in enumerate(frames):
        a = np.asarray(f, dtype="float32")
        if a.shape[:2] != (h, w):
            try:
                import cv2  # type: ignore

                a = cv2.resize(a, (w, h))
            except Exception:
                continue
        arr[i] = a
    return arr
