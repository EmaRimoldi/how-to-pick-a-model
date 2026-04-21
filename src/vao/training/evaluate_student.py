"""Evaluate a saved routing-only student on routing supervision records."""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

from vao.training.train_routing_lora import evaluate_records, load_jsonl


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--records", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--predictions_out", required=False)
    args = parser.parse_args(argv)

    with Path(args.model_path).open("rb") as handle:
        payload = pickle.load(handle)
    records = load_jsonl(Path(args.records))
    summary = evaluate_records(payload["model"], records, payload.get("config", {}))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({key: value for key, value in summary.items() if key != "predictions"}, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    if args.predictions_out:
        pred_out = Path(args.predictions_out)
        pred_out.parent.mkdir(parents=True, exist_ok=True)
        pred_out.write_text(json.dumps(summary["predictions"], indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    print(json.dumps({"records": len(records), "out": str(out)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
