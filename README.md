# LipSight

**English silent-video lip reading + multi-person tracking + gaze analysis + synthetic speech.**

LipSight analyzes visible speech from English-language video. You upload a video (up to
~5 minutes, 720p+ recommended), the system detects and tracks **all** reasonably visible people,
scores each person's face quality and lip-reading readiness, and lets you select any qualifying
person to run visual speech recognition, approximate gaze analysis, and optional generic
text-to-speech — all synchronized to a timeline.

> **Honesty first.** Lip reading is probabilistic — the same mouth movement can map to multiple
> words. This system never fabricates ML output. Every ML result is one of `REAL_RESULT`,
> `MODEL_UNAVAILABLE` (naming the exact missing dependency), `LOW_CONFIDENCE` (masked as
> `[uncertain]`), or `NO_SIGNAL`. See [`docs/limitations.md`](docs/limitations.md).

## ✅ Real, working lip reading (not a mock)

The pipeline runs **real models end to end** — a no-audio English video is transcribed from
visible mouth movement alone, visual-only, with rigorous evaluation. Two real models:

- **Open-vocabulary (production):** **SyncVSR** (`Vox+LRS2+LRS3`, Conformer, MIT) — transcribes
  **natural, free-form English** (SentencePiece subwords, no fixed vocabulary/grammar). Runs on
  CPU ~1–2 s per short utterance; GPU-ready. `LIP_READING_MODEL=syncvsr` (default).
- **Benchmark:** **GRID-LipNet** (closed 51-word grammar, MIT) — a fast regression/CI model with
  WER **0.017** on GRID. `LIP_READING_MODEL=lipnet`. Not a production transcriber.

The production test (strips audio first, proving visual-only):

```bash
make install && make install-ml && make download-models     # fetches the 1.14GB SyncVSR ckpt
python scripts/production_lipreading_test.py --video my_no_audio_english.mp4 --ground-truth "..."
# → open-vocabulary transcript + WER/CER/S-D-I, visual-only, on CPU or GPU
```

The GRID benchmark demo (constrained vocabulary):

```bash
make demo   # → "BIN BLUE AT F TWO NOW" (WER 0.000, GRID-LipNet benchmark)
```

> **Open-vocabulary scope & honesty.** SyncVSR is a real sentence-level VSR model; on natural
> connected English it performs at its published LRS-range accuracy. A **natural-English WER
> number** in this repo requires natural-English test videos, which the build environment's
> egress policy blocked from every source — the drop-in harness is ready
> (`evaluation/open_vocabulary/`, `scripts/evaluate_open_vocabulary.py`). See
> `docs/open-vocabulary-model-comparison.md`, `docs/open-vocabulary-evaluation.md`, and
> `docs/current-lipreading-limitations.md`. The app never falls back to GRID silently, never uses
> audio/ASR, and never hallucinates missing words.

Models used: **SyncVSR** (Vox+LRS2+LRS3, Conformer, MIT) for open-vocabulary visual speech
recognition (production); **GRID-LipNet** (MIT) as a closed-vocabulary benchmark/CI model;
**dlib-68** for mouth alignment (research-only license), **MediaPipe** (Apache-2.0) for face
detection + gaze landmarks, **YOLOv8n** (Ultralytics, AGPL-3.0) for person detection. Full
details, sources, licenses, and measured results: [`docs/live-ml-plan.md`](docs/live-ml-plan.md)
and [`docs/lipreading-model-comparison.md`](docs/lipreading-model-comparison.md).

> **Scope & honesty.** The production model (SyncVSR) is a real open-vocabulary sentence-level VSR
> model. Its accuracy on **natural connected English** has not yet been measured in this repo — a
> real natural-English WER requires natural-English test clips, which this environment's egress
> policy blocked. The drop-in evaluation harness (`evaluation/open_vocabulary/`,
> `scripts/evaluate_open_vocabulary.py`, and the in-app Developer evaluation panel) is ready to
> produce that number from a user-supplied clip. This is an **experimental MVP measurement**, not a
> clinical, medical-grade, or production-accuracy claim. The app never uses audio, never falls back
> to GRID for open-vocabulary requests, and never invents words for silent or low-confidence windows.

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
- For the real ML pipeline: system libs `libgl1 libglib2.0-0` (OpenCV/MediaPipe) and
  `espeak-ng` (generic TTS) — `sudo apt-get install -y ffmpeg libgl1 libglib2.0-0 espeak-ng`
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

### Using the web app (primary path — no Python needed)

The browser is the product. At http://localhost:3000 you:

1. **Upload** a video (≤5 min; 720p+, 130px+ face, 25fps+ recommended — MP4/MOV/WebM).
   Low-quality video is **analyzed and reported**, never silently rejected. A **no-audio**
   video is fully supported (`Audio: None`, `Visual-only mode: ACTIVE`); when audio is present
   it is shown as `Present (ignored)` and **never reaches** the VSR/ASR/TTS path.
2. **Scan for people** → every reasonably visible person becomes a gallery card with a
   `READY` / `WARNING` / `INSUFFICIENT` badge (a **combined** readiness score, not a single
   face-size threshold) and a full quality report (face quality, lip-reading readiness, usable
   duration, avg face width, mouth visibility, sharpness, pose, tracking).
3. **Select a person** → **Analyze speech** runs open-vocabulary SyncVSR on *that person's*
   visible mouth movement only (multi-person videos never mix mouths across people).
4. **Read the transcript**, synced to the video: each segment shows text, **confidence %**,
   **visual quality %**, a **Visual Speaking Activity Estimate**
   (`SPEAKING_LIKELY`/`NOT_SPEAKING`/`UNCERTAIN`), source frame range and model window;
   low-confidence text is masked `[uncertain]`, and a genuinely silent stretch reads
   `[no speech evidence]` rather than inventing words. Export **SRT / TXT / JSON / report**.
5. **Debug** (optional): see the exact original / face / lower-face / mouth crops and the
   temporal sequence the model sees. **Developer tools** (optional) expose a ground-truth
   textarea → WER / CER / S·D·I — never shown to normal users.

> **Honest scope.** This is open-vocabulary English *visual* speech recognition — estimates
> from visible lip movement, which is inherently probabilistic. It does not claim natural-English
> professional accuracy, does not "read minds", is not 100% accurate, and cannot hear anything.

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
