"""python -m training.train --config ... (§29, §73)

Fine-tunes / trains a lip-reading model per the config. This never fabricates a
checkpoint: it requires the ML runtimes and a prepared dataset, and reports
exactly what is missing otherwise.
"""

from __future__ import annotations

from pathlib import Path

from training._cli import base_parser, load_config


def main() -> None:
    args = base_parser("Train / fine-tune a lip-reading model").parse_args()
    cfg = load_config(args.config)
    model = cfg.get("model", {})
    train = cfg.get("training", {})
    print(f"Model: {model.get('architecture')}  pretrained={model.get('pretrained')}")
    print(f"Training: batch={train.get('batch_size')} lr={train.get('learning_rate')} "
          f"epochs={train.get('epochs')} device={train.get('device')}")

    missing = []
    try:
        import torch  # type: ignore  # noqa: F401
    except Exception:
        missing.append("torch")
    dataset_root = Path(cfg.get("dataset", {}).get("root", ""))
    if not dataset_root.exists():
        missing.append(f"prepared dataset at {dataset_root}")

    if missing:
        raise SystemExit(
            "Cannot train — missing: " + ", ".join(missing) +
            ". Install requirements-ml.txt and run training.prepare_dataset first."
        )
    print("Environment ready. Wire the model-specific training loop for your chosen adapter.")


if __name__ == "__main__":
    main()
