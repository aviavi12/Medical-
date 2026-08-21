# SilentSpeak Lab

**English silent-video lip reading + multi-person tracking + gaze analysis + synthetic speech.**

SilentSpeak Lab analyzes visible speech from English-language video. You upload a video (up to
~5 minutes, 720p+ recommended), the system detects and tracks **all** reasonably visible people,
scores each person's face quality and lip-reading readiness, and lets you select any qualifying
person to run visual speech recognition, approximate gaze analysis, and optional generic
text-to-speech — all synchronized to a timeline.

> **Honesty first.** Lip reading is probabilistic — the same mouth movement can map to multiple
> words. This system never fabricates ML output. Every ML result is one of `REAL_RESULT`,
> `MODEL_UNAVAILABLE` (naming the exact missing dependency), `LOW_CONFIDENCE` (masked as
> `[uncertain]`), or `NO_SIGNAL`. See [`docs/limitations.md`](docs/limitations.md).

## ✅ Real, working lip reading (not a mock)

The core pipeline runs **real models end to end** — a no-audio English video is transcribed
from mouth movement alone by a real English visual speech recognition model (**LipNet**, GRID),
with rigorous evaluation:

| Split | WER | CER | Sentence accuracy | Speed (CPU) |
|-------|-----|-----|-------------------|-------------|
| overlap (default) | **0.017** | **0.004** | **90%** (9/10) | ~0.09 s / 3-s clip |
| unseen speakers | 0.017 | 0.005 | 90% | ~0.08 s / clip |

Try it in one command (audio is stripped first, proving the transcript is visual-only):

```bash
make install && make install-ml && make download-models
make demo
# → "BIN BLUE AT F TWO NOW"  (= ground truth, WER 0.000)
```

Models used: **LipNet-GRID** (Fengdalu/LipNet-PyTorch, MIT) for visual speech recognition,
**dlib-68** for mouth alignment (research-only license), **MediaPipe** (Apache-2.0) for face
detection + gaze landmarks, **YOLOv8n** (Ultralytics, AGPL-3.0) for person detection. Full
details, sources, licenses, and measured results: [`docs/live-ml-plan.md`](docs/live-ml-plan.md)
and [`docs/lipreading-model-comparison.md`](docs/lipreading-model-comparison.md).

> **Scope:** the shipped checkpoint is trained on GRID's 6-word command grammar — the "suitable
> English video" domain. It is not yet an open-vocabulary conversational lip reader; upgrading to
> AV-HuBERT/Auto-AVSR is a drop-in adapter once those weights are reachable (their hosts are
> blocked by this environment's egress policy). The app reports `MODEL_UNAVAILABLE`/`NO_SIGNAL`
> rather than hallucinating out-of-domain speech.

---

## Architecture

Modular subsystems with clean interfaces, wired together by a two-stage pipeline:

```
VIDEO → FFmpeg → frame sampling → YOLO person detection → face detection →
tracking (ByteTrack/BoT-SORT) → quality scoring → PERSON GALLERY →
[select person] → face alignment → landmarks → mouth ROI → temporal sequence →
visual speech recognition → transcript ┐
                              gaze estimation ┘ → timeline → optional TTS → exports
```

- **Stage A (coarse scan)** runs detection/tracking/quality over the whole video at `COARSE_FPS`.
- **Stage B (selected person)** runs the expensive lip-reading + gaze only on the chosen person.
- Everything in Stage A is cached, so selecting another person never re-runs detection.

See [`docs/architecture.md`](docs/architecture.md), [`docs/model-selection.md`](docs/model-selection.md),
and [`docs/implementation-plan.md`](docs/implementation-plan.md).

### Layout
```
apps/api    FastAPI backend (routes, services, workers, schemas)
apps/web    Next.js + TypeScript + Tailwind frontend
ml/         detection, tracking, association, quality, landmarks, mouth,
            lipreading, gaze, tts — interfaces + adapters + honesty envelope
database/   SQLAlchemy models (+ SQLite dev fallback)
training/   dataset adapters, configs, evaluation (offline only)
tests/      unit / api / ml / integration
scripts/    benchmark + utilities
docs/       documentation
```

## Requirements

- Python 3.11+
- Node 20+ (for the frontend)
- FFmpeg (`ffmpeg` + `ffprobe` on PATH) — required for real video metadata & frames
- PostgreSQL (optional; SQLite is used automatically when `DATABASE_URL` is unset)
- Optional GPU (CUDA) or Apple Silicon (MPS) — CPU is a supported fallback
- Optional heavy ML runtimes (`requirements-ml.txt`) for the real models

## Installation

```bash
# 1. Backend + CV runtime (enough for API, metadata, tests with mock ML)
make install                 # creates .venv and installs requirements.txt

# 2. (optional) heavy ML runtimes — torch, ultralytics, mediapipe, ...
make install-ml

# 3. Frontend
make web-install

# 4. FFmpeg
#   Debian/Ubuntu:  sudo apt-get install -y ffmpeg
#   macOS:          brew install ffmpeg

# 5. Config
cp .env.example .env         # every value has a safe default
```

### GPU setup
Install the CUDA/MPS-matched PyTorch wheel from https://pytorch.org, then `make install-ml`.
`DEVICE=auto` resolves to cuda → mps → cpu and never crashes when a GPU is absent; the actual
device is shown in `/health` and the UI.

## Running locally

```bash
# Backend  → http://localhost:8000  (docs at /docs)
make api

# Frontend → http://localhost:3000  (proxies /api and /media to the backend)
make web
```

Then open http://localhost:3000, upload a 720p+ video, run the coarse scan, pick a person, and
analyze.

## Running tests

```bash
make test          # full suite; uses SQLite + mock ML adapters, needs no GPU/weights
```

The mock adapters (guarded by `ALLOW_MOCK_INFERENCE`) let the whole pipeline run in CI. They emit
obviously-synthetic placeholders and can never surface as a production result.

## Running inference (real models)

```bash
make install-ml         # torch, torchvision, ultralytics, mediapipe, dlib-bin
make download-models    # LipNet + dlib-68 + yolov8n + GRID fixtures → ./models
python scripts/demo.py                                   # one-command real demo
python scripts/run_real_lipreading.py --video my.mp4 --output results/
pytest tests/live -m live                                # real WER + no-audio acceptance
```

Weights auto-resolve from `MODELS_DIR` (default `./models`); override with
`LIP_READING_WEIGHTS`, `DLIB_LANDMARKS`, `YOLO_PERSON_WEIGHTS` if needed. Any subsystem still
missing a dependency reports `MODEL_UNAVAILABLE` with the exact gap — it never fakes results.
See [`docs/live-ml-plan.md`](docs/live-ml-plan.md).

## Training & evaluation

Training is offline and separate from inference. Datasets (LRS2/LRS3/GRID/LRW) must be obtained
under their own licenses — this repo never auto-downloads license-gated data.

```bash
python -m training.prepare_dataset --config training/configs/lipreading.yaml
python -m training.train          --config training/configs/lipreading.yaml
python -m training.evaluate       --config training/configs/lipreading.yaml
```

Metrics (WER/CER/sentence accuracy) live in `training/evaluation` and power the `/api/evaluation`
endpoint and the in-app Evaluation page.

## Benchmarking

```bash
python scripts/benchmark_pipeline.py --video path/to/clip.mp4 --report out/bench.json
```
Reports per-stage latency, FPS, and device. Model-selection benchmarks are recorded in
[`docs/model-benchmark.md`](docs/model-benchmark.md).

## Docker

```bash
docker compose up --build     # web + api + postgres (+ optional worker/redis)
```
GPU configuration is documented in [`docker/README.md`](docker/README.md).

## Privacy

Processing is **local by default**; nothing leaves your machine unless you explicitly configure an
external provider (every external service is documented). You can delete the original video,
derived artifacts, generated audio, or the entire project. Uploaded video is treated as untrusted
input (extension/MIME/size/duration validation, filename sanitisation, path-traversal protection,
isolated processing, no execution of uploaded files).

## Limitations

Lip reading is probabilistic; gaze is approximate; accuracy depends heavily on face visibility,
resolution, pose, and lighting; synthetic speech is not the original audio and never clones a real
voice; the system infers nothing about thoughts or intentions. See
[`docs/limitations.md`](docs/limitations.md).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/health` shows `ffmpeg: false` | Install FFmpeg and ensure `ffprobe` is on PATH. |
| People list is empty after scan; status `FAILED` | Person detector deps missing — `make install-ml` + weights (the error names the gap). |
| Transcript shows `MODEL UNAVAILABLE` | Install the lip-reading model + weights and accept its license. |
| Upload rejected | Check extension/MIME/size/duration limits in `.env`. |
| No GPU detected | Expected on CPU-only hosts; `DEVICE=auto` falls back to CPU. |
