"""CTC greedy decoding with per-word timestamps and confidence.

Timestamps are derived from the actual frame times of the visual sequence used
for inference (§18): each emitted character is anchored to the frame that emitted
it, and words inherit the span of their characters. Confidence is the mean
softmax posterior of the emitted (non-blank) path — a real model quantity (§19).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ml.lipreading.lipnet.model import GRID_LETTERS


@dataclass
class DecodedWord:
    word: str
    start: float
    end: float
    confidence: float


@dataclass
class DecodeResult:
    text: str
    confidence: float
    words: list[DecodedWord] = field(default_factory=list)


def _softmax(logits: np.ndarray) -> np.ndarray:
    m = logits.max(axis=-1, keepdims=True)
    e = np.exp(logits - m)
    return e / e.sum(axis=-1, keepdims=True)


def ctc_greedy_decode(
    logits, timestamps: list[float] | None = None, letters: list[str] | None = None
) -> DecodeResult:
    """Greedy CTC decode of (T, C) logits. Index 0 is the CTC blank."""
    letters = letters or GRID_LETTERS
    if hasattr(logits, "detach"):
        logits = logits.detach().cpu().numpy()
    logits = np.asarray(logits, dtype=np.float64)
    probs = _softmax(logits)
    path = probs.argmax(axis=-1)

    chars: list[str] = []
    char_frames: list[int] = []
    char_conf: list[float] = []
    prev = -1
    for t, n in enumerate(path):
        n = int(n)
        if n != prev and n >= 1:  # skip blank (0) and repeats
            ch = letters[n - 1]
            if not (chars and chars[-1] == " " and ch == " "):
                chars.append(ch)
                char_frames.append(t)
                char_conf.append(float(probs[t, n]))
        prev = n

    text = "".join(chars).strip()
    letter_confs = [c for ch, c in zip(chars, char_conf) if ch != " "]
    confidence = float(np.mean(letter_confs)) if letter_confs else 0.0

    words: list[DecodedWord] = []
    cur: list[str] = []
    cur_frames: list[int] = []
    cur_conf: list[float] = []

    def flush() -> None:
        if not cur:
            return
        f0, f1 = cur_frames[0], cur_frames[-1]
        if timestamps:
            t0 = timestamps[min(f0, len(timestamps) - 1)]
            t1 = timestamps[min(f1, len(timestamps) - 1)]
        else:
            t0, t1 = float(f0), float(f1)
        words.append(DecodedWord("".join(cur), round(t0, 3), round(t1, 3),
                                 round(float(np.mean(cur_conf)), 4)))

    for ch, fr, cf in zip(chars, char_frames, char_conf):
        if ch == " ":
            flush()
            cur, cur_frames, cur_conf = [], [], []
        else:
            cur.append(ch)
            cur_frames.append(fr)
            cur_conf.append(cf)
    flush()

    return DecodeResult(text=text, confidence=round(confidence, 4), words=words)
