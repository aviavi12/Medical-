# SilentSpeak Lab — Architecture

> English silent-video lip reading + multi-person tracking + gaze analysis + synthetic speech.

This document describes the system architecture. It is a living document; sections marked
**(planned)** describe interfaces that exist as clean seams but whose heavy ML back-ends are
not yet runnable in every environment (see [model-selection.md](./model-selection.md) and
[limitations.md](./limitations.md)).

## 1. Core principle

The pipeline is decomposed into **independent subsystems** with clean interfaces. No monolithic
script performs everything. Subsystems:

```
DETECTION → TRACKING → FACE ANALYSIS → LIP READING → GAZE ESTIMATION → TEXT-TO-SPEECH
```

Each subsystem is a Python package under `ml/` with a stable base interface and pluggable
**adapters**, so any individual model can be swapped later without touching callers.

## 2. The honesty contract

Silent lip reading is an *inference* problem — the same mouth shape maps to multiple sounds.
The system therefore **never** presents visual speech recognition as ground truth and **never**
fabricates ML output. Every ML result carries one of four explicit states:

| State | Meaning |
|-------|---------|
| `REAL_RESULT` | A real model performed inference and produced this output. |
| `MODEL_UNAVAILABLE` | Weights / deps / GPU / license missing. `detail` names exactly what is missing. |
| `LOW_CONFIDENCE` | A real model ran but confidence is below threshold → text is masked with `[uncertain]`. |
| `NO_SIGNAL` | Visual quality gates failed; the expensive model was intentionally not run. |

The `mock_adapter` exists **only** for unit tests and can never surface as a production result
(a runtime guard blocks it unless `ALLOW_MOCK_INFERENCE=1`).

## 3. High-level component map

```
                         VIDEO (≤ ~5 min, 720p+ recommended)
                                     │
                          ┌──────────▼──────────┐
                          │  FFmpeg / ffprobe   │  validation + metadata
                          └──────────┬──────────┘
                                     ▼
                           FRAME SAMPLING (coarse 5–10 fps)
                                     │
     ┌───────────────────────────────┼──────────────────────────────────┐
     ▼                               ▼                                    ▼
 PersonDetector               FaceDetector                        FaceQualityEstimator
 (YOLO family)          (YOLO-face vs MediaPipe)             blur/pose/visibility/…
     │                               │                                    │
     └──────────────┬────────────────┘                                    │
                    ▼                                                      │
             PersonTracker  (ByteTrack / BoT-SORT)                        │
                    │                                                      │
                    ▼                                                      │
          FacePersonAssociation ◄─────────────────────────────────────────┘
                    │
                    ▼
             PERSON GALLERY  (readiness score per person)
                    │
                    ▼   ← USER SELECTS PERSON N (Stage B begins)
     ┌──────────────┴───────────────┐
     ▼                              ▼
 FaceAlignment                 (cached coarse-scan data reused, never recomputed)
     ▼
 FaceLandmarks  (MediaPipe Face Landmarker)
     │
 ┌───┴─────────────┐
 ▼                 ▼
 MouthExtractor    Eyes / Iris
 ▼                 ▼
 TemporalMouthSeq  HeadPose
 ▼                 ▼
 LipReadingModel   GazeEstimator
 ▼                 ▼
 ENGLISH TRANSCRIPT   GAZE DATA
     └───────┬─────────┘
             ▼
       TIMELINE ENGINE
     ┌───────┴────────┐
     ▼                ▼
 TRANSCRIPT        GAZE TIMELINE
     ▼
 OPTIONAL GENERIC TTS → SYNTHETIC AUDIO
     ▼
 EXPORTS (SRT / TXT / JSON / report)
```

## 4. Two-stage processing (§17)

- **Stage A — Coarse scan.** The whole video is scanned at `COARSE_FPS` (default 8) for person
  detection, face detection, tracking, and quality. Expensive lip reading is **not** run here.
  Output: the person gallery with per-person readiness scores.
- **Stage B — Selected person.** After the user picks a person, only that person's high-quality
  frames feed alignment → landmarks → mouth ROI → lip reading → gaze. This is where GPU-heavy
  inference happens, on one track instead of all of them.

Everything in Stage A is **cached** (§59). Selecting a second person reuses detection/tracking
and only re-runs Stage B.

## 5. Technology stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js (App Router) + TypeScript + Tailwind + shadcn/ui-style components |
| Backend | Python + FastAPI, fully typed with Pydantic schemas |
| ML | PyTorch, OpenCV, NumPy, ONNX Runtime (where useful) |
| Video | FFmpeg / ffprobe |
| DB | PostgreSQL in production; SQLAlchemy with a SQLite fallback for local/dev/test |
| Storage | `StorageProvider` abstraction — local filesystem in dev, S3-compatible in prod |
| Background work | Local in-process worker now; interface compatible with Celery + Redis later |

### Why SQLite fallback?
The schema is authored for PostgreSQL. `DATABASE_URL` selects the engine; when it is unset the
app uses a local SQLite file so the API and the full test-suite run with zero external services.
No business logic assumes a specific engine — only the connection string changes.

## 6. Repository layout

```
apps/
  api/            FastAPI app: routes, services, schemas, workers, dependencies
  web/            Next.js frontend
ml/
  common/         shared types, device detection, model registry, result envelope
  detection/      PersonDetector, FaceDetector + adapters
  tracking/       PersonTracker + adapters (ByteTrack / BoT-SORT)
  association/    face↔person association
  quality/        face quality, blur, visibility, readiness score
  landmarks/      face landmarks
  mouth/          alignment, extraction, normalization
  lipreading/     base, inference, pre/post-processing, adapters
  gaze/           base, head pose, iris, estimator
  tts/            base + providers
database/         SQLAlchemy models + migrations
training/         dataset adapters, configs, scripts, evaluation (offline only)
tests/            unit / integration / api / ml
scripts/          benchmark + utility scripts
storage/          dev filesystem storage (gitignored)
docker/           Dockerfiles
docs/             this documentation
```

## 7. Subsystem interfaces (contracts)

Every ML subsystem returns typed dataclasses (see `ml/common/types.py`) and an availability
report. The key contracts:

- `PersonDetector.detect(frame) -> list[PersonDetection]`
- `FaceDetector.detect(frame) -> list[FaceDetection]`
- `PersonTracker.update(detections, frame_index) -> list[Track]`
- `FaceQualityEstimator.score(frame, face_bbox) -> FaceQuality`
- `FaceLandmarker.landmarks(frame, face_bbox) -> FaceLandmarks | None`
- `MouthExtractor.extract(frame, landmarks) -> MouthCrop`
- `LipReadingModel.predict(sequence) -> LipReadingResult`  *(carries the honesty state)*
- `GazeEstimator.estimate(landmarks, head_pose) -> GazeResult`
- `TextToSpeechProvider.synthesize(text) -> AudioArtifact`

Each package exposes a factory (`get_<subsystem>()`) that reads configuration and returns the
configured adapter, falling back to an "unavailable" adapter that reports precisely what is
missing rather than crashing.

## 8. Model registry & memory (§58)

`ml/common/registry.py` holds a process-wide registry that lazily loads each heavy model **once
per worker** and can unload it to free GPU/CPU memory. Frame loops never re-instantiate networks.

## 9. Device handling (§57)

`ml/common/device.py` resolves `DEVICE=auto` to CUDA → MPS → CPU in that order, never crashing
when CUDA is absent, and reports the *actual* device used back to the UI and logs.

## 10. Processing state machine (§55)

A processing job moves through explicit statuses:

```
QUEUED → VALIDATING → EXTRACTING_METADATA → DETECTING_PEOPLE → DETECTING_FACES →
TRACKING → QUALITY_ANALYSIS → READY_FOR_SELECTION →
ANALYZING_PERSON → EXTRACTING_MOUTH → LIP_READING → GAZE_ANALYSIS → FINALIZING → COMPLETED
                                                                        (FAILED / CANCELLED)
```

Progress (stage, %, elapsed, ETA, device) is exposed via `GET /api/videos/{id}/status`.

## 11. Security & privacy posture

Uploaded video is untrusted input: extension + MIME + size + duration validation, filename
sanitisation, path-traversal protection, isolated processing dirs, and no execution of uploaded
content. Processing is local by default; nothing leaves the machine unless an external provider
is explicitly configured, and every external dependency is documented. Users can delete the
original video, derived artifacts, generated audio, or an entire project.
