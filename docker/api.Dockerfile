# SilentSpeak Lab API image.
FROM python:3.11-slim

# FFmpeg for video; libgl/libglib for OpenCV + MediaPipe; espeak-ng for generic TTS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Core deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Optional: uncomment to bake heavy ML runtimes into the image.
# COPY requirements-ml.txt ./
# RUN pip install --no-cache-dir -r requirements-ml.txt

COPY apps ./apps
COPY ml ./ml
COPY database ./database
COPY training ./training
COPY pyproject.toml ./

ENV PYTHONUNBUFFERED=1 STORAGE_PATH=/data/storage
RUN mkdir -p /data/storage

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
