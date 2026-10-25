"""CLI for computing endpoint, routing, and mode-conditioned estimators."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from vao.analysis.aggregate_runs import grouped_records
from vao.estimators import aggregate_run


OUTPUT_COLUMNS = [
    "run_id",
    "profile_id",
    "model_id",
    "visibility_regime",
    "best_loss",
    "success",
    "mean_routing_regret",
    "mean_jsd",
    "mean_cost_wall",
    "mean_cost_tokens",
    "invalid_rate",
    "mean_gain_layout",
    "mean_gain_indexing",
    "mean_gain_topk",
    "mean_gain_caching",
    "mean_gain_summaries",
    "mean_gain_micro",
]


def compute(roots: list[Path], success_threshold: float = 1.0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, records in grouped_records(roots).items():
        row = aggregate_run(records, success_threshold=success_threshold)
        if row:
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--metrics", default="all")
    parser.add_argument("--success-threshold", type=float, default=1.0)
    args = parser.parse_args(argv)
    rows = compute([Path(item) for item in args.runs], success_threshold=args.success_threshold)
    out = Path(args.out)
    if out.suffix == ".json":
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=2, allow_nan=True), encoding="utf-8")
    else:
        write_csv(out, rows)
    print(json.dumps({"rows": len(rows), "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
