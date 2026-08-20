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
    return " ".join(text.strip().lower().split())


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
