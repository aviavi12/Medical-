"""ByteTrack / BoT-SORT adapter (§10, §70).

Preferred production trackers (MIT). They require native deps (e.g. ``lap``,
``cython-bbox``) and a vendored tracker implementation. This module is a seam:
when those are installed, wire the real tracker here. Until then, importing it
raises so ``get_tracker`` falls back to the dependency-free SimpleIoUTracker.
"""

from __future__ import annotations

from ml.common.config import MLConfig
from ml.tracking.tracker import PersonTracker


def make_tracker(name: str, config: MLConfig) -> PersonTracker:  # pragma: no cover
    raise ImportError(
        f"{name} adapter not wired: install the tracker package and its native "
        "deps, then implement make_tracker(). See docs/model-selection.md §70."
    )
