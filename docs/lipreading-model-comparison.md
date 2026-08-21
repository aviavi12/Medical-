# Lip-Reading Model Comparison (§30, §71)

Why the MVP ships **LipNet (GRID)** as the first real visual speech recognition
model, and what the alternatives require. AV-HuBERT was investigated first, per
the brief; it is impractical in this environment for the reasons below.

| Model | English | Input | Pretrained weights | License | Reported WER | CPU feasible | GPU need | Complexity |
|-------|---------|-------|--------------------|---------|--------------|--------------|----------|------------|
| **LipNet (GRID)** ✅ chosen | Yes (GRID grammar) | 128×64 mouth, 25fps, CTC | **MIT, on GitHub (reachable)** | MIT (code+weights) | 4.6% (overlap) / 13.3% (unseen) | **Yes (~0.1s/clip)** | Optional | Low |
| AV-HuBERT | Yes (LRS3, open vocab) | 96×96 mouth, fairseq stack | `dl.fbaipublicfiles.com` — **BLOCKED (403) here** | CC-BY-NC (non-commercial) | ~1–2% (LRS3, large) | Slow; heavy | Strongly recommended | High (fairseq + retinaface align) |
| Auto-AVSR / VSR-Conformer | Yes (LRS2/3, open vocab) | 88×88 mouth, ESPnet | HuggingFace / Google Drive — **BLOCKED here** | per-repo | ~1.6–2% | Slow | Recommended | High |
| VideoMAE-based VSR | research | full-face patches | HuggingFace — **BLOCKED here** | Apache base | varies | Slow | Yes | High |
| Wav2Lip | ❌ not VSR | — | — | — | — | — | — | — |

Notes:
- **Wav2Lip is excluded** — it is audio-driven lip *synthesis*, not recognition (§23).
- **Whisper is excluded** from the lip-reading path — it is audio ASR and must never
  substitute for visual inference (§31). It may be used only in the separate,
  clearly-labeled audio-vs-visual evaluation mode (§45).

## Decision

The dominant constraint is the session's **egress policy**, which blocks
HuggingFace, `dl.fbaipublicfiles.com` (AV-HuBERT's host), Google Drive, and
`download.pytorch.org`. That makes AV-HuBERT / Auto-AVSR / VideoMAE weights
**unobtainable here**, independent of their quality. LipNet's MIT weights are
committed to a public GitHub repo (reachable via `git clone`), it runs in ~0.1s on
CPU, and it is a genuine, published English VSR model with a clean CTC decode.

We therefore ship LipNet as the **real, runnable default**, wired behind the same
`LipReadingModel` interface. When AV-HuBERT/Auto-AVSR weights become reachable (a
different network policy, or a manual drop into `MODELS_DIR`), an adapter can be
added with **no change to callers** — the honesty envelope and pipeline are
model-agnostic.

## Honest scope

LipNet's checkpoints are trained on GRID's constrained 6-word command grammar. On
GRID-style English footage (clear frontal face, ~130px+, 25fps) it achieves the
measured WER 0.017 in `docs/live-ml-plan.md`. It is **not** an open-vocabulary
conversational lip reader; the product surfaces this via `MODEL_UNAVAILABLE`/`NO_SIGNAL`
states and the limitations page rather than hallucinating out-of-domain sentences.
Upgrading to open-vocabulary VSR is the documented next step once such weights are
reachable.
