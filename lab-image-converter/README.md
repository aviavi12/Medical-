# Laboratory Image Converter

A simple MVP web application that converts laboratory microscopy and scientific image files into standard JPEG images.

## What It Does

Upload a CZI, TIFF, or standard image file. The application reads it, lets you select specific planes/channels if the file contains multiple, converts it to JPEG, and provides a download.

**Important:** JPEG is a lossy, 8-bit-oriented presentation format. It should NOT replace the original scientific CZI/TIFF file. Always retain originals for scientific analysis and archival purposes.

## Supported Input Formats

| Format | Extension | Library Used |
|--------|-----------|-------------|
| Zeiss CZI | `.czi` | aicspylibczi |
| TIFF | `.tif`, `.tiff` | tifffile |
| PNG | `.png` | Pillow |
| JPEG | `.jpg`, `.jpeg` | Pillow |

### Fiji Compatibility

Fiji (ImageJ) exports images primarily as TIFF, PNG, and JPEG. All of these are supported. TIFF files from Fiji use the same TIFF processing pipeline (tifffile). Not every proprietary Fiji plugin format is supported.

## Output Format

JPEG only (`.jpg`). Quality is configurable (80, 90, 95, 100). Default: 95.

## How CZI Works

CZI files from Zeiss microscopes can contain multiple dimensions:
- **X, Y** — spatial dimensions
- **Z** — Z-stack (focal planes)
- **C** — channels (fluorescence channels, not necessarily RGB)
- **T** — time points
- **S** — scenes

When a CZI has multiple Z planes, channels, or time points, the UI shows selectors so you can choose which specific image plane to convert. Single-channel data converts to grayscale JPEG. Multi-channel data with RGB-compatible channels preserves color.

## How TIFF Works

The converter handles 8-bit, 16-bit, and 32-bit TIFF images (grayscale, RGB, RGBA). For multi-page TIFFs, the UI shows a page selector.

Scientific images with bit depths above 8-bit are normalized to 0-255 using min/max normalization before JPEG encoding. This preserves visual contrast but reduces scientific precision — the original file remains unchanged.

## Installation

### Prerequisites

- Python 3.10+ (recommended: Python 3.12)

### Windows (Recommended for most users)

1. Extract the `lab-image-converter-portable.tar.gz` file
2. Open the `lab-image-converter` folder
3. Double-click **`install.bat`**
4. After installation, double-click **"LabFile Converter"** on your Desktop

### Linux / macOS

1. Extract the archive:
   ```bash
   tar xzf lab-image-converter-portable.tar.gz
   cd lab-image-converter
   bash install.sh
   ```
2. Double-click the **"LabFile Converter"** icon on your Desktop, or run:
   ```bash
   bash launch.sh
   ```

### Manual Setup (any OS)

```bash
cd lab-image-converter
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate
# Activate (Windows)
.venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000 in your browser.

### Docker

```bash
docker compose up --build
```

Open http://localhost:8000 in your browser.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI |
| GET | `/health` | Health check |
| POST | `/api/inspect` | Upload and inspect a file |
| POST | `/api/convert` | Convert a file to JPEG |
| GET | `/api/download/{id}` | Download converted JPEG |

### POST /api/inspect

Upload a file as multipart form data. Returns metadata:

```json
{
  "filename": "sample.czi",
  "format": "CZI",
  "size": 123456,
  "width": 2048,
  "height": 2048,
  "channels": 3,
  "z_planes": 1,
  "time_points": 1
}
```

### POST /api/convert

Upload a file with conversion parameters:

- `file` — the image file
- `quality` — JPEG quality (1-100, default 95)
- `z` — Z plane index (CZI, default 0)
- `channel` — channel index (CZI, default 0)
- `timepoint` — time point index (CZI, default 0)
- `scene` — scene index (CZI, default 0)
- `page` — page index (TIFF, default 0)

Returns:

```json
{
  "success": true,
  "filename": "sample.jpg",
  "download_url": "/api/download/abc123..."
}
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_MB` | 2048 | Maximum upload file size in MB |
| `DEFAULT_JPEG_QUALITY` | 95 | Default JPEG quality |
| `CLEANUP_AFTER_DOWNLOAD` | false | Delete temp files after download |

## Testing

```bash
pytest tests/ -v
```

CZI integration tests require real `.czi` fixture files. Place them in `tests/fixtures/czi/` and uncomment the integration tests in `tests/test_czi.py`.

## Known Limitations

- JPEG output only — no PNG, PDF, or other output formats
- CZI support depends on aicspylibczi compatibility with the specific CZI file version
- No batch conversion mode (one file at a time)
- No authentication or multi-user support
- Temporary files accumulate during development (cleanup is configurable)
- Very large files (>2GB) may require increased memory
- JPEG conversion loses bit depth, metadata, and scientific precision
- Multi-channel CZI images default to single-channel grayscale unless channels are RGB-compatible
