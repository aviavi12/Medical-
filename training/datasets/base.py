"""DatasetAdapter interface (§28).

Datasets (LRS2/LRS3/GRID/LRW) are used ONLY per their licenses. This adapter
never auto-downloads license-gated data; ``download`` refuses and points the user
to the manual acceptance step when a license requires it (§72).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DatasetManifest:
    name: str
    root: str
    samples: list[dict] = field(default_factory=list)
    splits: dict[str, list[int]] = field(default_factory=dict)
    license: str = "unknown"


class DatasetLicenseError(RuntimeError):
    """Raised when a dataset requires manual license acceptance (§72)."""


class DatasetAdapter(ABC):
    name = "dataset"
    license = "unknown"
    requires_manual_acceptance = True

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @abstractmethod
    def download(self) -> None:
        """Obtain the data. Must refuse to auto-download license-gated datasets."""

    @abstractmethod
    def prepare(self) -> None:
        """Run face detection → alignment → mouth extraction → sequence creation."""

    @abstractmethod
    def validate(self) -> list[str]:
        """Return a list of problems (empty if the dataset looks correct)."""

    @abstractmethod
    def create_manifest(self) -> DatasetManifest: ...

    @abstractmethod
    def create_splits(self, manifest: DatasetManifest) -> DatasetManifest: ...

    def guard_license(self) -> None:
        if self.requires_manual_acceptance:
            raise DatasetLicenseError(
                f"Dataset '{self.name}' ({self.license}) requires manual license acceptance "
                f"and download. Obtain it yourself and place it under {self.root}. "
                "This tool will not auto-download license-gated data."
            )
