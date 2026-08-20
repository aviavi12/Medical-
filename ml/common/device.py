"""Device resolution (§57). Never crashes when CUDA/MPS are absent."""

from __future__ import annotations

import functools


@functools.lru_cache(maxsize=8)
def resolve_device(preference: str = "auto") -> str:
    """Resolve a device preference to a concrete device string.

    ``auto`` → cuda → mps → cpu, in that order of availability. Falls back to
    ``cpu`` cleanly if torch is not installed at all.
    """
    preference = (preference or "auto").lower()

    try:
        import torch  # type: ignore
    except Exception:
        # No torch: only cpu is meaningful.
        return "cpu"

    def cuda_ok() -> bool:
        try:
            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def mps_ok() -> bool:
        try:
            return bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        except Exception:
            return False

    if preference == "cuda":
        return "cuda" if cuda_ok() else "cpu"
    if preference == "mps":
        return "mps" if mps_ok() else "cpu"
    if preference == "cpu":
        return "cpu"

    # auto
    if cuda_ok():
        return "cuda"
    if mps_ok():
        return "mps"
    return "cpu"


def device_report(preference: str = "auto") -> dict[str, object]:
    """Human-facing device info for the UI/logs (§56)."""
    resolved = resolve_device(preference)
    info: dict[str, object] = {"preference": preference, "device": resolved, "torch": False}
    try:
        import torch  # type: ignore

        info["torch"] = True
        info["torch_version"] = torch.__version__
        if resolved == "cuda":
            info["cuda_device_name"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return info
