# Test Video Procedure (§84)

Use **legally usable** English test footage only. **Do not commit copyrighted test videos** to
the repository (they are gitignored under `storage/`). The automated suite generates its own
synthetic fixtures with FFmpeg, so no external media is required for CI.

## Automated fixtures

`tests/conftest.py` synthesizes real videos with FFmpeg (`testsrc` at 720p, with/without an audio
track) plus a corrupted file, and runs the full pipeline with deterministic **mock** ML adapters.
Run:

```bash
make test
```

## Manual test matrix

Record or obtain short, permissively-licensed clips covering:

1. **One clear speaker** — frontal, well lit, 720p+.
2. **Two people** — both faces visible.
3. **Secondary speaker at edge** — a person near the frame border.
4. **Person entering frame** — appears partway through.
5. **Person leaving frame** — exits partway through.
6. **Moderate head rotation** — speaker turns their head.
7. **No audio** — silent video (primary use case).
8. **With audio** — for the optional audio-vs-visual comparison mode (§45).

For each clip, verify:
- all reasonably visible people are detected (including the edge/entering/leaving ones);
- person IDs stay stable across frames;
- face-quality and lip-readiness scores are shown;
- only qualifying people are selectable; others show the insufficient-quality message;
- the transcript is timestamped, shows confidence, and marks low-confidence as `[uncertain]`;
- the gaze timeline classifies obvious directions and reports possible gaze toward another person
  as *possible*, not certain;
- SRT/TXT/JSON/report exports download correctly;
- optional TTS produces generic synthetic audio labelled as synthetic.

## Failure cases (§87)

Also confirm graceful, explicit handling of: empty video, corrupted video, no faces, one tiny
face, many faces, unsupported codec, over-duration video, missing model, missing GPU / CPU-only.
