"""SentencePiece tokenizer for the open-vocabulary VSR model.

Slim copy of SyncVSR's TextTransform (MIT) — only the pieces needed for
inference decoding, without the torchaudio dependency. unigram5000 subword
vocabulary → open vocabulary.
"""

from __future__ import annotations

import os

VENDOR = os.path.dirname(os.path.abspath(__file__)) + "/vendor"
SPM_MODEL = os.path.join(VENDOR, "spm", "unigram", "unigram5000.model")
SPM_UNITS = os.path.join(VENDOR, "spm", "unigram", "unigram5000_units.txt")


class TextTransform:
    def __init__(self, sp_model_path: str = SPM_MODEL, dict_path: str = SPM_UNITS) -> None:
        import sentencepiece

        self.spm = sentencepiece.SentencePieceProcessor(model_file=sp_model_path)
        units = open(dict_path, encoding="utf8").read().splitlines()
        self.hashmap = {u.split()[0]: u.split()[-1] for u in units}
        # index 0 = CTC blank; last = <eos>
        self.token_list = ["<blank>"] + list(self.hashmap.keys()) + ["<eos>"]

    def post_process(self, token_ids) -> str:
        ids = [int(i) for i in token_ids if int(i) != -1]
        text = "".join(self.token_list[i] for i in ids).replace("<space>", " ")
        return text.replace("▁", " ").strip()
