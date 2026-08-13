from pathlib import Path

import numpy as np
import tifffile

from app.converters.base import BaseConverter
from app.models.schemas import InspectionResult
from app.processing.image_processing import normalize_to_uint8, array_to_pil
from app.processing.jpeg_encoder import encode_jpeg


class TIFFConverter(BaseConverter):
    def inspect(self, file_path: Path) -> InspectionResult:
        with tifffile.TiffFile(str(file_path)) as tif:
            num_pages = len(tif.pages)
            first_page = tif.pages[0]
            shape = first_page.shape
            dtype = first_page.dtype

            height = shape[0] if len(shape) >= 2 else None
            width = shape[1] if len(shape) >= 2 else None
            channels = shape[2] if len(shape) >= 3 else 1

            bit_depth = dtype.itemsize * 8 if dtype else None

            return InspectionResult(
                filename=file_path.name,
                format="TIFF",
                size=file_path.stat().st_size,
                width=width,
                height=height,
                channels=channels,
                pages=num_pages,
                bit_depth=bit_depth,
            )

    def convert(self, file_path: Path, output_path: Path, **kwargs) -> Path:
        quality = kwargs.get("quality", 95)
        page = kwargs.get("page", 0)

        with tifffile.TiffFile(str(file_path)) as tif:
            num_pages = len(tif.pages)
            if page < 0 or page >= num_pages:
                raise ValueError(
                    f"Page {page} out of range. This TIFF has {num_pages} page(s)."
                )

            data = tif.pages[page].asarray()

        if data.dtype != np.uint8:
            data = normalize_to_uint8(data)

        img = array_to_pil(data)
        encode_jpeg(img, output_path, quality=quality)
        return output_path
