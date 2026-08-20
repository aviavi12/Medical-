"""python -m training.prepare_dataset --config ... (§29, §73)

Prepares a dataset: validation → face detection → alignment → mouth extraction →
temporal sequences → train/val/test splits. Refuses to auto-download
license-gated datasets (§72).
"""

from __future__ import annotations

from pathlib import Path

from training._cli import base_parser, load_config


def main() -> None:
    args = base_parser("Prepare a lip-reading dataset").parse_args()
    cfg = load_config(args.config)
    ds = cfg.get("dataset", {})
    root = Path(ds.get("root", ""))
    print(f"Dataset: {ds.get('name')}  root={root}  license={ds.get('license')}")
    if not root.exists():
        raise SystemExit(
            f"Dataset root {root} does not exist. Datasets must be obtained manually under "
            "their own licenses (§72). Place the data there and re-run."
        )
    print("Would run: validate → face detect → align → mouth ROI → sequences → splits.")
    print("Install the ML runtimes (requirements-ml.txt) to execute preparation for real.")


if __name__ == "__main__":
    main()
