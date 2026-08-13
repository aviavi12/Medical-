from abc import ABC, abstractmethod
from pathlib import Path

from app.models.schemas import InspectionResult


class BaseConverter(ABC):
    @abstractmethod
    def inspect(self, file_path: Path) -> InspectionResult:
        ...

    @abstractmethod
    def convert(self, file_path: Path, output_path: Path, **kwargs) -> Path:
        ...
