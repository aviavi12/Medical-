"""Shared helpers for the training CLIs (§73)."""

from __future__ import annotations

import argparse
from pathlib import Path


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Config not found: {path}")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(p.read_text())
    except Exception:
        raise SystemExit(
            "PyYAML is required to read training configs. `pip install pyyaml`."
        )


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", default="training/configs/lipreading.yaml")
    return parser
