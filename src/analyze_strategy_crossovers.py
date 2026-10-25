from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from src.dataset import load_config, load_dataset
from src.estimate_strategy_closure import read_jsonl, replay


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze retry and borrowed-allocation crossovers")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--context-examples", type=int, default=20)
    args = parser.parse_args()

    config = load_config(args.config)
    bundle = load_dataset(config)
    raw_dir = Path(config["paths"]["raw"])
    derived_dir = Path(config["paths"]["derived"])
    workers = read_jsonl(sorted(raw_dir.glob("strategy_*.jsonl")), args.run_id)
    routers = read_jsonl(sorted(raw_dir.glob("router_*.jsonl")), args.run_id)
    strategies = list(config["strategies"])
    models = list(config["models"])
    mode_strategy = {str(key): str(value) for key, value in config["mode_strategy_map"].items()}
    indexed = {
        (str(row["model_key"]), str(row["task_id"]), str(row["strategy"])): row
        for row in workers
    }
    router_index = {
        (str(row["model_key"]), str(row["task_id"])): row
        for row in routers
        if int(row["context_examples"]) == args.context_examples
    }

    borrowed: dict[str, dict[str, Any]] = defaultdict(dict)
    for target_model in models:
        for source_model in models:
            log_times: list[float] = []
            solved = 0
            for task_id in sorted(bundle.problems):
                source = router_index[(source_model, task_id)]
                allocation = tuple(int(source["allocation"][strategy]) for strategy in strategies)
                resource, success = replay(
                    indexed,
                    model=target_model,
                    task_id=task_id,
                    allocation=allocation,
                    strategies=strategies,
                    matched_strategy=mode_strategy[bundle.modes[task_id]],
                    clock="seconds",
                    stop_on_any_success=True,
                )
                log_times.append(math.log(resource))
                solved += int(success)
            borrowed[target_model][source_model] = {
                "mean_log_certified_time": float(np.mean(log_times)),
                "geometric_mean_certified_seconds": float(math.exp(np.mean(log_times))),
                "verified_success_rate": solved / len(log_times),
            }

    retry: dict[str, Any] = {}
    for model in models:
        retry[model] = {}
        for mode, matched_strategy in mode_strategy.items():
            retry[model][mode] = {}
            task_ids = [task_id for task_id in bundle.problems if bundle.modes[task_id] == mode]
            for strategy in strategies:
                points = []
                for depth in range(1, int(config["sampling"]["attempts_per_task"]) + 1):
                    resources = []
                    successes = 0
                    for task_id in task_ids:
                        row = indexed[(model, task_id, strategy)]
                        statuses = row["attempt_statuses"][:depth]
                        costs = np.asarray(row["attempt_seconds"][:depth], dtype=float)
                        first = next((idx for idx, status in enumerate(statuses) if status == "pass"), None)
                        if first is None:
                            resources.append(float(costs.sum()))
                        else:
                            resources.append(float(costs[: first + 1].sum()))
                            successes += 1
                    points.append(
                        {
                            "depth": depth,
                            "verified_success_rate": successes / len(task_ids),
                            "geometric_mean_certified_seconds": float(
                                np.exp(np.mean(np.log(np.maximum(resources, 1.0e-9))))
                            ),
                        }
                    )
                retry[model][mode][strategy] = points

    matched_model_winners: dict[str, Any] = {}
    for mode, strategy in mode_strategy.items():
        by_model = {}
        for model in models:
            final = retry[model][mode][strategy][-1]
            by_model[model] = final
        winner = min(models, key=lambda model: by_model[model]["geometric_mean_certified_seconds"])
        matched_model_winners[mode] = {"winner": winner, "by_model": by_model}

    output = {
        "schema_version": 1,
        "run_id": args.run_id,
        "context_examples": args.context_examples,
        "borrowed_allocation_matrix": dict(borrowed),
        "retry_curves": retry,
        "matched_strategy_model_winners_at_depth_20": matched_model_winners,
    }
    path = derived_dir / f"strategy_crossovers_{args.run_id}.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
