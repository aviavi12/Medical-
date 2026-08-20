# SilentSpeak Lab — Limitations & Scientific Caveats

This page is surfaced in the product UI (§101). It states plainly what the system can and cannot
do, so results are never over-trusted.

## Scientific limitations

- **Lip reading is probabilistic.** The same visible mouth movement can correspond to several
  different sounds or words. Visual speech recognition is an *inference*, never guaranteed truth.
- **Confidence is shown, always.** Low-confidence output is masked as `[uncertain]`, and where the
  model supports it, multiple candidate hypotheses are shown instead of a single confident guess.
  The system does not hallucinate complete sentences just because they are grammatically plausible.
- **Gaze is approximate.** Head direction is not the same as eye gaze. Gaze toward another person
  is reported as *possible / estimated*, never as certainty about intent or attention.
- **The system does not read minds.** It infers nothing about thoughts, intentions, emotions, or
  protected personal attributes.

## Quality dependencies

Accuracy depends heavily on visual quality. The MVP is **not** intended for:
extremely small faces, heavy blur, extreme occlusion, faces hidden most of the video, extreme
motion blur, very dark footage, faces only a few pixels wide, or arbitrary low-quality surveillance
footage. When visual evidence is insufficient, the system says so explicitly and does **not** run
the expensive model (quality gates, §65). Side-facing faces, occlusion, low resolution, and
multiple overlapping people all reduce accuracy and can create ambiguity.

## Honesty states

Every ML output is one of: `REAL_RESULT`, `MODEL_UNAVAILABLE` (with exact missing dependency),
`LOW_CONFIDENCE`, or `NO_SIGNAL`. The UI distinguishes all four; a real model result is never
confused with a placeholder, and there are **no hard-coded demo transcripts**.

## Synthetic audio

Optional text-to-speech uses a **generic** synthetic voice. It never clones the voice of a person
in an uploaded video. All generated audio is labelled *"Synthetic audio generated from visual
transcript."* and is a separate artifact — it never replaces the original recording.

## Current environment (this build)

- No GPU/CUDA, no PyTorch/MediaPipe/Ultralytics installed → detection, tracking, landmarks, lip
  reading, gaze, and TTS report `MODEL_UNAVAILABLE` with the missing dependency until installed.
- FFmpeg present → video validation, metadata, frame extraction are fully functional.
- PostgreSQL not present → app uses a local SQLite database (same schema).

See `docs/model-selection.md` for how to make each subsystem live.
