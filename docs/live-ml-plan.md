# SilentSpeak Lab — Live ML Plan & Status

This document records the transition from architecture-with-seams to a **real,
runnable** visual speech recognition pipeline, and the exact models, sources,
licenses, and procedures behind it.

## 1. Current ML status (this build)

| Subsystem | Status | Backend | Notes |
|-----------|--------|---------|-------|
| Person detection | ✅ REAL | YOLOv8n (Ultralytics) | Best-effort context; does not gate the gallery |
| Face detection | ✅ REAL | MediaPipe Face Detection | Gates gallery — a trackable face is what lip reading needs |
| Tracking | ✅ REAL | IoU tracker (dependency-free) | Each tracked face = a selectable person; ByteTrack seam remains |
| Face quality | ✅ REAL | OpenCV (blur/brightness/contrast/sharpness) | Calibrated so ~130px frontal faces are "usable" |
| Landmarks (gaze) | ✅ REAL | MediaPipe Face Mesh (468 + iris) | Head pose + gaze |
| Face/mouth ROI (lip reading) | ✅ REAL | 96×96 lower-face (SyncVSR) / dlib-68 128×64 (LipNet) | Per-model preprocessing |
| **Open-vocab VSR (production)** | ✅ **REAL** | **SyncVSR Vox+LRS2+LRS3 (Conformer)** | Open vocabulary; runs on CPU ~1–2s/utterance; see docs/open-vocabulary-*.md |
| VSR (benchmark) | ✅ REAL | LipNet (GRID) | Closed-vocab regression model, WER 0.017 on GRID |
| Gaze estimation | ✅ REAL | Geometric (head pose + iris) | Approximate; multi-person "possible target" wired (§35) |
| TTS | ✅ REAL | eSpeak NG (generic voice) | Offline, no weights; Piper is the neural upgrade when reachable |

**Verified end to end:** a no-audio English video → face detection → tracking →
person selection → mouth ROI → 25fps temporal sequence → real LipNet → timestamped
English transcript, evaluated against ground truth. See `run_real_lipreading.py`
and the `tests/live` suite.

## 2. Hardware

- Environment: **CPU-only** (no CUDA/MPS). `DeviceManager` (`ml/common/device.py`)
  resolves `DEVICE=auto` → cuda → mps → cpu and never crashes without a GPU. The
  resolved device is shown in `/health` and the Settings page.
- LipNet inference: **~0.1s per 3-second clip on CPU**. The heavier CPU costs are
  MediaPipe/dlib per-frame detection; a full 3s GRID demo runs in ~10–30s on CPU.
- GPU: the same code path uses CUDA automatically when available (torch picks the
  device); no separate code path.

## 3. Selected models

### Visual speech recognition — LipNet (GRID)
- **Why:** AV-HuBERT (first choice) is impractical here — its weights are hosted on
  `dl.fbaipublicfiles.com`, which this environment's egress policy **blocks (403)**,
  and it needs fairseq + a heavy preprocessing stack. LipNet is a real, published
  English VSR model (Assael et al. 2016), CPU-friendly, with MIT weights reachable
  on GitHub. See `docs/lipreading-model-comparison.md`.
- **Model / weights:** Fengdalu/LipNet-PyTorch (MIT). Two checkpoints:
  `lipnet_overlap.pt` (overlapped-speaker split, WER 4.6%) and `lipnet_unseen.pt`
  (unseen-speaker split, WER 13.3%). Default: overlap.
- **Version:** `lipnet-grid:fengdalu-mit`.
- **Source:** https://github.com/Fengdalu/LipNet-PyTorch
- **License:** MIT (code + weights). GRID corpus: research use.
- **Input:** `(B, 3, T, 64, 128)`, BGR, `/255`; 25fps; mouth ROI aligned via dlib-68
  Procrustes to a canonical face, cropped 160×80 around the mouth, resized 128×64.
- **Output:** `(B, T, 28)` CTC logits over `[blank, space, A–Z]` → greedy decode →
  text + per-word timestamps + confidence.
- **Domain / limitation:** GRID's 6-word command grammar
  (`command color preposition letter digit adverb`). This is the "suitable English
  video" domain (§17). Out-of-domain conversational speech is **not** what this
  checkpoint transcribes — the app documents this rather than hallucinating.

### Landmarks for the mouth ROI — dlib 68-point
- **Model:** `shape_predictor_68_face_landmarks.dat` (dlib).
- **Why:** the LipNet crops were produced with a 68-point (FAN/dlib-family) aligner;
  a MediaPipe→dlib approximation shifted the crop and produced wrong (though valid)
  GRID sentences (documented §17 debugging). dlib-68 matches the training distribution.
- **License:** trained on iBUG 300-W → **research-only** (non-commercial). Documented.

### Person detection — YOLOv8n (Ultralytics)
- **Weights:** `models/yolov8n.pt` (downloaded directly from the reachable GitHub
  release asset; ultralytics' api.github.com auto-check is blocked, so weights are
  fetched by `download_models.py` and loaded from disk with autoinstall disabled).
- **License:** AGPL-3.0 — review before distribution.
- **Note:** yolov8n (not yolo11n) to match the pinned `ultralytics==8.2.103`.

### Face detection + gaze landmarks — MediaPipe
- **License:** Apache-2.0. Models bundled in the wheel / fetched from
  `storage.googleapis.com` (reachable).

## 4. Missing dependencies / blocked hosts

Egress policy for this session **allows** PyPI, GitHub (repos, raw, releases),
`storage.googleapis.com`; and **blocks (403)** `huggingface.co`,
`download.pytorch.org`, `drive.google.com`, `dl.fbaipublicfiles.com`, `zenodo.org`.
Consequences:
- AV-HuBERT / HuggingFace VSR weights: not obtainable here → not used.
- torch installed from PyPI (CUDA-enabled wheel; runs on CPU).
- TTS (Piper) not installed → `MODEL_UNAVAILABLE`.

## 5. Installation

```bash
make install          # core backend + CV
make install-ml       # torch, torchvision, ultralytics, mediapipe, dlib-bin, ...
make download-models  # fetch LipNet + dlib-68 + yolov8n + GRID fixtures into ./models
```

`requirements-ml.txt` pins the working set: `torch==2.2.2`, `torchvision==0.17.2`,
`ultralytics==8.2.103`, `mediapipe==0.10.14`, `dlib-bin`, `editdistance`.

## 6. Expected model input / output

See §3. The explicit preprocessing lives in
`ml/lipreading/lipnet/preprocess.py` (`VisualSpeechPreprocessor`) and decoding in
`ml/lipreading/lipnet/decode.py`.

## 7. Test procedure

```bash
make download-models
python scripts/demo.py                       # one-command real demo (audio stripped)
pytest tests/live -m live                     # real WER + no-audio acceptance
python scripts/run_real_lipreading.py --video my.mp4 --output results/
```

`tests/live/test_lipnet_grid.py` asserts aggregate WER < 0.12 on labeled GRID clips
and a WER-0 no-audio end-to-end run (audio stream proven absent with ffprobe).

## 8. Fallback behavior (the honesty contract)

There is **no hidden fallback** that turns missing evidence into plausible English
(§31). The only outcomes are:
- `REAL_RESULT` — a real model produced the transcript.
- `MODEL_UNAVAILABLE` — weights/deps missing; the exact gap is named.
- `NO_SIGNAL` — quality gates failed or too few mouth frames were found.
- `LOW_CONFIDENCE` — a real model ran but confidence is below threshold → `[uncertain]`.

Audio ASR / Whisper are **never** used as a substitute (there is no audio path in
lip-reading inference at all — `transcribe` takes only frames).

## 9. Measured results (CPU, this build)

| Split | WER | CER | Sentence acc | Speed |
|-------|-----|-----|--------------|-------|
| overlap | 0.017 | 0.004 | 90% (9/10) | ~0.09s/clip |
| unseen | 0.017 | 0.005 | 90% (9/10) | ~0.08s/clip |

Errors are single-letter visual confusions (E↔F, F↔O) — near-identical lip shapes.
