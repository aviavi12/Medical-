# LipSight — Model Selection

For every AI model we document: name, version, source, license, input requirements, output, GPU
& memory requirements, accuracy metrics, limitations, and installation procedure (§98). This
document records the **candidates and the decision framework**. Final defaults are chosen from
measured benchmarks recorded in [`model-benchmark.md`](./model-benchmark.md); until a benchmark
exists for a given slot, the adapter defaults to the documented first choice **and reports
`MODEL_UNAVAILABLE` if its weights/deps are not installed** rather than guessing.

## Environment note (this build)

The environment used to bootstrap this repo has **no GPU/CUDA, no pre-installed PyTorch,
MediaPipe, or Ultralytics**. Consequently the heavy adapters are wired as clean seams that
report `MODEL_UNAVAILABLE` with the exact missing dependency. FFmpeg **is** installed, so video
validation, metadata, and frame extraction are fully real. See `docs/limitations.md`.

---

## 1. Person detection — YOLO family

| Field | Value |
|-------|-------|
| Candidates | YOLOv8 / YOLO11 (Ultralytics), YOLOX |
| Default | `ultralytics` YOLO11n/s at configurable `IMG_SIZE` (default 1280 for facial detail) |
| Source | https://github.com/ultralytics/ultralytics |
| License | AGPL-3.0 (Ultralytics) — **review before any distribution**; alternatives (YOLOX, Apache-2.0) provided as an adapter option |
| Input | RGB frame, configurable inference size |
| Output | `bbox`, `confidence`, `class_id=person`, `frame_index` |
| GPU | Optional; runs on CPU (slow). CUDA/MPS accelerated |
| Install | `pip install ultralytics` + first-run weight download |
| Limitations | Small/edge faces need high `IMG_SIZE`; do not upscale tiny faces and pretend detail exists (§9) |

We detect **all** reasonably visible people, never only the largest/centre/highest-confidence one.

## 2. Face detection — YOLO-face vs MediaPipe

| Candidate | Source | License | Notes |
|-----------|--------|---------|-------|
| MediaPipe Face Detector / Face Landmarker | google/mediapipe | Apache-2.0 | Fast on CPU, robust frontal, gives landmarks too |
| YOLO-face (e.g. YOLOv8-face) | community | varies (often AGPL) | Better small/edge faces at high res in some tests |

**Decision rule (§11, §69):** benchmark both on frontal, rotated, edge-of-frame, small, occluded,
and varied-lighting faces plus FPS/CPU/GPU. Record in `model-benchmark.md`. Default is
`FACE_DETECTOR=mediapipe` pending measured results, chosen for permissive licensing and built-in
landmarks. Do not select a model merely because it is popular.

## 3. Tracking — ByteTrack vs BoT-SORT

| Candidate | Source | License |
|-----------|--------|---------|
| ByteTrack | ifzhang/ByteTrack | MIT |
| BoT-SORT | NirAharon/BoT-SORT | MIT |

We do **not** implement MOT from scratch. Benchmark ID stability, ID switches, missed tracks,
and speed on project test clips; select the better default (§70). Interim default
`TRACKER=bytetrack`. Same person keeps the same `person_id` across frames when tracking is possible;
handles temporary loss, occlusion, crossings, entering/leaving frame.

## 4. Facial landmarks — MediaPipe Face Landmarker

| Field | Value |
|-------|-------|
| Model | MediaPipe Face Landmarker (468/478 landmarks incl. iris) |
| License | Apache-2.0 |
| Output | mouth, lips, jaw, eyes, iris landmarks, face orientation |
| Install | `pip install mediapipe` + `.task` model download |
| Use | alignment, mouth ROI, eye/iris for gaze |

## 5. Lip reading — English visual speech recognition (central subsystem)

| Candidate | Source | License | Notes |
|-----------|--------|---------|-------|
| **AV-HuBERT** | facebookresearch/av_hubert | CC-BY-NC 4.0 (**non-commercial**) | Strong VSR; license restricts commercial use |
| Auto-AVSR / VSR transformers | mpc001/auto_avsr | check per-repo | Modern, competitive WER |
| VideoMAE-based VSR | community | Apache-2.0 base | Research option |
| LipNet-compatible | rizkiarm/LipNet & forks | varies | GRID-scale, sentence-constrained; useful baseline |

**Explicit non-choice:** **Wav2Lip is NOT a lip-reading model** — it is audio-driven lip
*synthesis*. It is excluded from the recognition slot (§23).

**Decision rule (§71):** benchmark WER/CER, inference speed, GPU memory, required sequence length,
and accuracy-by-face-quality. Do not choose a model merely because it is newest. Interim default
`LIP_READING_MODEL=avhubert`, **gated** so that without weights it reports `MODEL_UNAVAILABLE`
listing: model weights, PyTorch/CUDA, and (for AV-HuBERT) the non-commercial license acceptance.

Each lip-reading adapter must declare its input contract: `required_fps`, `sequence_length`,
`input_size`, `normalization`.

## 6. Language-model post-processing (§27)

An optional LM may fix punctuation/capitalisation/segmentation only. It must **not** invent
speech. Both `raw_visual_transcript` and `processed_transcript` are stored so the UI can compare.

## 7. Gaze / head pose / iris

Built from landmarks (§32–§35): head pose via solvePnP on landmark↔3D-model correspondences;
iris position relative to eye geometry from MediaPipe iris landmarks; direction classified into
LEFT/CENTER/RIGHT/UP/DOWN/UNKNOWN. When iris is unreliable → head pose; when both unreliable →
`UNKNOWN`. Gaze is always reported as "possible/estimated/approximate", never as certainty about
where someone was looking.

## 8. TTS — generic synthetic voice (§42, §43)

| Field | Value |
|-------|-------|
| Default (working) | **eSpeak NG** — local, GPL-3.0, generic English voice, fully offline (no weights). Robotic but real synthesized speech. |
| Neural upgrade | Piper (rhasspy/piper, MIT) — higher quality; its voice models are on HuggingFace, **blocked by this environment's egress policy**, so it is the documented upgrade rather than the default here. |
| Safety | **Never** clones a voice from an uploaded video by default. Any future authorized voice profile requires explicit user confirmation of permission (`VoicePermissionError` otherwise). All output labelled *"Synthetic audio generated from visual transcript."* |

## 9. Optional audio ASR (evaluation only, §45)

For research comparison when the video has audio (e.g. Whisper). The audio transcript is **never**
silently substituted for the visual transcript.

---

## Installation summary

| Slot | pip / asset | Runs without GPU? |
|------|-------------|-------------------|
| Person detect | `ultralytics` (+weights) | yes, slow |
| Face detect | `mediapipe` (+.task) | yes |
| Tracking | `pip install` tracker or bundled | yes |
| Landmarks | `mediapipe` (+.task) | yes |
| Lip reading | model repo + weights + torch | CPU possible, GPU strongly recommended |
| Gaze | opencv + landmarks | yes |
| TTS | `piper-tts` (+voice) | yes |

Any missing item ⇒ the corresponding adapter returns `MODEL_UNAVAILABLE` naming the exact gap.
