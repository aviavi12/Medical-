"""Mouth crop normalization.

Converts a BGR crop to a normalized grayscale float array in [0, 1]. Model
adapters may re-normalize to their own spec; this is a stable common baseline.
"""

from __future__ import annotations

from typing import Any


def normalize_crop(crop: Any) -> Any:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        if crop.ndim == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop
        arr = gray.astype("float32") / 255.0
        return arr
    except Exception:
        return crop
