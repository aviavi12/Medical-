# LipSight — Evaluation (Experimental MVP Measurement)

> This is an **early MVP benchmark**, not a clinical, medical-grade, or production-accuracy
> claim. Numbers here are measurements under **clearly defined conditions**, produced by the real
> pipeline (no audio, no fabricated data). Reproduce them with the in-app **Developer evaluation
> panel** or `scripts/evaluate_open_vocabulary.py`.

## What is measured

| Field | Meaning |
|-------|---------|
| **WER** | Word Error Rate = edit distance (substitutions+deletions+insertions) ÷ reference words, after normalization. Lower is better. |
| **CER** | Character Error Rate, same idea at character level. |
| **Sentence accuracy** | Fraction of samples whose normalized prediction exactly equals the normalized reference (per-sample it is 0 or 1). |
| **Model confidence** | `exp(mean per-token decoder log-score)` in [0,1] — the model's own certainty in the decoded sequence. **Not** the fraction of words that are correct. |
| **Visual quality** | Aggregate of sharpness (Laplacian variance), brightness, mouth visibility and pose from the analyzed frames. |

### Normalization (applied identically to prediction AND reference)

- Lowercased.
- Surface punctuation removed: `. , ! ? ; : " ' \` ( ) [ ] { }`.
- Whitespace collapsed.
- **Not** normalized: contractions (`don't` ≠ `do not`), numbers-vs-words (`9` ≠ `nine`), spelling.

No transcript is altered to improve the score; both strings get the same treatment.

## Current measured result (GRID-domain sanity clip, CPU)

| LipSight Evaluation | |
|---|---|
| Clip | GRID `lrwp9a` (single frontal speaker, no audio, upscaled to 720p) |
| Reference | `lay red with p nine again` |
| Prediction | `LAY RED WITH PE NINE AGAIN` |
| Model | `syncvsr-vox-lrs2-lrs3` (open vocabulary, visual-only) |
| Samples | 1 |
| WER | **0.167** (1 substitution: `PE`↔`P`) |
| CER | **0.04** |
| Sentence accuracy | **0** (not an exact match) |
| Model confidence | 0.43 (likelihood proxy) |
| Compute | CPU |
| Analyze time | ~8 s for a 3 s clip (incl. model load from warm cache) |

**Interpretation.** This is a *constrained GRID-grammar* clip, not natural connected English. It
demonstrates the visual-only pipeline decodes real free-form tokens correctly end to end, but it is
**not** evidence of natural-English accuracy.

## The open question (highest-value next experiment)

LipSight's production model (SyncVSR) is trained for natural connected English, but its
**natural-English WER has not been measured in this repository** — suitable natural-English test
clips were not fetchable in the build environment. The evaluation path is fully built and waiting:

1. Upload a legally usable natural-English clip of one person speaking to camera.
2. Analyze the person.
3. Open **Developer tools → Run evaluation**, paste the exact spoken words.
4. Record WER / CER / sentence accuracy + the conditions (resolution, face size, lighting, pose).

Report the number **honestly**, whatever it is. A credible MVP with an honest benchmark is worth
more than an impressive-looking fabricated one.
