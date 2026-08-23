# Vendored third-party code

This directory vendors, unmodified, code required to run the SyncVSR open-vocabulary
visual speech recognition model for inference:

- `espnet/` — ESPnet networks subset (Apache-2.0), as redistributed by SyncVSR.
- `utils.py`, `config_lrs3.yaml` — from KAIST-AILab/SyncVSR (MIT).
- `spm/unigram/` — SentencePiece unigram-5000 tokenizer (MIT, SyncVSR).

Sources:
- SyncVSR: https://github.com/KAIST-AILab/SyncVSR  (MIT, Interspeech 2024)
- ESPnet:  https://github.com/espnet/espnet          (Apache-2.0)

The model checkpoint (Vox+LRS2+LRS3.ckpt, ~1.14 GB, MIT) is NOT committed; it is
downloaded by `scripts/download_models.py` from the SyncVSR GitHub release.
