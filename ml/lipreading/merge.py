"""Intelligent overlapping-window merge for long-video VSR (§16).

Long videos are transcribed in overlapping windows so the model always has
temporal context at chunk boundaries. Overlap means the same words can be
decoded at the end of one window and the start of the next. We remove those
duplicated boundary words by matching the **token suffix** of one window against
the **token prefix** of the next — purely from the model's own outputs and the
window timestamps. No language model invents or reorders words (§16, §31).

Each window stays a separate segment (so timestamps, frame ranges, window index,
confidence and speaking-activity provenance are preserved, §19); only the
duplicated leading tokens of the later segment are trimmed.
"""

from __future__ import annotations

import re

from ml.common.types import LipReadingSegment

_MAX_OVERLAP_TOKENS = 8


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"\s+", text.strip()) if t]


def _norm(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tok.lower())


def _overlap_len(prev_tokens: list[str], cur_tokens: list[str], max_k: int) -> int:
    """Largest k where prev's last k tokens == cur's first k tokens (normalised)."""
    limit = min(max_k, len(prev_tokens), len(cur_tokens))
    for k in range(limit, 0, -1):
        a = [_norm(t) for t in prev_tokens[-k:]]
        b = [_norm(t) for t in cur_tokens[:k]]
        if a == b and all(a):
            return k
    return 0


def merge_overlapping_segments(segments: list[LipReadingSegment]) -> list[LipReadingSegment]:
    """Trim duplicated boundary tokens from consecutive overlapping windows.

    Segments are assumed ordered by start_time. Returns segments whose texts,
    read in order, no longer repeat the overlap words. A segment fully consumed
    by the overlap (nothing new) is dropped.
    """
    if len(segments) < 2:
        return segments

    out: list[LipReadingSegment] = [segments[0]]
    for cur in segments[1:]:
        prev = out[-1]
        prev_toks = _tokens(prev.text)
        cur_toks = _tokens(cur.text)
        if not prev_toks or not cur_toks:
            out.append(cur)
            continue
        k = _overlap_len(prev_toks, cur_toks, _MAX_OVERLAP_TOKENS)
        if k:
            trimmed = cur_toks[k:]
            if not trimmed:
                # This window added nothing new — fold its span into prev and drop.
                prev.end_time = max(prev.end_time, cur.end_time)
                if cur.frame_end is not None:
                    prev.frame_end = cur.frame_end
                continue
            new_text = " ".join(trimmed)
            cur.text = new_text
            cur.raw_text = new_text
            if cur.processed_text:
                cur.processed_text = new_text
        out.append(cur)
    return out


def joined_transcript(segments: list[LipReadingSegment]) -> str:
    """Full running transcript from already-merged segments (skips [uncertain])."""
    from ml.lipreading.postprocessing import UNCERTAIN

    parts = [s.text for s in segments if s.text and s.text != UNCERTAIN]
    return " ".join(parts).strip()
