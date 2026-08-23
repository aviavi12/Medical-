# Current Lip-Reading Model — Audit & Limitations (Phase 1)

Honest audit of the GRID/LipNet model that produced the earlier "LAY BLUE BY C
TWO AGAIN" proof-of-concept, and how it differs from the open-vocabulary product
goal.

## The two models in this repo

| | **GRID-LipNet** (benchmark) | **SyncVSR** (production, added) |
|---|---|---|
| Status | `BENCHMARK_ONLY` | `PRODUCTION_CANDIDATE` |
| `LIP_READING_MODEL` | `lipnet` | `syncvsr` (default) |
| Open vocabulary | ❌ No | ✅ Yes |

This page audits **GRID-LipNet**. SyncVSR is documented in
`docs/open-vocabulary-model-comparison.md` and `docs/open-vocabulary-evaluation.md`.

## GRID-LipNet audit (the 11 questions)

1. **Model:** LipNet (Assael et al. 2016), PyTorch port `Fengdalu/LipNet-PyTorch` (MIT).
2. **Checkpoint:** `lipnet_overlap.pt` (also `lipnet_unseen.pt`), 3D-CNN + Bi-GRU + CTC.
3. **Trained on:** the **GRID** audiovisual corpus only.
4. **Vocabulary:** **closed, 51 words** — `{bin,lay,place,set}`, `{blue,green,red,white}`,
   `{at,by,in,with}`, letters `A–Z` (minus W), digits `zero–nine`, `{again,now,please,soon}`.
5. **Grammar constraints:** a **fixed 6-slot grammar** `command color preposition letter
   digit adverb`. Every GRID utterance has exactly this shape.
6. **Level:** sentence-level (fixed-length 6-word utterance), CTC over characters.
7. **Closed-vocabulary:** **Yes.** It can only ever emit GRID characters/words; it has never
   seen the vast majority of English words.
8. **Suitable for natural English:** **No.** It cannot transcribe out-of-vocabulary words or
   free-form sentences; on natural speech it degrades to nearest-GRID guesses.
9. **Published WER/CER:** GRID overlapped-speakers WER ~4.6% / CER ~1.9%; unseen-speakers
   WER ~13.3% / CER ~6.8% — but **only within GRID's grammar**. Our measured GRID WER is 0.017.
10. **Does the decoder constrain output?** The CTC greedy decoder itself is unconstrained over
    the 27-character set, but the model was trained **only** on GRID sentences, so it strongly
    biases toward GRID structure — effectively a closed language model baked into the weights.
11. **Does the code accidentally benefit from GRID structure?** The inference/decoder does **not**
    hard-code GRID grammar (no grammar mask, no template). The high GRID accuracy comes from the
    weights, not from leaking the grammar in code. Ground truth in the GRID tests is derived
    independently from the corpus filename convention, never fed to the model.

## Why GRID is not the product

- **Closed vocabulary + fixed grammar** ≠ the goal of transcribing *natural* English.
- It is retained strictly as a **pipeline-validation / regression / CI** model: it is small,
  fast, and its low, stable WER catches regressions in detection → tracking → alignment → mouth
  ROI → CTC decode → export. It is labelled `BENCHMARK_ONLY` in the model registry and is **not**
  the default; the UI shows which model produced any transcript.

## Target

**Open-vocabulary English visual speech recognition** — a real pretrained sentence model that
transcribes natural speech (any words), exposes uncertainty, and never hallucinates. That is the
SyncVSR production model added in this phase.
