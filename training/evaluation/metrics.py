"""Lip-reading evaluation metrics (§31).

WER, CER, sentence accuracy via Levenshtein edit distance. Pure/standalone so
both the training pipeline and the API evaluation endpoint use the same code.
"""

from __future__ import annotations

from dataclasses import dataclass


def levenshtein(a: list, b: list) -> int:
    """Edit distance between two token sequences (words or characters)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def _normalize(text: str) -> str:
    # Lowercase, collapse whitespace, and strip surface punctuation so WER/CER
    # measure the words — not LM-added periods or ground-truth commas (standard
    # ASR/VSR scoring convention).
    import re

    cleaned = re.sub(r"[.,!?;:\"'`()\[\]{}]", " ", text.lower())
    return " ".join(cleaned.split())


def word_error_rate(prediction: str, reference: str) -> float:
    ref_words = _normalize(reference).split()
    pred_words = _normalize(prediction).split()
    if not ref_words:
        return 0.0 if not pred_words else 1.0
    return levenshtein(pred_words, ref_words) / len(ref_words)


def character_error_rate(prediction: str, reference: str) -> float:
    ref = _normalize(reference)
    pred = _normalize(prediction)
    if not ref:
        return 0.0 if not pred else 1.0
    return levenshtein(list(pred), list(ref)) / len(ref)


def sentence_accuracy(predictions: list[str], references: list[str]) -> float:
    if not references:
        return 0.0
    correct = sum(1 for p, r in zip(predictions, references) if _normalize(p) == _normalize(r))
    return correct / len(references)


def alignment_ops(prediction: str, reference: str) -> dict:
    """Word-level substitution/deletion/insertion/hit counts via edit-distance
    backtrace (Phase 10). Rates are per reference word."""
    ref = _normalize(reference).split()
    hyp = _normalize(prediction).split()
    n, m = len(ref), len(hyp)
    # DP cost table with operation backtrace.
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
    i, j = n, m
    sub = dele = ins = hit = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (0 if ref[i - 1] == hyp[j - 1] else 1):
            if ref[i - 1] == hyp[j - 1]:
                hit += 1
            else:
                sub += 1
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            dele += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    denom = max(1, n)
    return {
        "sub": sub, "del": dele, "ins": ins, "hits": hit, "ref_words": n, "hyp_words": m,
        "sub_rate": round(sub / denom, 4), "del_rate": round(dele / denom, 4),
        "ins_rate": round(ins / denom, 4),
    }


@dataclass
class EvaluationResult:
    wer: float
    cer: float
    sentence_accuracy: float
    n: int
    per_sample: list[dict]


def evaluate(predictions: list[str], references: list[str]) -> EvaluationResult:
    if len(predictions) != len(references):
        raise ValueError("predictions and references must have the same length")
    per_sample = []
    total_wer = 0.0
    total_cer = 0.0
    for p, r in zip(predictions, references):
        w = word_error_rate(p, r)
        c = character_error_rate(p, r)
        total_wer += w
        total_cer += c
        per_sample.append({"prediction": p, "reference": r, "wer": round(w, 4), "cer": round(c, 4)})
    n = len(references) or 1
    return EvaluationResult(
        wer=round(total_wer / n, 4),
        cer=round(total_cer / n, 4),
        sentence_accuracy=round(sentence_accuracy(predictions, references), 4),
        n=len(references),
        per_sample=per_sample,
    )
