import logging
import time
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse

from app.config import MAX_UPLOAD_SIZE_BYTES, SUPPORTED_EXTENSIONS, DEFAULT_JPEG_QUALITY
from app.detection.detector import detect_file_type
from app.converters.czi_converter import CZIConverter
from app.converters.tiff_converter import TIFFConverter
from app.converters.image_converter import ImageConverter
from app.models.schemas import InspectionResult, ConversionResponse, HealthResponse
from app.processing.jpeg_encoder import validate_jpeg
from app.utils.files import (
    save_upload,
    generate_conversion_id,
    register_output,
    get_output_path,
    get_output_dir,
    cleanup_upload,
)
from app.utils.security import sanitize_filename, safe_output_filename

logger = logging.getLogger(__name__)
router = APIRouter()

czi_converter = CZIConverter()
tiff_converter = TIFFConverter()
image_converter = ImageConverter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@router.post("/api/inspect", response_model=InspectionResult)
async def inspect_file(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the maximum allowed size.")

    safe_name = sanitize_filename(file.filename or "upload")
    ext = Path(safe_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="This file format is not supported.\n\nSupported: CZI, TIFF/TIF, PNG, JPEG/JPG",
        )

    upload_path = save_upload(content, safe_name)

    try:
        detection = detect_file_type(upload_path)
        if detection.format == "UNKNOWN":
            raise HTTPException(
                status_code=400,
                detail="This file format is not supported.\n\nSupported: CZI, TIFF/TIF, PNG, JPEG/JPG",
            )

        if detection.format == "CZI":
            result = czi_converter.inspect(upload_path)
        elif detection.format == "TIFF":
            result = tiff_converter.inspect(upload_path)
        else:
            result = image_converter.inspect(upload_path)

        result.filename = safe_name
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Inspection failed")
        raise HTTPException(status_code=500, detail=f"The file could not be read as a valid image. {str(e)}")
    finally:
        cleanup_upload(upload_path)


@router.post("/api/convert", response_model=ConversionResponse)
async def convert_file(
    file: UploadFile = File(...),
    quality: int = Form(DEFAULT_JPEG_QUALITY),
    z: int = Form(0),
    channel: int = Form(0),
    timepoint: int = Form(0),
    scene: int = Form(0),
    page: int = Form(0),
):
    start_time = time.time()
    request_id = generate_conversion_id()

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the maximum allowed size.")

    safe_name = sanitize_filename(file.filename or "upload")
    ext = Path(safe_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="This file format is not supported.\n\nSupported: CZI, TIFF/TIF, PNG, JPEG/JPG",
        )

    quality = max(1, min(100, quality))
    upload_path = save_upload(content, safe_name)

    try:
        detection = detect_file_type(upload_path)
        if detection.format == "UNKNOWN":
            raise HTTPException(
                status_code=400,
                detail="This file format is not supported.\n\nSupported: CZI, TIFF/TIF, PNG, JPEG/JPG",
            )

        output_name = safe_output_filename(safe_name, ".jpg")
        conversion_id = generate_conversion_id()
        output_path = get_output_dir() / f"{conversion_id}_{output_name}"

        logger.info(
            f"[{request_id}] Converting {safe_name} (format={detection.format}, "
            f"size={len(content)})"
        )

        if detection.format == "CZI":
            czi_converter.convert(
                upload_path,
                output_path,
                quality=quality,
                z=z,
                channel=channel,
                timepoint=timepoint,
                scene=scene,
            )
        elif detection.format == "TIFF":
            tiff_converter.convert(
                upload_path, output_path, quality=quality, page=page
            )
        else:
            image_converter.convert(upload_path, output_path, quality=quality)

        if not validate_jpeg(output_path):
            raise HTTPException(
                status_code=500,
                detail="Conversion produced an invalid JPEG file.",
            )

        register_output(conversion_id, output_path)
        duration = time.time() - start_time
        logger.info(f"[{request_id}] Conversion successful in {duration:.2f}s")

        return ConversionResponse(
            success=True,
            filename=output_name,
            download_url=f"/api/download/{conversion_id}",
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"[{request_id}] Conversion failed")
        raise HTTPException(
            status_code=500,
            detail=f"The file could not be converted. {str(e)}",
        )
    finally:
        cleanup_upload(upload_path)


@router.get("/api/download/{conversion_id}")
async def download_file(conversion_id: str):
    output_path = get_output_path(conversion_id)
    if not output_path:
        raise HTTPException(status_code=404, detail="File not found or expired.")

    return FileResponse(
        path=str(output_path),
        media_type="image/jpeg",
        filename=output_path.name.split("_", 1)[-1] if "_" in output_path.name else output_path.name,
    )
