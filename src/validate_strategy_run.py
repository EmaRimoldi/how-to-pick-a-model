from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.dataset import load_config, load_dataset


def load_rows(raw_dir: Path, run_id: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(raw_dir.glob("strategy_*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    if run_id is None or row.get("run_id") == run_id:
                        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate completeness of a strategy run")
    parser.add_argument("--config", default="config/strategy_experiment.yaml")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    bundle = load_dataset(config)
    rows = load_rows(Path(config["paths"]["raw"]), args.run_id)
    expected_attempts = int(config["sampling"]["attempts_per_task"])
    expected = {
        (model, strategy, task_id)
        for model in config["models"]
        for strategy in config["strategies"]
        for task_id in bundle.problems
    }
    counts = Counter(
        (str(row["model_key"]), str(row["strategy"]), str(row["task_id"]))
        for row in rows
    )
    actual = set(counts)
    malformed = [
        f"{row['model_key']}|{row['strategy']}|{row['task_id']}"
        for row in rows
        if not (
            len(row["attempt_statuses"])
            == len(row["attempt_token_counts"])
            == len(row["attempt_seconds"])
            == len(row.get("attempt_generation_seconds", row["attempt_seconds"]))
            == len(row.get("attempt_verification_seconds", row["attempt_seconds"]))
            == len(row.get("attempt_overhead_seconds", row["attempt_seconds"]))
            == expected_attempts
        )
    ]
    report = {
        "run_id": args.run_id,
        "expected_cells": len(expected),
        "observed_rows": len(rows),
        "complete_unique_cells": len(actual & expected),
        "missing_cells": ["|".join(cell) for cell in sorted(expected - actual)],
        "unexpected_cells": ["|".join(cell) for cell in sorted(actual - expected)],
        "duplicate_cells": ["|".join(cell) for cell, count in sorted(counts.items()) if count > 1],
        "malformed_attempt_rows": malformed,
    }
    report["complete"] = not any(
        report[key]
        for key in (
            "missing_cells",
            "unexpected_cells",
            "duplicate_cells",
            "malformed_attempt_rows",
        )
    )
    suffix = f"_{args.run_id}" if args.run_id else ""
    output = Path(config["paths"]["derived"]) / f"validation{suffix}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {output}; complete={report['complete']}")
    if not report["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
