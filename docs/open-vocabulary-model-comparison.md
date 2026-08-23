# Open-Vocabulary VSR — Research, Comparison & Selection (Phases 2-3)

Investigation of real pretrained open-vocabulary English visual speech recognition
models, constrained by this environment's **egress policy** (which model weights
are actually reachable), and the selected model.

## Reachability findings (the deciding constraint)

Model weights were probed directly. Blocked = HTTP 000/403 through the egress proxy:

| Host | Used by | Reachable? |
|------|---------|-----------|
| huggingface.co | AV-HuBERT ports, auto_avsr LM, chaplin | ❌ blocked |
| dl.fbaipublicfiles.com | **AV-HuBERT** weights | ❌ blocked |
| drive.google.com | **auto_avsr** weights | ❌ blocked |
| robots.ox.ac.uk / thor.robots.ox.ac.uk | Oxford VGG VSR, LRW | ❌ blocked |
| www.doc.ic.ac.uk | auto_avsr trackers | ❌ blocked |
| modelscope / hf-mirror | mirrors | ❌ blocked |
| **github.com / release-assets.githubusercontent.com** | **SyncVSR** | ✅ reachable |
| pypi.org / files.pythonhosted.org | pip packages | ✅ reachable |

**Consequence:** AV-HuBERT, auto_avsr, and Oxford VSR checkpoints are *unobtainable
here*, independent of their quality. SyncVSR hosts an open-vocab checkpoint on a
GitHub release → reachable → runnable.

## Comparison

| Field | **SyncVSR (selected)** | AV-HuBERT | auto_avsr | Oxford TM-seq2seq | GRID-LipNet (benchmark) |
|-------|------------------------|-----------|-----------|-------------------|-------------------------|
| Dataset | VoxCeleb2+LRS2+LRS3 | LRS3(+Vox) | LRS2/LRS3/Vox | LRS2/LRS3 | GRID |
| Vocabulary | **open** (unigram5000 subword) | open | open | open | closed (51 words) |
| Open/closed | **open** | open | open | open | closed |
| Architecture | Conv3D+ResNet → Conformer enc → Transformer/CTC dec | AV-HuBERT transformer + seq2seq | Conv3D+ResNet → Conformer + CTC/attn | CNN + Transformer seq2seq | 3D-CNN + Bi-GRU + CTC |
| Pretrained ckpt | **`Vox+LRS2+LRS3.ckpt` (1.14 GB)** | `self_large_vox_433h` | `vsr_trlrs3vox2_base` | vgg models | `lipnet_overlap.pt` |
| Checkpoint host | **GitHub release (reachable)** | fbaipublicfiles (blocked) | Google Drive (blocked) | ox.ac.uk (blocked) | GitHub (reachable) |
| Input | 96×96 grayscale **lower-face** crop | 96×96 mouth ROI | 96×96 mouth ROI | mouth ROI | 64×128 mouth ROI |
| FPS | 25 | 25 | 25 | 25 | 25 |
| Decoder | CTC(0.1)+attention beam search | seq2seq / CTC | CTC/attention | seq2seq | CTC greedy |
| License | **MIT** (+ESPnet Apache-2.0) | CC-BY-NC (non-commercial) | per-repo | research | MIT |
| Published WER | LRS3 ~ mid-20s% (video-only, w/ sync) | ~26% (base) / ~1–2% (huge) | ~20–36% | ~40–50% | 4.6% (GRID only) |
| GPU | optional | recommended | recommended | recommended | optional |
| CPU feasible | **yes (~1–2 s / short utterance)** | slow | slow | slow | yes |
| Memory | ~1.2 GB weights + modest runtime | large | large | large | small |
| Complexity | medium (vendored ESPnet, self-contained inference) | high (fairseq) | high (ESPnet) | high | low |
| Pros | reachable MIT weights, open-vocab, CPU-runnable, self-contained | strong accuracy | strong accuracy | — | tiny, fast |
| Cons | needs 1.14 GB download; accuracy below huge AV-HuBERT | weights blocked here, non-commercial | weights blocked here | weights blocked here | closed vocab |
| **Recommendation** | ✅ **ship as production open-vocab** | seam only (blocked) | seam (blocked) | no | benchmark only |

## Decision

**SyncVSR (`Vox+LRS2+LRS3`, MIT, Interspeech 2024, KAIST-AILab)** is selected as the
production open-vocabulary model. It is the **only** real open-vocab English VSR whose
pretrained weights are reachable in this environment (GitHub release), it is genuinely
visual-only and sentence-level with a subword (open) vocabulary, it runs on CPU in ~1–2 s
per short utterance, and its inference stack (vendored ESPnet subset) is self-contained (no
fairseq). AV-HuBERT/auto_avsr remain wired as seams and will drop in behind the same
`OpenVocabularyLipReadingModel` interface once their (currently blocked) weights are provided.

Verified: the checkpoint loads 100% (missing=0), and the full pipeline produces free-form
English from audio-removed video (see `docs/open-vocabulary-evaluation.md`).
