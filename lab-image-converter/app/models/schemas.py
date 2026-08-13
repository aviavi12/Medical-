from pydantic import BaseModel
from typing import Optional


class FileDetectionResult(BaseModel):
    format: str
    extension: str
    mime_type: str
    confidence: float


class InspectionResult(BaseModel):
    filename: str
    format: str
    size: int
    width: Optional[int] = None
    height: Optional[int] = None
    channels: Optional[int] = None
    z_planes: Optional[int] = None
    time_points: Optional[int] = None
    scenes: Optional[int] = None
    pages: Optional[int] = None
    bit_depth: Optional[int] = None
    mode: Optional[str] = None


class ConversionRequest(BaseModel):
    quality: int = 95
    z: int = 0
    channel: int = 0
    timepoint: int = 0
    scene: int = 0
    page: int = 0


class ConversionResponse(BaseModel):
    success: bool
    filename: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


class BatchFileResult(BaseModel):
    filename: str
    success: bool
    output_filename: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


class BatchConversionResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    output_directory: Optional[str] = None
    files: list[BatchFileResult]
    download_all_url: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
