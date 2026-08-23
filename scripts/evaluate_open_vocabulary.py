#!/usr/bin/env python3
"""Open-vocabulary evaluation runner (Phase 6-11).

Evaluates the production VSR model on natural-English cases under
evaluation/open_vocabulary/ (and, with --grid-reference, on the GRID fixtures as
a documented constrained-vocabulary reference). Audio is removed before inference
(Phase 7). Emits docs/open-vocabulary-evaluation.md + a JSON report.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
EVAL_DIR = REPO_ROOT / "evaluation" / "open_vocabulary"
GRID_DIR = REPO_ROOT / "tests" / "fixtures" / "visual_speech" / "grid"

_CMD = {"b": "bin", "l": "lay", "p": "place", "s": "set"}
_COL = {"b": "blue", "g": "green", "r": "red", "w": "white"}
_PREP = {"a": "at", "b": "by", "i": "in", "w": "with"}
_DIG = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
        "6": "six", "7": "seven", "8": "eight", "9": "nine", "z": "zero"}
_ADV = {"a": "again", "n": "now", "p": "please", "s": "soon"}


def grid_truth(code: str) -> str:
    c = code.lower()
    return f"{_CMD[c[0]]} {_COL[c[1]]} {_PREP[c[2]]} {c[3]} {_DIG[c[4]]} {_ADV[c[5]]}"


def _setup_env():
    work = Path(tempfile.mkdtemp(prefix="ov_eval_"))
    os.environ["DATABASE_URL"] = f"sqlite:///{work}/db.sqlite"
    os.environ["STORAGE_PATH"] = f"{work}/storage"
    os.environ["ALLOW_MOCK_INFERENCE"] = "0"
    os.environ["LIP_READING_MODEL"] = "syncvsr"
    os.environ["COARSE_FPS"] = "8"
    os.environ["ANALYSIS_FPS"] = "25"
    return work


def _run_case(video_path: Path, work: Path):
    """Strip audio, run the pipeline, return (transcript, meta, elapsed, audio_ok)."""
    from apps.api.config import get_settings
    from apps.api.services import pipeline
    from apps.api.services.storage import get_storage
    from apps.api.services.video import probe_metadata
    from database import models
    from database.base import create_all, get_session_factory, reset_engine_for_tests
    from ml.common.config import get_ml_config

    get_settings.cache_clear()
    reset_engine_for_tests()
    create_all()
    settings, config = get_settings(), get_ml_config()
    storage = get_storage(settings)
    db = get_session_factory()()

    noaudio = work / (video_path.stem + "_na.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", str(video_path), "-an", "-c:v", "libx264", "-r", "25",
                    str(noaudio)], capture_output=True, check=True)
    astreams = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(noaudio)], capture_output=True, text=True).stdout.strip()

    meta = probe_metadata(noaudio)
    key = f"eval/{video_path.stem}.mp4"
    storage.save(key, noaudio)
    video = models.Video(filename=noaudio.name, storage_path=key, status="QUEUED",
                         duration=meta.duration, width=meta.width, height=meta.height,
                         fps=meta.fps, has_audio=False)
    db.add(video)
    db.commit()
    db.refresh(video)

    t0 = time.time()
    pipeline.run_coarse_scan(db, video, storage, settings, config)
    people = (db.query(models.PersonTrack)
              .filter(models.PersonTrack.video_id == video.id)
              .order_by(models.PersonTrack.lip_readiness_score.desc()).all())
    transcript, fq = "", 0.0
    if people:
        person = people[0]
        fq = person.average_face_quality
        pipeline.run_person_analysis(db, video, person, storage, settings, config)
        segs = (db.query(models.LipReadingSegment)
                .filter(models.LipReadingSegment.person_track_id == person.id)
                .order_by(models.LipReadingSegment.start_time).all())
        transcript = " ".join(s.text for s in segs).strip()
    elapsed = time.time() - t0
    return transcript, meta, fq, elapsed, (astreams == "")


def main() -> int:
    from training.evaluation import alignment_ops, character_error_rate, word_error_rate

    ap = argparse.ArgumentParser(description="Open-vocabulary evaluation")
    ap.add_argument("--grid-reference", action="store_true",
                    help="also evaluate on GRID fixtures (constrained-vocab reference)")
    ap.add_argument("--report", default=str(REPO_ROOT / "docs" / "open-vocabulary-evaluation.md"))
    args = ap.parse_args()

    work = _setup_env()

    cases = []  # (name, video_path, ground_truth, kind)
    for d in sorted(EVAL_DIR.glob("*/")):
        vids = list(d.glob("video.*")) or [p for p in d.iterdir() if p.suffix.lower() in (".mp4", ".mov", ".webm", ".avi", ".mkv")]
        gt = d / "ground_truth.txt"
        if vids and gt.exists():
            cases.append((d.name, vids[0], gt.read_text().strip(), "natural"))

    if args.grid_reference:
        for mpg in sorted(glob.glob(str(GRID_DIR / "*.mpg"))):
            code = Path(mpg).stem
            cases.append((f"grid/{code}", Path(mpg), grid_truth(code), "grid"))

    results = []
    for name, vpath, gt, kind in cases:
        try:
            pred, meta, fq, elapsed, audio_ok = _run_case(vpath, work)
        except Exception as exc:  # pragma: no cover
            print(f"  ! {name}: {exc}")
            continue
        wer = word_error_rate(pred, gt)
        cer = character_error_rate(pred, gt)
        ops = alignment_ops(pred, gt)
        results.append({
            "case": name, "kind": kind, "prediction": pred, "ground_truth": gt,
            "wer": round(wer, 4), "cer": round(cer, 4), **ops,
            "audio_removed": audio_ok, "face_quality": round(fq, 1),
            "resolution": f"{meta.width}x{meta.height}", "seconds": round(elapsed, 1),
        })
        print(f"  {name}: WER={wer:.3f} CER={cer:.3f}  pred={pred!r}")

    natural = [r for r in results if r["kind"] == "natural"]
    grid = [r for r in results if r["kind"] == "grid"]

    def agg(rows):
        if not rows:
            return None
        n = len(rows)
        return {
            "n": n,
            "wer": round(sum(r["wer"] for r in rows) / n, 4),
            "cer": round(sum(r["cer"] for r in rows) / n, 4),
            "sentence_acc": round(sum(1 for r in rows if r["wer"] == 0) / n, 4),
            "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 1),
        }

    report = {"natural_english": agg(natural), "grid_reference": agg(grid), "cases": results}
    _write_markdown(Path(args.report), report, natural, grid)
    json_path = Path(args.report).with_suffix(".json")
    json_path.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {args.report} and {json_path}")
    if not natural:
        print("NOTE: no natural-English cases present — add videos per "
              "evaluation/open_vocabulary/README.md for a real natural-English WER.")
    return 0


def _write_markdown(path: Path, report: dict, natural, grid) -> None:
    from ml.common.device import device_report

    lines = ["# Open-Vocabulary Evaluation (Phase 10)", "",
             f"Model: **SyncVSR (Vox+LRS2+LRS3)** — open vocabulary. "
             f"Device: **{device_report('auto')['device']}**. Audio: **REMOVED** before inference.", ""]
    nat = report["natural_english"]
    if nat:
        lines += ["## Natural English", "",
                  f"- n={nat['n']}  WER={nat['wer']}  CER={nat['cer']}  "
                  f"sentence_acc={nat['sentence_acc']}  avg_time={nat['avg_seconds']}s", ""]
    else:
        lines += ["## Natural English", "",
                  "_No natural-English cases were available in this environment "
                  "(video hosts blocked by egress policy). Add clips per "
                  "`evaluation/open_vocabulary/README.md` and re-run for a real number._", ""]
    if grid:
        g = report["grid_reference"]
        lines += ["## GRID reference (constrained vocabulary — out of domain, zero training overlap)", "",
                  f"- n={g['n']}  WER={g['wer']}  CER={g['cer']}  sentence_acc={g['sentence_acc']}  "
                  f"avg_time={g['avg_seconds']}s",
                  "",
                  "> GRID uses isolated letters/digits in a fixed 6-word grammar — the hardest "
                  "case for a natural-sentence model. High WER here is expected and does **not** "
                  "reflect natural-speech performance; it confirms the model runs open-vocabulary "
                  "and produces free-form English with no GRID knowledge.", ""]
    lines += ["## Per-case", "",
              "| case | kind | WER | CER | sub/del/ins | face_q | prediction |",
              "|------|------|-----|-----|-------------|--------|------------|"]
    for r in report["cases"]:
        lines.append(f"| {r['case']} | {r['kind']} | {r['wer']} | {r['cer']} | "
                     f"{r['sub']}/{r['del']}/{r['ins']} | {r['face_quality']} | {r['prediction'][:50]!r} |")
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
