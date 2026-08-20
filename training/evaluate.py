"""python -m training.evaluate --config ... (§31, §73)

Evaluates predictions against references using the shared WER/CER metrics. Given
a JSONL file of {"prediction","reference"} rows, prints aggregate metrics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.evaluation import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate lip-reading predictions")
    parser.add_argument("--pairs", help="JSONL file with {prediction, reference} per line")
    parser.add_argument("--config", default="training/configs/lipreading.yaml")
    args = parser.parse_args()

    if not args.pairs:
        # Demonstrate the metric on a tiny inline example.
        preds = ["hello world", "good morning"]
        refs = ["hello world", "good evening"]
    else:
        rows = [json.loads(line) for line in Path(args.pairs).read_text().splitlines() if line.strip()]
        preds = [r["prediction"] for r in rows]
        refs = [r["reference"] for r in rows]

    result = evaluate(preds, refs)
    print(json.dumps({
        "n": result.n, "wer": result.wer, "cer": result.cer,
        "sentence_accuracy": result.sentence_accuracy,
    }, indent=2))


if __name__ == "__main__":
    main()
