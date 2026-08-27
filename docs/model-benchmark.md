# LipSight — Model Benchmarks

This file records **measured** results that drive default model selection (§68–§71). Until a
benchmark is run in a given environment, defaults follow the reasoned choices in
`model-selection.md` and the runner below produces the numbers to replace the "pending" rows.

Run benchmarks with:

```bash
python scripts/benchmark_pipeline.py --video path/to/clip.mp4 --report out/bench.json
```

## Person detector (A vs B) — §68
Metrics: recall, precision, inference speed, small-person recall, edge-of-frame recall.

| Config | Recall | Precision | FPS | Small | Edge | Notes |
|--------|--------|-----------|-----|-------|------|-------|
| YOLO11n @1280 | pending | pending | pending | pending | pending | |
| YOLO11s @1280 | pending | pending | pending | pending | pending | |

## Face detector (YOLO-face vs MediaPipe) — §69
Metrics: face recall, small-face recall, side-face, rotated-face, FPS, CPU, GPU.

| Detector | Recall | Small | Side | Rotated | FPS | Notes |
|----------|--------|-------|------|---------|-----|-------|
| MediaPipe | pending | pending | pending | pending | pending | Apache-2.0, has landmarks |
| YOLO-face | pending | pending | pending | pending | pending | license varies |

## Tracker (ByteTrack vs BoT-SORT) — §70
Metrics: ID stability, ID switches, missed tracks, speed.

| Tracker | ID stability | ID switches | Missed | FPS | Notes |
|---------|--------------|-------------|--------|-----|-------|
| ByteTrack | pending | pending | pending | pending | MIT |
| BoT-SORT | pending | pending | pending | pending | MIT |

## Lip-reading model — §71
Metrics: WER, CER, inference speed, sequence length. **Measured** on 10 labeled
GRID clips (filename-encoded ground truth), CPU-only, this build.

| Model | Split | WER | CER | Sentence acc | Speed (CPU) | Seq len | License | Notes |
|-------|-------|-----|-----|--------------|-------------|---------|---------|-------|
| **LipNet (GRID)** | overlap | **0.017** | **0.004** | **90%** | ~0.09s/clip | 75 @25fps | MIT | shipped default |
| LipNet (GRID) | unseen | 0.017 | 0.005 | 90% | ~0.08s/clip | 75 @25fps | MIT | unseen speakers |
| AV-HuBERT | — | n/a | n/a | n/a | n/a | — | CC-BY-NC | weights host blocked (403) here — see model-comparison |
| Auto-AVSR | — | n/a | n/a | n/a | n/a | — | per-repo | weights host blocked here |

Errors are single-letter visual confusions (E↔F, F↔O). Reproduce with:
`pytest tests/live -m live` or `python scripts/demo.py`.

## Pipeline latency — §67
Produced as JSON by `scripts/benchmark_pipeline.py` (FPS, per-stage latency, GPU memory).
