"""Export generation (§41, §82, §83).

Pure functions turning transcript/analysis data into SRT / TXT / JSON / report.
No I/O here — routes decide where bytes go — so these are trivially testable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class Segment:
    start_time: float
    end_time: float
    text: str
    confidence: float


def _fmt_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(segments: list[Segment]) -> str:
    """SRT subtitle format (§82)."""
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_fmt_timestamp(seg.start_time)} --> {_fmt_timestamp(seg.end_time)}")
        lines.append(seg.text or "")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def to_txt(segments: list[Segment]) -> str:
    return "\n".join(seg.text for seg in segments if seg.text).strip() + "\n"


def to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, default=str)


def to_csv(segments: list[Segment]) -> str:
    rows = ["start_time,end_time,confidence,text"]
    for seg in segments:
        text = (seg.text or "").replace('"', '""')
        rows.append(f'{seg.start_time:.3f},{seg.end_time:.3f},{seg.confidence:.3f},"{text}"')
    return "\n".join(rows) + "\n"


def build_analysis_report(
    *,
    video: dict[str, Any],
    person: dict[str, Any],
    transcript: dict[str, Any],
    gaze: dict[str, Any] | None,
    model_versions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Structured analysis report (§83) — includes limitations + reproducibility."""
    return {
        "report_type": "lipsight_analysis",
        "product": "LipSight",
        "disclaimer": (
            "AI-generated visual speech analysis. The transcript is reconstructed from visible "
            "mouth movement only (no audio) and may be inaccurate. It should not be treated as a "
            "definitive transcription or a medical diagnosis. 'Confidence' is a model-likelihood "
            "score, not a measure of word-level accuracy."
        ),
        "video": video,
        "selected_person": person,
        "transcript": transcript,
        "gaze": gaze,
        "model_versions": model_versions,
        "limitations": [
            "Lip reading is probabilistic; the same mouth movement can map to multiple words.",
            "Confidence is a model-likelihood proxy (exp of the mean per-token decoder score), "
            "not the fraction of words that are correct.",
            "Gaze is approximate; head direction is not identical to eye gaze.",
            "Accuracy depends heavily on face visibility, resolution, pose, and lighting.",
            "Synthetic speech is not the original audio and does not clone any real voice.",
            "The system infers nothing about a person's thoughts or intentions.",
        ],
        "processing": {
            "app": "LipSight",
        },
    }
