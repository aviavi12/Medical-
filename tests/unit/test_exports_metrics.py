"""Unit tests: export formats + WER/CER evaluation metrics."""

from __future__ import annotations

import json

from apps.api.services.exports import Segment, build_analysis_report, to_csv, to_json, to_srt, to_txt
from training.evaluation import character_error_rate, evaluate, word_error_rate


def _segs():
    return [
        Segment(0.0, 2.4, "hello world", 0.9),
        Segment(2.4, 4.0, "[uncertain]", 0.3),
    ]


def test_srt_format_timestamps():
    out = to_srt(_segs())
    assert "00:00:00,000 --> 00:00:02,400" in out
    assert "1\n" in out
    assert "hello world" in out


def test_txt_and_csv():
    assert "hello world" in to_txt(_segs())
    csv = to_csv(_segs())
    assert csv.splitlines()[0] == "start_time,end_time,confidence,text"
    assert "hello world" in csv


def test_json_export_roundtrip():
    payload = {"a": 1, "segments": [s.__dict__ for s in _segs()]}
    parsed = json.loads(to_json(payload))
    assert parsed["a"] == 1
    assert len(parsed["segments"]) == 2


def test_report_includes_limitations_and_models():
    report = build_analysis_report(
        video={"id": "v"}, person={"id": "p"}, transcript={"segments": []},
        gaze=None, model_versions=[{"model_version": "mock-vsr:test"}],
    )
    assert report["report_type"] == "silentspeak_analysis"
    assert len(report["limitations"]) >= 4
    assert report["model_versions"][0]["model_version"] == "mock-vsr:test"


def test_wer_cer_perfect_and_imperfect():
    assert word_error_rate("hello world", "hello world") == 0.0
    assert character_error_rate("hello", "hello") == 0.0
    assert word_error_rate("hello there", "hello world") == 0.5  # 1 of 2 words wrong


def test_evaluate_aggregate():
    res = evaluate(["hello world", "good morning"], ["hello world", "good evening"])
    assert res.n == 2
    assert 0 <= res.wer <= 1
    assert res.sentence_accuracy == 0.5  # one exact match
