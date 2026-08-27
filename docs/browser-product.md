# LipSight — Browser Product & Real-World Failure Matrix

This document records the **user-testable, browser-driven** product: upload → scan →
select person → **Analyze speech** (open-vocabulary SyncVSR, visual-only) → timestamped
transcript with confidence, visual quality, speaking-activity and provenance → export.
No Python commands are required; the CLI remains for testing only.

Everything below was exercised against the **running app** (FastAPI backend on :8000 +
Next.js frontend on :3000, proxying `/api`), on **CPU**, with the real 1.14 GB SyncVSR
`Vox+LRS2+LRS3` checkpoint.

## End-to-end flow (verified)

| Step | Endpoint (browser) | Result |
|------|--------------------|--------|
| Upload no-audio 720p | `POST /api/videos` | `has_audio:false`, stored, metadata probed |
| Scan for people | `POST /api/videos/{id}/analyze` → `GET …/status` | `READY_FOR_SELECTION`, people with status + quality report |
| People gallery | `GET …/people` | `READY`/`WARNING`/`INSUFFICIENT` + full quality report + reasons |
| Analyze speech | `POST …/people/{pid}/analyze` | `REAL_RESULT`, SyncVSR transcript |
| Transcript | `GET …/people/{pid}/transcript` | text + confidence + visual quality + activity + frame range + window + person_id |
| Debug crops | `GET …/people/{pid}/debug` | original/face/lower-face/mouth + temporal strip |
| Evaluate (dev) | `POST …/people/{pid}/evaluate` | WER/CER/S·D·I vs pasted ground truth |
| Export | `GET …/people/{pid}/export/{srt,txt,json,report}` | timeline-synced files |

## Real-world failure test matrix (§27)

Legend: ✅ verified against the running app · 🧪 covered by an automated test ·
🟡 handled by design (not reproduced end-to-end in this environment).

| # | Scenario | Handling | Status |
|---|----------|----------|--------|
| 1 | Frontal single person, no audio, 720p | Real transcript; WER 0.167 on GRID `lrwp9a` | ✅ |
| 2 | Audio **present** but visual-only | `has_audio:true`, shown `Present (ignored)`; transcript still produced from frames only — audio never enters VSR | ✅ |
| 3 | No-audio video (mandatory) | Never fails; `Audio: None`, `Visual-only mode: ACTIVE` | ✅ |
| 4 | Two people, side by side (1280×720) | Both detected on correct sides | ✅ 🧪 |
| 5 | Secondary / side person selected | LEFT person's transcript isolates to its own clip (own-side WER < neighbour) | ✅ 🧪 `tests/live/test_openvocab_multiperson.py` |
| 6 | Left / right edge-of-frame person | Eligible if thresholds met; face detector + per-person ROI crop | 🟡 |
| 7 | Sub-threshold / small or soft face | `WARNING`/`INSUFFICIENT` with specific reasons; not silently rejected | ✅ |
| 8 | Silent (visible, not speaking) | `[no speech evidence]`, activity `NOT_SPEAKING`, conf 0.00 — no invented words | ✅ |
| 9 | Motion blur / low sharpness | Scored; surfaced as a `WARNING` reason ("soft / motion-blurred") | ✅ |
| 10 | 3 people | Face-driven gallery scales to N tracked faces | 🟡 |
| 11 | Person enters / exits mid-video | Tracking spans; `usable_duration` reflects on-screen time | 🟡 |
| 12 | Occlusion (hand/mic over mouth) | Lowers mouth-visibility → reason + lower readiness | 🟡 |
| 13 | Low light | Brightness feeds face quality → reason/gate | 🟡 |
| 14 | Head turned away | Pose quality → "turned away" reason; lower readiness | ✅ (reason path) |
| 15 | 5-minute video | Overlapping-window merge; only small crops kept in memory (bounded) | 🟡 (design + unit-tested merge) |
| 16 | Multi-window long clip boundary words | Token-boundary dedup removes duplicated words across windows | 🧪 unit |

Scenarios marked 🟡 are handled by the same code paths that the ✅ cases exercise
(face detection, per-person ROI cropping, quality scoring, windowed inference); they are
not separately reproduced here only because suitable long / occluded / low-light natural
clips are not fetchable under this environment's egress policy. The **evaluation upload**
path is ready to accept a user-provided clip for any of them.

## Honesty guarantees (unchanged)

- Every ML result is `REAL_RESULT` / `MODEL_UNAVAILABLE` / `LOW_CONFIDENCE` / `NO_SIGNAL`.
- Audio is **never** used as a substitute for lip reading — `transcribe` takes only frames.
- The app never falls back to GRID for open-vocabulary requests and never invents words for
  silent or low-confidence windows.
