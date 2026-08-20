# SilentSpeak Lab — Implementation Plan

Incremental, milestone-gated build. Each milestone: **implement → test → run → inspect → fix →
document → proceed**. No uncontrolled single pass; no fabricated ML results.

## Status legend
- ✅ done in this repo
- 🟡 interface/seam in place; heavy back-end reports `MODEL_UNAVAILABLE` in this environment
- ⬜ not started

## Milestones

| # | Milestone | Definition of done | Status |
|---|-----------|--------------------|--------|
| 1 | Project skeleton | Next.js + FastAPI + DB + FFmpeg + config + health endpoints + tests; app starts | ✅ |
| 2 | Video upload | Upload + validation + metadata + storage + playback | ✅ |
| 3 | YOLO person detection | All reasonably visible people detected; debug overlays | 🟡 (interface + config; needs `ultralytics`) |
| 4 | Face detection | Best detector chosen from documented benchmark | 🟡 (interface + benchmark harness) |
| 5 | Tracking | Stable person IDs (ByteTrack/BoT-SORT benchmark) | 🟡 (interface) |
| 6 | Person gallery | Thumbnails, metrics, readiness score, selection | 🟡 (API + scoring real; needs detections) |
| 7 | Face landmarks | Mouth & eye regions tracked | 🟡 (interface; needs `mediapipe`) |
| 8 | Mouth extraction | ROI, normalization, temporal sequences, caching | 🟡 (real geometry; needs landmarks) |
| 9 | Lip reading | A real English model produces real transcription, else MODEL UNAVAILABLE | 🟡 (interface + honesty envelope) |
| 10 | Transcript UI | Timestamps, confidence, click-to-seek, raw vs processed | ✅ (UI); data from M9 |
| 11 | Gaze | Head pose, iris/eye, direction, confidence | 🟡 (interface) |
| 12 | Multi-person gaze | Possible gaze toward another person | 🟡 (interface) |
| 13 | TTS | Transcript → synthetic audio (generic voice) | 🟡 (interface; needs `piper`) |
| 14 | Exports | SRT / TXT / JSON / report download | ✅ |
| 15 | Evaluation | WER/CER vs ground truth; benchmark dashboard | 🟡 (metrics implemented; dashboard page) |

## What "🟡" means precisely

The **software architecture** for these milestones is complete and tested: interfaces, adapters,
config wiring, DB schema, API routes, caching, honesty-state envelope, and mock adapters for unit
tests. What is not present in *this* environment is the heavy model runtime (GPU/weights/`torch`/
`mediapipe`/`ultralytics`). Rather than fake outputs, each subsystem factory returns an adapter
that reports `MODEL_UNAVAILABLE` with the exact missing dependency, and the UI renders that state.

To make a 🟡 slot fully live: install its dependency (see `model-selection.md` install summary),
drop in weights, set the corresponding `.env` variable, and the same interface starts returning
`REAL_RESULT`. No caller code changes.

## Build order executed in this repo

1. Environment inspection → `docs/`.
2. **M1** monorepo skeleton, config, DB layer (SQLite fallback), storage provider, health
   endpoints, FastAPI app, Next.js app, Makefile, docker, tests.
3. ML `common` layer: types, honesty envelope, device detection, model registry, quality gates.
4. Subsystem interfaces + factories + mock/unavailable adapters (detection, tracking, association,
   quality, landmarks, mouth, lipreading, gaze, tts).
5. **M2** upload → validate → ffprobe metadata → store → DB → frame sampling.
6. Person-gallery API + readiness scoring (real math over whatever detections exist).
7. Exports (SRT/TXT/JSON/report) + transcript/gaze schemas.
8. Tests across api / unit / ml; run green.

## Testing strategy

- Unit tests cover every interface, quality scoring, timestamp preservation, export generation,
  gaze classification, and the honesty envelope.
- API tests exercise upload validation, metadata, status state machine, people, exports.
- Mock adapters (guarded by `ALLOW_MOCK_INFERENCE`) let the full pipeline run in CI without GPUs.
- Failure tests: empty/corrupt/oversize/over-duration/unsupported video, missing model, CPU-only.

## Deferred (not in MVP, architected-for) — §103

multilingual, extra VSR models, diarization, GPU worker cluster, cloud storage, auth providers,
team projects, fine-tuning, human transcript correction, active learning, confidence calibration.
