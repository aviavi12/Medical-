"""Post-processing for lip-reading output (§26, §27).

- Confidence masking: low-confidence text becomes ``[uncertain]`` rather than a
  confident sentence.
- n-best: alternative hypotheses are preserved when the model supplies them.
- Optional LM cleanup may fix punctuation/casing only — never invent words. Both
  raw and processed transcripts are kept so the UI can compare them.
"""

from __future__ import annotations

from ml.common.types import LipReadingSegment

UNCERTAIN = "[uncertain]"


def is_uncertain(confidence: float, threshold: float = 0.5) -> bool:
    return confidence < threshold


def mask_low_confidence(segment: LipReadingSegment, threshold: float = 0.5) -> LipReadingSegment:
    """Replace the displayed text with ``[uncertain]`` when below threshold.

    ``raw_text`` always keeps the original decoding for transparency.
    """
    if not segment.raw_text:
        segment.raw_text = segment.text
    if is_uncertain(segment.confidence, threshold):
        segment.text = UNCERTAIN
        segment.processed_text = segment.processed_text or UNCERTAIN
    else:
        segment.processed_text = segment.processed_text or segment.text
    return segment


def light_lm_cleanup(text: str) -> str:
    """Capitalise the first letter and ensure terminal punctuation. Does NOT add,
    remove, or reorder words."""
    if not text or text == UNCERTAIN:
        return text
    cleaned = text.strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
        if cleaned[-1] not in ".!?":
            cleaned += "."
    return cleaned


def apply_postprocessing(
    segments: list[LipReadingSegment], threshold: float = 0.5, lm_cleanup: bool = True
) -> list[LipReadingSegment]:
    out: list[LipReadingSegment] = []
    for seg in segments:
        seg = mask_low_confidence(seg, threshold)
        if lm_cleanup and seg.text != UNCERTAIN:
            seg.processed_text = light_lm_cleanup(seg.text)
        out.append(seg)
    return out
