import logging
from pathlib import Path

import numpy as np

from app.converters.base import BaseConverter
from app.models.schemas import InspectionResult
from app.processing.image_processing import normalize_to_uint8, array_to_pil
from app.processing.jpeg_encoder import encode_jpeg

logger = logging.getLogger(__name__)


class CZIConverter(BaseConverter):
    def inspect(self, file_path: Path) -> InspectionResult:
        from aicspylibczi import CziFile

        czi = CziFile(str(file_path))
        dims = czi.get_dims_shape()

        dim_map = dims[0] if dims else {}

        def _dim_size(key: str) -> int:
            val = dim_map.get(key)
            if isinstance(val, (list, tuple)) and len(val) == 2:
                return val[1] - val[0]
            if isinstance(val, int):
                return val
            return 1

        width = _dim_size("X")
        height = _dim_size("Y")
        channels = _dim_size("C")
        z_planes = _dim_size("Z")
        time_points = _dim_size("T")
        scenes = _dim_size("S")

        return InspectionResult(
            filename=file_path.name,
            format="CZI",
            size=file_path.stat().st_size,
            width=width,
            height=height,
            channels=channels,
            z_planes=z_planes,
            time_points=time_points,
            scenes=scenes,
        )

    def convert(self, file_path: Path, output_path: Path, **kwargs) -> Path:
        from aicspylibczi import CziFile

        quality = kwargs.get("quality", 95)
        z = kwargs.get("z", 0)
        channel = kwargs.get("channel", 0)
        timepoint = kwargs.get("timepoint", 0)
        scene = kwargs.get("scene", 0)

        czi = CziFile(str(file_path))
        dims = czi.get_dims_shape()
        dim_map = dims[0] if dims else {}

        read_kwargs = {}
        dim_str = czi.dims if hasattr(czi, "dims") else ""

        if "S" in dim_map and "S" in dim_str:
            read_kwargs["S"] = scene
        if "T" in dim_map and "T" in dim_str:
            read_kwargs["T"] = timepoint
        if "Z" in dim_map and "Z" in dim_str:
            read_kwargs["Z"] = z
        if "C" in dim_map and "C" in dim_str:
            read_kwargs["C"] = channel

        try:
            data, shape_info = czi.read_image(**read_kwargs)
        except TypeError:
            data = czi.read_image(**read_kwargs)
            if isinstance(data, tuple):
                data = data[0]

        data = np.squeeze(data)

        if data.dtype != np.uint8:
            data = normalize_to_uint8(data)

        img = array_to_pil(data)
        encode_jpeg(img, output_path, quality=quality)
        return output_path
