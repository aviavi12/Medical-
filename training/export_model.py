"""python -m training.export_model --config ... (§73)

Exports a trained checkpoint (e.g. to ONNX) for faster inference. Requires a real
checkpoint; refuses to produce a fake artifact.
"""

from __future__ import annotations

from pathlib import Path

from training._cli import base_parser, load_config


def main() -> None:
    parser = base_parser("Export a trained lip-reading model")
    parser.add_argument("--checkpoint", help="Path to a trained checkpoint")
    args = parser.parse_args()
    cfg = load_config(args.config)
    ckpt = Path(args.checkpoint) if args.checkpoint else Path(
        cfg.get("training", {}).get("checkpoint_dir", "")
    )
    if not ckpt.exists():
        raise SystemExit(
            f"No checkpoint at {ckpt}. Train a model first (training.train). "
            "Export never fabricates weights."
        )
    print(f"Would export {ckpt} → ONNX (install onnxruntime + torch to run for real).")


if __name__ == "__main__":
    main()
