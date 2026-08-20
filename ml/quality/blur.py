"""Blur / sharpness metrics — real computation via the variance of the Laplacian."""

from __future__ import annotations

from typing import Any


def laplacian_variance(gray: Any) -> float:
    """Variance of the Laplacian; higher = sharper. Returns 0 on failure."""
    try:
        import cv2  # type: ignore

        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        try:
            import numpy as np  # type: ignore

            gy, gx = np.gradient(gray.astype("float64"))
            return float((gx**2 + gy**2).var())
        except Exception:
            return 0.0


def sharpness_score(lap_var: float, ref: float = 500.0) -> float:
    """Map Laplacian variance to 0..1. ``ref`` is 'clearly sharp' for a face crop."""
    if lap_var <= 0:
        return 0.0
    return max(0.0, min(1.0, lap_var / ref))


def blur_score(lap_var: float, ref: float = 500.0) -> float:
    """0 = sharp, 1 = very blurry (complement of sharpness)."""
    return round(1.0 - sharpness_score(lap_var, ref), 4)
