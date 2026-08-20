"""Process-wide model registry (§58).

Heavy models are loaded lazily **once per worker** and can be unloaded to free
memory. Frame loops must fetch models through this registry, never construct a
network per frame.
"""

from __future__ import annotations

import threading
from typing import Any, Callable


class ModelRegistry:
    """Thread-safe lazy singleton store for expensive models."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instances: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}

    def register(self, key: str, factory: Callable[[], Any]) -> None:
        with self._lock:
            self._factories[key] = factory

    def get(self, key: str, factory: Callable[[], Any] | None = None) -> Any:
        """Return the model for ``key``, constructing it once on first use."""
        with self._lock:
            if key in self._instances:
                return self._instances[key]
            f = factory or self._factories.get(key)
            if f is None:
                raise KeyError(f"No factory registered for model '{key}'")
            instance = f()
            self._instances[key] = instance
            return instance

    def is_loaded(self, key: str) -> bool:
        with self._lock:
            return key in self._instances

    def unload(self, key: str) -> bool:
        """Unload a model and best-effort free GPU memory."""
        with self._lock:
            inst = self._instances.pop(key, None)
        if inst is None:
            return False
        _free_memory()
        return True

    def clear(self) -> None:
        with self._lock:
            self._instances.clear()
        _free_memory()

    def loaded_keys(self) -> list[str]:
        with self._lock:
            return list(self._instances.keys())


def _free_memory() -> None:
    try:
        import gc

        gc.collect()
        import torch  # type: ignore

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


# Global registry used by subsystem factories.
REGISTRY = ModelRegistry()
