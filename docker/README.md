# Docker & GPU notes

## Quick start (CPU)
```bash
docker compose up --build
# web → http://localhost:3000   api → http://localhost:8000
```

## Heavy ML runtimes
The default API image installs only `requirements.txt`. To run real models, either:
- uncomment the `requirements-ml.txt` lines in `docker/api.Dockerfile`, or
- install them into a running container / derived image.

## GPU (NVIDIA CUDA)
1. Install the NVIDIA Container Toolkit on the host.
2. Use a CUDA base image and a CUDA-matched PyTorch wheel in `api.Dockerfile`.
3. Add a GPU reservation to the `api` (and `worker`) service:

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

`DEVICE=auto` inside the app resolves to CUDA when available and falls back to CPU otherwise.

## Storage
The `storage` volume holds uploaded videos and derived artifacts. In production, set
`STORAGE_BACKEND=s3` and the `S3_*` variables to use S3-compatible object storage instead.
