#!/usr/bin/env python3
"""One-command real lip-reading demo (§22).

    python scripts/demo.py                 # uses a bundled labeled GRID clip
    python scripts/demo.py --video x.mp4   # uses your own video

Strips the audio track first (proving the transcript is visual-only, §13/§14),
then runs the real end-to-end pipeline and prints the transcript + WER.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GRID_DIR = REPO_ROOT / "tests" / "fixtures" / "visual_speech" / "grid"

_CMD = {"b": "bin", "l": "lay", "p": "place", "s": "set"}
_COL = {"b": "blue", "g": "green", "r": "red", "w": "white"}
_PREP = {"a": "at", "b": "by", "i": "in", "w": "with"}
_DIG = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
        "6": "six", "7": "seven", "8": "eight", "9": "nine", "z": "zero"}
_ADV = {"a": "again", "n": "now", "p": "please", "s": "soon"}


def grid_truth(code: str) -> str | None:
    c = code.lower()
    try:
        return f"{_CMD[c[0]]} {_COL[c[1]]} {_PREP[c[2]]} {c[3]} {_DIG[c[4]]} {_ADV[c[5]]}".upper()
    except (KeyError, IndexError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="SilentSpeak Lab real lip-reading demo")
    ap.add_argument("--video", default=None, help="your own video; default = a labeled GRID clip")
    ap.add_argument("--weights", default="overlap", choices=["overlap", "unseen"])
    args = ap.parse_args()

    ground_truth = None
    if args.video:
        src = Path(args.video)
    else:
        clips = sorted(GRID_DIR.glob("*.mpg"))
        if not clips:
            print("No demo clip found. Run: python scripts/download_models.py", file=sys.stderr)
            return 2
        src = clips[0]
        ground_truth = grid_truth(src.stem)

    if not src.exists():
        print(f"Video not found: {src}", file=sys.stderr)
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="ssl_demo_"))
    noaudio = workdir / "visual_only.mp4"
    print(f"Input: {src.name}")
    print("Stripping audio (visual-only proof)…")
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-an", "-c:v", "libx264", "-r", "25", str(noaudio)],
                   capture_output=True, check=True)

    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "run_real_lipreading.py"),
           "--video", str(noaudio), "--output", str(REPO_ROOT / "results" / "demo"),
           "--weights", args.weights]
    if ground_truth:
        cmd += ["--ground-truth", ground_truth]
    print("Running real pipeline…\n")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
