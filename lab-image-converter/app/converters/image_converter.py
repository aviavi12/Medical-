from pathlib import Path

from PIL import Image

from app.converters.base import BaseConverter
from app.models.schemas import InspectionResult
from app.processing.image_processing import ensure_rgb
from app.processing.jpeg_encoder import encode_jpeg


class ImageConverter(BaseConverter):
    def inspect(self, file_path: Path) -> InspectionResult:
        with Image.open(file_path) as img:
            return InspectionResult(
                filename=file_path.name,
                format=img.format or "UNKNOWN",
                size=file_path.stat().st_size,
                width=img.width,
                height=img.height,
                channels=len(img.getbands()),
                mode=img.mode,
            )

    def convert(self, file_path: Path, output_path: Path, **kwargs) -> Path:
        quality = kwargs.get("quality", 95)

        with Image.open(file_path) as img:
            if img.mode == "L":
                encode_jpeg(img, output_path, quality=quality)
            else:
                rgb = ensure_rgb(img)
                encode_jpeg(rgb, output_path, quality=quality)

        return output_path
