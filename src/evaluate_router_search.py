from __future__ import annotations

import argparse
import glob
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from src.analyze_strategy_router import fit_temperature, temperature_scale
from src.dataset import load_config, load_dataset
from src.estimate_strategy_closure import replay


MODE_ORDER = ("easy", "medium", "hard")


def allocations(total: int, width: int) -> list[tuple[int, ...]]:
    return [values for values in itertools.product(range(1, total), repeat=width) if sum(values) == total]


def positive_floor(values: list[int], budget: int) -> tuple[int, ...]:
    result = np.asarray(values, dtype=int)
    result = np.maximum(result, 1)
    while int(result.sum()) > budget:
        candidates = np.flatnonzero(result > 1)
        result[candidates[np.argmax(result[candidates])]] -= 1
    while int(result.sum()) < budget:
        result[int(np.argmax(values))] += 1
    return tuple(int(value) for value in result)


def posterior_floor(probabilities: np.ndarray, budget: int) -> tuple[int, ...]:
    residual = budget - len(probabilities)
    raw = probabilities * residual
    result = np.floor(raw).astype(int) + 1
    for idx in np.argsort(-(raw - np.floor(raw)))[: budget - int(result.sum())]:
        result[idx] += 1
    return tuple(int(value) for value in result)


def load_workers(raw_dir: Path, run_id: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for path in sorted(raw_dir.glob("strategy_*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("run_id") == run_id
    ]


def load_search(path: Path, phase: str) -> dict[tuple[str, int], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for file in sorted(path.glob(f"{phase}_gpt-*.jsonl")):
        for line in file.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            grouped[(str(row["router_model"]), int(row["context_examples"]))].append(row)
    return grouped


def metrics(
    values: list[float],
    baseline_times: list[float],
    routed_times: list[float],
    baseline_success: int,
    routed_success: int,
    seed: int,
) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    bootstrap = np.mean(rng.choice(array, size=(4000, len(array)), replace=True), axis=1)
    low, high = np.quantile(bootstrap, [0.025, 0.975])
    return {
        "n_tasks": len(array),
        "mean_log_speedup": float(array.mean()),
        "multiplicative_speedup": float(math.exp(array.mean())),
        "speedup_95ci": [float(math.exp(low)), float(math.exp(high))],
        "baseline_successes": baseline_success,
        "routed_successes": routed_success,
        "baseline_success_rate": baseline_success / len(array),
        "routed_success_rate": routed_success / len(array),
        "geometric_mean_baseline_seconds": float(
            np.exp(np.mean(np.log(np.maximum(baseline_times, 1.0e-9))))
        ),
        "geometric_mean_routed_seconds": float(
            np.exp(np.mean(np.log(np.maximum(routed_times, 1.0e-9))))
        ),
        "arithmetic_mean_baseline_seconds": float(np.mean(baseline_times)),
        "arithmetic_mean_routed_seconds": float(np.mean(routed_times)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a router and allocation head on validation traces")
    parser.add_argument("--config", required=True)
    parser.add_argument("--worker-run-id", required=True)
    parser.add_argument("--search-dir", required=True)
    parser.add_argument("--phase", choices=("validation", "test"), default="validation")
    args = parser.parse_args()

    config = load_config(args.config)
    bundle = load_dataset(config)
    raw_dir = Path(config["paths"]["raw"])
    search_dir = Path(args.search_dir)
    split = json.loads((search_dir / "split.json").read_text(encoding="utf-8"))
    workers = load_workers(raw_dir, args.worker_run_id)
    strategies = list(config["strategies"])
    models = list(config["models"])
    mode_strategy = {str(k): str(v) for k, v in config["mode_strategy_map"].items()}
    indexed = {
        (str(row["model_key"]), str(row["task_id"]), str(row["strategy"])): row
        for row in workers
    }
    required_tasks = set(split["train"]) | set(split[args.phase])
    missing = [
        (model, task_id, strategy)
        for model in models
        for task_id in required_tasks
        for strategy in strategies
        if (model, task_id, strategy) not in indexed
    ]
    if missing:
        raise RuntimeError(f"Worker run is incomplete for search split: {len(missing)} missing cells")

    budget = int(config["allocation"]["retry_budget"])
    candidates = allocations(budget, len(strategies))
    mode_index = {mode: idx for idx, mode in enumerate(MODE_ORDER)}
    prior_counts = Counter(bundle.modes.values())
    prior = np.asarray([prior_counts[mode] for mode in MODE_ORDER], dtype=float)
    prior /= prior.sum()
    q0 = posterior_floor(prior, budget)

    surfaces: dict[str, dict[str, np.ndarray]] = {}
    for model in models:
        success = np.zeros((len(MODE_ORDER), len(candidates)))
        log_time = np.zeros_like(success)
        for mode_idx, mode in enumerate(MODE_ORDER):
            task_ids = [task_id for task_id in split["train"] if bundle.modes[task_id] == mode]
            for alloc_idx, allocation in enumerate(candidates):
                resources = []
                solved = []
                for task_id in task_ids:
                    resource, ok = replay(
                        indexed,
                        model=model,
                        task_id=task_id,
                        allocation=allocation,
                        strategies=strategies,
                        matched_strategy=mode_strategy[mode],
                        clock="seconds",
                        stop_on_any_success=True,
                    )
                    resources.append(resource)
                    solved.append(ok)
                success[mode_idx, alloc_idx] = np.mean(solved)
                log_time[mode_idx, alloc_idx] = np.mean(np.log(np.maximum(resources, 1.0e-9)))
        surfaces[model] = {"success": success, "log_time": log_time}

    search = load_search(search_dir, args.phase)
    validation_search = load_search(search_dir, "validation")
    validation_selection = None
    if args.phase == "test":
        validation_selection = json.loads(
            (search_dir / "validation_selection.json").read_text(encoding="utf-8")
        )["selected"]
    results: dict[str, Any] = {model: {} for model in models}
    temperatures: dict[str, float] = {}
    for (router_model, context), rows in sorted(search.items()):
        posterior_rows = [row for row in rows if row["model_key"] == models[0]]
        posterior_by_task = {str(row["task_id"]): row for row in posterior_rows}
        task_ids = split[args.phase]
        probabilities = np.asarray(
            [[posterior_by_task[task_id]["posterior_raw"][mode] for mode in MODE_ORDER] for task_id in task_ids]
        )
        labels = np.asarray([mode_index[bundle.modes[task_id]] for task_id in task_ids], dtype=int)
        if args.phase == "validation":
            temperature = fit_temperature(probabilities, labels)
        else:
            calibration_rows = [
                row
                for row in validation_search[(router_model, context)]
                if row["model_key"] == models[0]
            ]
            calibration_p = np.asarray(
                [[row["posterior_raw"][mode] for mode in MODE_ORDER] for row in calibration_rows]
            )
            calibration_y = np.asarray(
                [mode_index[row["true_mode"]] for row in calibration_rows], dtype=int
            )
            temperature = fit_temperature(calibration_p, calibration_y)
        calibrated = temperature_scale(probabilities, temperature)
        temperatures[f"{router_model}|{context}"] = temperature
        calibrated_by_task = dict(zip(task_ids, calibrated, strict=True))
        rows_by_model_task = {
            (str(row["model_key"]), str(row["task_id"])): row for row in rows
        }

        for model in models:
            key = f"{router_model}|n={context}"
            if (
                validation_selection is not None
                and validation_selection[model]["router_configuration"] != key
            ):
                continue
            surface = surfaces[model]
            head_allocations: dict[str, dict[str, tuple[int, ...]]] = {
                "direct_floor": {},
                "posterior_floor": {},
                "performance_aware": {},
            }
            for task_id in task_ids:
                p = calibrated_by_task[task_id]
                direct = [rows_by_model_task[(model, task_id)]["allocation"][s] for s in strategies]
                head_allocations["direct_floor"][task_id] = positive_floor(direct, budget)
                head_allocations["posterior_floor"][task_id] = posterior_floor(p, budget)
                predicted_success = p @ surface["success"]
                best_success = float(np.max(predicted_success))
                eligible = np.flatnonzero(predicted_success >= best_success - 0.02)
                predicted_log_time = p @ surface["log_time"]
                selected = int(eligible[np.argmin(predicted_log_time[eligible])])
                head_allocations["performance_aware"][task_id] = candidates[selected]

            results[model][key] = {}
            for head, allocations_by_task in head_allocations.items():
                if (
                    validation_selection is not None
                    and validation_selection[model]["allocation_head"] != head
                ):
                    continue
                differences = []
                baseline_times = []
                routed_times = []
                baseline_success = routed_success = 0
                for task_id in task_ids:
                    mode = bundle.modes[task_id]
                    baseline_time, baseline_ok = replay(
                        indexed,
                        model=model,
                        task_id=task_id,
                        allocation=q0,
                        strategies=strategies,
                        matched_strategy=mode_strategy[mode],
                        clock="seconds",
                        stop_on_any_success=True,
                    )
                    routed_time, routed_ok = replay(
                        indexed,
                        model=model,
                        task_id=task_id,
                        allocation=allocations_by_task[task_id],
                        strategies=strategies,
                        matched_strategy=mode_strategy[mode],
                        clock="seconds",
                        stop_on_any_success=True,
                    )
                    differences.append(math.log(baseline_time) - math.log(routed_time))
                    baseline_times.append(baseline_time)
                    routed_times.append(routed_time)
                    baseline_success += int(baseline_ok)
                    routed_success += int(routed_ok)
                results[model][key][head] = metrics(
                    differences,
                    baseline_times,
                    routed_times,
                    baseline_success,
                    routed_success,
                    seed=20260712 + context,
                )

    selected: dict[str, Any] = {}
    if args.phase == "validation":
        for model in models:
            flat = [
                (config_key, head, value)
                for config_key, heads in results[model].items()
                for head, value in heads.items()
            ]
            eligible = [
                item
                for item in flat
                if item[2]["routed_successes"] >= item[2]["baseline_successes"] - 1
            ]
            winner = max(eligible, key=lambda item: item[2]["mean_log_speedup"])
            selected[model] = {
                "router_configuration": winner[0],
                "allocation_head": winner[1],
                "validation_metrics": winner[2],
            }

    output = {
        "schema_version": 1,
        "worker_run_id": args.worker_run_id,
        "phase": args.phase,
        "selection_rule": "maximize paired operational log-speedup subject to at most one fewer validation success",
        "baseline_allocation": dict(zip(strategies, q0, strict=True)),
        "temperatures": temperatures,
        "results": results,
        "selected": selected,
    }
    if args.phase == "test":
        output["validation_selected"] = validation_selection
    path = search_dir / (
        "validation_selection.json" if args.phase == "validation" else "test_evaluation.json"
    )
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {path}")
    print(json.dumps(selected if args.phase == "validation" else results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
