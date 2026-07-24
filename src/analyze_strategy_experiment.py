from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from src.dataset import load_config


def read_rows(raw_dir: Path, run_id: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(raw_dir.glob("strategy_*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if run_id is None or row.get("run_id") == run_id:
                    rows.append(row)
    if not rows:
        raise FileNotFoundError(f"No strategy logs in {raw_dir}")
    return rows


def first_pass_resource(row: dict[str, Any], clock: str, horizon: int) -> float:
    statuses = list(row["attempt_statuses"])[:horizon]
    costs = np.asarray(row[f"attempt_{clock}"], dtype=float)[:horizon]
    first = next((idx for idx, value in enumerate(statuses) if value == "pass"), None)
    if first is not None:
        return float(np.sum(costs[: first + 1]))
    return float(np.sum(costs))


def integer_allocations(total: int, width: int) -> list[tuple[int, ...]]:
    return [
        values
        for values in itertools.product(range(1, total + 1), repeat=width)
        if sum(values) == total
    ]


def weighted_schedule(allocation: tuple[int, ...], offset: int) -> list[int]:
    total = sum(allocation)
    used = [0] * len(allocation)
    schedule: list[int] = []
    for step in range(total):
        scores = [((step + 1) * allocation[idx] / total) - used[idx] for idx in range(len(allocation))]
        best = max(scores)
        candidates = [idx for idx, score in enumerate(scores) if abs(score - best) < 1.0e-12]
        chosen = candidates[offset % len(candidates)]
        schedule.append(chosen)
        used[chosen] += 1
    return schedule


def inverse_share_slope(
    rows: list[dict[str, Any]],
    *,
    strategy_order: list[str],
    mode_strategy_map: dict[str, str],
    budget: int,
    clock: str,
) -> dict[str, Any]:
    indexed = {
        (str(row["model_key"]), str(row["task_id"]), str(row["strategy"])): row
        for row in rows
    }
    allocations = integer_allocations(budget, len(strategy_order))
    x_values: list[float] = []
    y_values: list[float] = []
    groups: list[str] = []
    for row in rows:
        if row["strategy"] != mode_strategy_map[row["task_mode"]]:
            continue
        strategy_idx = strategy_order.index(str(row["strategy"]))
        group = f"{row['model_key']}|{row['task_id']}"
        offset = sum(group.encode("utf-8")) % len(strategy_order)
        for alloc in allocations:
            attempt_index = [0] * len(strategy_order)
            resource = 0.0
            for scheduled_idx in weighted_schedule(alloc, offset):
                strategy = strategy_order[scheduled_idx]
                source = indexed[(str(row["model_key"]), str(row["task_id"]), strategy)]
                idx = attempt_index[scheduled_idx]
                if idx >= len(source["attempt_statuses"]):
                    continue
                resource += float(source[f"attempt_{clock}"][idx])
                attempt_index[scheduled_idx] += 1
                if scheduled_idx == strategy_idx and source["attempt_statuses"][idx] == "pass":
                    break
            x_values.append(-math.log(alloc[strategy_idx] / budget))
            y_values.append(math.log(max(resource, 1.0e-9)))
            groups.append(group)

    x = np.asarray(x_values)
    y = np.asarray(y_values)
    centered_x = np.empty_like(x)
    centered_y = np.empty_like(y)
    for group in sorted(set(groups)):
        mask = np.asarray([value == group for value in groups])
        centered_x[mask] = x[mask] - np.mean(x[mask])
        centered_y[mask] = y[mask] - np.mean(y[mask])
    denominator = float(centered_x @ centered_x)
    slope = float(centered_x @ centered_y / denominator) if denominator > 0 else math.nan
    residual = centered_y - slope * centered_x
    return {
        "clock": clock,
        "slope": slope,
        "target_slope": 1.0,
        "rmse_log": float(np.sqrt(np.mean(residual**2))),
        "n_observations": len(x_values),
        "n_task_model_groups": len(set(groups)),
    }


def summarize(config: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    strategy_order = list(config["strategies"])
    mode_strategy_map = {str(k): str(v) for k, v in config["mode_strategy_map"].items()}
    attempts = int(config["sampling"]["attempts_per_task"])
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["model_key"]), str(row["task_mode"]), str(row["strategy"]))].append(row)

    cells: dict[str, Any] = {}
    for (model, mode, strategy), cell_rows in sorted(grouped.items()):
        token_values = np.asarray(
            [first_pass_resource(row, "token_counts", attempts) for row in cell_rows],
            dtype=float,
        )
        second_values = np.asarray(
            [first_pass_resource(row, "seconds", attempts) for row in cell_rows],
            dtype=float,
        )
        cells[f"{model}|{mode}|{strategy}"] = {
            "n_tasks": len(cell_rows),
            "success_rate": float(np.mean([row["solved"] for row in cell_rows])),
            "geometric_mean_tokens": float(np.exp(np.mean(np.log(np.maximum(token_values, 1.0e-9))))),
            "geometric_mean_seconds": float(np.exp(np.mean(np.log(np.maximum(second_values, 1.0e-9))))),
        }

    kappa: dict[str, float] = {}
    for model in sorted({str(row["model_key"]) for row in rows}):
        rates = [
            seconds / tokens
            for row in rows
            if row["model_key"] == model
            for seconds, tokens in zip(
                row.get("attempt_generation_seconds", row["attempt_seconds"]),
                row["attempt_token_counts"],
            )
            if tokens > 0
        ]
        kappa[model] = float(median(rates))

    focused_t0: dict[str, float] = {}
    for key, value in cells.items():
        model, mode, strategy = key.split("|")
        if strategy == mode_strategy_map[mode]:
            focused_t0[f"{model}|{mode}"] = float(value["geometric_mean_tokens"])

    models = sorted(kappa, key=lambda value: float(value.replace("b", "")))
    modes = list(mode_strategy_map)
    phi: dict[str, float] = {}
    if models:
        baseline = models[0]
        for model in models:
            if all(f"{baseline}|{mode}" in focused_t0 and f"{model}|{mode}" in focused_t0 for mode in modes):
                phi[f"{baseline}->{model}"] = float(
                    np.mean(
                        [
                            math.log(focused_t0[f"{baseline}|{mode}"] / focused_t0[f"{model}|{mode}"])
                            for mode in modes
                        ]
                    )
                )

    return {
        "schema_version": 1,
        "n_rows": len(rows),
        "models": models,
        "strategies": strategy_order,
        "mode_strategy_map": mode_strategy_map,
        "cells": cells,
        "kappa_seconds_per_token": kappa,
        "focused_t0_tokens": focused_t0,
        "phi": phi,
        "inverse_share_tokens": inverse_share_slope(
            rows,
            strategy_order=strategy_order,
            mode_strategy_map=mode_strategy_map,
            budget=int(config["allocation"]["retry_budget"]),
            clock="token_counts",
        ),
        "inverse_share_seconds": inverse_share_slope(
            rows,
            strategy_order=strategy_order,
            mode_strategy_map=mode_strategy_map,
            budget=int(config["allocation"]["retry_budget"]),
            clock="seconds",
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze mode-specialized strategy logs")
    parser.add_argument("--config", default="config/strategy_experiment.yaml")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    rows = read_rows(Path(config["paths"]["raw"]), args.run_id)
    output = summarize(config, rows)
    suffix = f"_{args.run_id}" if args.run_id else ""
    out_path = Path(config["paths"]["derived"]) / f"strategy_summary{suffix}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
