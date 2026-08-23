# Natural-English open-vocabulary evaluation set

Drop-in evaluation for the open-vocabulary VSR model (Phase 6–11). Each test case
is a subdirectory containing:

```
evaluation/open_vocabulary/<case_name>/
├── video.mp4          # a person speaking natural English (720p+, face visible)
├── ground_truth.txt   # the exact spoken transcript (one line, or one line per utterance)
└── metadata.json      # optional: {"speaker","lighting","pose","notes", ...}
```

Run:

```bash
python scripts/evaluate_open_vocabulary.py                 # evaluates every case here
python scripts/evaluate_open_vocabulary.py --grid-reference # + GRID constrained-vocab reference
```

The runner (Phase 7) **removes the audio track** from each video before inference,
so the visual model provably has no audio access. It reports WER/CER, sentence
accuracy, and substitution/deletion/insertion rates, with per-case breakdowns,
and writes `docs/open-vocabulary-evaluation.md`.

## Providing videos (why this folder may be empty here)

Natural-English talking-face videos with ground-truth transcripts could **not** be
downloaded in the build environment: every candidate host (YouTube, Wikimedia
Commons, archive.org, LRS2/LRS3) is blocked by the egress policy, and LRS is
license-restricted for redistribution anyway. Add your own legally-usable clips
in the layout above and re-run — no code changes needed.

## Dataset leakage (Phase 9)

The production model (SyncVSR `Vox+LRS2+LRS3`) was trained on **VoxCeleb2 + LRS2 +
LRS3**. To keep evaluation honest, your test videos must **not** be drawn from
those datasets or contain speakers that appear in them. Record the provenance in
each case's `metadata.json` (`"source"`, `"speaker"`, `"in_training": false`).
The bundled GRID reference has **zero overlap** with the model's training data.
