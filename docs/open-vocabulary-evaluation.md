# Open-Vocabulary Evaluation (Phase 10)

Model: **SyncVSR (Vox+LRS2+LRS3)** — open vocabulary. Device: **cpu**. Audio: **REMOVED** before inference.

## Natural English

_No natural-English cases were available in this environment (video hosts blocked by egress policy). Add clips per `evaluation/open_vocabulary/README.md` and re-run for a real number._

## GRID reference (constrained vocabulary — out of domain, zero training overlap)

- n=10  WER=0.7833  CER=0.524  sentence_acc=0.0  avg_time=7.0s

> GRID uses isolated letters/digits in a fixed 6-word grammar — the hardest case for a natural-sentence model. High WER here is expected and does **not** reflect natural-speech performance; it confirms the model runs open-vocabulary and produces free-form English with no GRID knowledge.

## Per-case

| case | kind | WER | CER | sub/del/ins | face_q | prediction |
|------|------|-----|-----|-------------|--------|------------|
| grid/bbaf2n | grid | 0.8333 | 0.4762 | 3/2/0 | 62.7 | 'PIMPLE LEFT TOO NOW' |
| grid/brbk7n | grid | 0.6667 | 0.3636 | 4/0/0 | 63.7 | 'BEEN READ BY CASE EVER NOW' |
| grid/lbax4n | grid | 0.5 | 0.1818 | 3/0/0 | 60.2 | 'LAY BLUE A TEXT FOR NOW' |
| grid/lbbc2a | grid | 1.0 | 0.8261 | 1/5/0 | 63.3 | '[uncertain]' |
| grid/lrwp9a | grid | 0.1667 | 0.04 | 1/0/0 | 65.8 | 'LAY RED WITH PE NINE AGAIN' |
| grid/lwbsza | grid | 1.3333 | 0.84 | 5/0/3 | 61.7 | 'NOW WHY AM I THERE TO SEE THROUGH AGAIN' |
| grid/pwij3p | grid | 1.0 | 0.8276 | 1/5/0 | 63.6 | '[uncertain]' |
| grid/sbia1a | grid | 0.5 | 0.4348 | 1/2/0 | 63.2 | 'SET BLUE IN A1K' |
| grid/sbwe5n | grid | 0.8333 | 0.6667 | 5/0/0 | 60.6 | 'THE SAME BALL WITHIN 5 NOW' |
| grid/swiz3n | grid | 1.0 | 0.5833 | 5/0/1 | 61.0 | 'JET WET AND JET THREE YOU KNOW' |
