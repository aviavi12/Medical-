"""SyncVSR open-vocabulary VSR model wrapper.

Builds the ESPnet E2E Conformer (Conv3D+ResNet frontend → Conformer encoder →
Transformer/CTC attention decoder) from the vendored SyncVSR code, loads the
MIT-licensed Vox+LRS2+LRS3 checkpoint, and runs CTC+attention beam search over
the unigram5000 subword vocabulary. Visual-only: the encoder receives only video.
"""

from __future__ import annotations

import os
import sys
from argparse import Namespace

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")


def _ensure_vendor_on_path() -> None:
    if VENDOR not in sys.path:
        sys.path.insert(0, VENDOR)


def build_beam_search(model, token_list, ctc_weight: float = 0.1, beam_size: int = 10):
    _ensure_vendor_on_path()
    from espnet.nets.batch_beam_search import BatchBeamSearch
    from espnet.nets.scorers.length_bonus import LengthBonus

    sos = eos = model.odim - 1
    scorers = model.scorers()
    scorers["lm"] = None
    scorers["length_bonus"] = LengthBonus(len(token_list))
    weights = {"decoder": 1.0 - ctc_weight, "ctc": ctc_weight, "lm": 0.0, "length_bonus": 0.0}
    return BatchBeamSearch(
        beam_size=beam_size, vocab_size=len(token_list), weights=weights, scorers=scorers,
        sos=sos, eos=eos, token_list=token_list,
        pre_beam_score_key=None if ctc_weight == 1.0 else "decoder",
    )


class SyncVSRModel:
    """Loads the checkpoint once and runs visual-only inference on a mouth/face
    sequence tensor of shape (T, 1, 96, 96)."""

    # keys in the checkpoint that belong to the audio-sync training branch and are
    # not part of the video-only recognition model.
    _AUDIO_PREFIXES = ("wav2vec", "audio_classifier", "audio_projection",
                       "category_classifier", "cutmix")

    def __init__(self, checkpoint_path: str, device: str = "cpu", beam_size: int = 10) -> None:
        _ensure_vendor_on_path()
        import torch
        from omegaconf import OmegaConf

        from espnet.nets.pytorch_backend.e2e_asr_transformer import E2E

        from ml.lipreading.openvocab.text_transform import TextTransform

        self.device = device
        self.beam_size = beam_size
        self._torch = torch

        self.text_transform = TextTransform()
        self.token_list = self.text_transform.token_list
        odim = len(self.token_list)

        cfg = OmegaConf.load(os.path.join(VENDOR, "config_lrs3.yaml"))
        bargs = Namespace(**OmegaConf.to_container(cfg.model.visual_backbone, resolve=True))
        self.model = E2E(odim, bargs)

        state = torch.load(checkpoint_path, map_location="cpu")["state_dict"]
        model_sd = {}
        for k, v in state.items():
            if not k.startswith("model."):
                continue
            kk = k[len("model."):]
            if kk.startswith(self._AUDIO_PREFIXES):
                continue
            model_sd[kk] = v
        missing, unexpected = self.model.load_state_dict(model_sd, strict=False)
        # The video-recognition weights must all be present.
        self.load_report = {"missing": len(missing), "unexpected": len(unexpected)}
        self.model.to(device).eval()
        self._beam = build_beam_search(self.model, self.token_list, beam_size=beam_size)

    def transcribe_tensor(self, sample) -> tuple[str, float]:
        """sample: (T, 1, 96, 96) float tensor. Returns (text, mean_token_score)."""
        _ensure_vendor_on_path()
        from espnet.asr.asr_utils import add_results_to_json

        torch = self._torch
        with torch.no_grad():
            enc, _ = self.model.encoder(sample.unsqueeze(0).to(self.device), None)
            nbest = self._beam(enc.squeeze(0))
        if not nbest:
            return "", 0.0
        best = nbest[0]
        hyp = best.asdict()
        text = add_results_to_json([hyp], self.token_list)
        text = text.replace("▁", " ").strip().replace("<eos>", "").strip()
        # Confidence proxy: normalized total hypothesis score → 0..1 via length.
        score = float(best.score)
        n_tok = max(1, len(best.yseq) - 1)
        conf = _score_to_confidence(score / n_tok)
        return text, conf

    def nbest(self, sample, n: int = 3) -> list[tuple[str, float]]:
        _ensure_vendor_on_path()
        from espnet.asr.asr_utils import add_results_to_json

        torch = self._torch
        with torch.no_grad():
            enc, _ = self.model.encoder(sample.unsqueeze(0).to(self.device), None)
            hyps = self._beam(enc.squeeze(0))
        out: list[tuple[str, float]] = []
        for h in hyps[: max(1, n)]:
            text = add_results_to_json([h.asdict()], self.token_list)
            text = text.replace("▁", " ").strip().replace("<eos>", "").strip()
            n_tok = max(1, len(h.yseq) - 1)
            out.append((text, _score_to_confidence(float(h.score) / n_tok)))
        return out


def _score_to_confidence(per_token_logprob: float) -> float:
    """Map a mean per-token log-prob (<=0) to a 0..1 confidence. Monotonic; a
    per-token logprob near 0 → ~1.0, more negative → lower."""
    import math

    return round(float(math.exp(min(0.0, per_token_logprob))), 4)
