from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from src.analyze_strategy_experiment import first_pass_resource, weighted_schedule
from src.dataset import load_config, load_dataset


def read_jsonl(paths: list[Path], run_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            rows.extend(
                row
                for line in handle
                if line.strip()
                for row in [json.loads(line)]
                if row.get("run_id") == run_id
            )
    return rows


def integer_allocation(probabilities: list[float], budget: int) -> tuple[int, ...]:
    shares = np.asarray(probabilities, dtype=float)
    shares /= shares.sum()
    raw = shares * budget
    result = np.floor(raw).astype(int)
    for idx in np.argsort(-(raw - result))[: budget - int(result.sum())]:
        result[idx] += 1
    return tuple(int(value) for value in result)


def replay(
    indexed: dict[tuple[str, str, str], dict[str, Any]],
    *,
    model: str,
    task_id: str,
    allocation: tuple[int, ...],
    strategies: list[str],
    matched_strategy: str,
    clock: str,
    stop_on_any_success: bool,
) -> tuple[float, bool]:
    attempt_index = [0] * len(strategies)
    resource = 0.0
    offset = sum(f"{model}|{task_id}".encode("utf-8")) % len(strategies)
    for strategy_idx in weighted_schedule(allocation, offset):
        strategy = strategies[strategy_idx]
        row = indexed[(model, task_id, strategy)]
        attempt = attempt_index[strategy_idx]
        attempt_index[strategy_idx] += 1
        if attempt >= len(row["attempt_statuses"]):
            continue
        resource += float(row[f"attempt_{clock}"][attempt])
        solved = row["attempt_statuses"][attempt] == "pass"
        if solved and (stop_on_any_success or strategy == matched_strategy):
            return max(resource, 1.0e-9), True
    return max(resource, 1.0e-9), False


def bootstrap_mean(values: np.ndarray, seed: int, draws: int = 2000) -> list[float]:
    rng = np.random.default_rng(seed)
    means = np.mean(rng.choice(values, size=(draws, len(values)), replace=True), axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate empirical closure of the four-term identity")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--baseline-model", default="1.5b")
    args = parser.parse_args()

    config = load_config(args.config)
    bundle = load_dataset(config)
    raw_dir = Path(config["paths"]["raw"])
    derived_dir = Path(config["paths"]["derived"])
    workers = read_jsonl(sorted(raw_dir.glob("strategy_*.jsonl")), args.run_id)
    routers = read_jsonl(sorted(raw_dir.glob("router_*.jsonl")), args.run_id)
    if not workers or not routers:
        raise FileNotFoundError("Both complete worker and router logs are required")

    strategies = list(config["strategies"])
    mode_strategy = {str(k): str(v) for k, v in config["mode_strategy_map"].items()}
    indexed = {
        (str(row["model_key"]), str(row["task_id"]), str(row["strategy"])): row
        for row in workers
    }
    mode_counts = Counter(bundle.modes.values())
    prior = [mode_counts[mode] / len(bundle.modes) for mode in mode_strategy]
    budget = int(config["allocation"]["retry_budget"])
    q0 = integer_allocation(prior, budget)

    rates: dict[str, float] = {}
    for model in config["models"]:
        samples = [
            seconds / tokens
            for row in workers
            if row["model_key"] == model
            for seconds, tokens in zip(
                row.get("attempt_generation_seconds", row["attempt_seconds"]),
                row["attempt_token_counts"],
            )
            if tokens > 0
        ]
        rates[model] = float(median(samples))

    attempts = int(config["sampling"]["attempts_per_task"])
    t0: dict[tuple[str, str], float] = {}
    for model in config["models"]:
        for mode, strategy in mode_strategy.items():
            values = [
                first_pass_resource(indexed[(model, task_id, strategy)], "token_counts", attempts)
                for task_id in bundle.problems
                if bundle.modes[task_id] == mode
            ]
            t0[(model, mode)] = float(np.exp(np.mean(np.log(np.maximum(values, 1.0e-9)))))

    phi: dict[str, float] = {}
    for model in config["models"]:
        phi[model] = float(
            sum(
                prior[idx] * math.log(t0[(args.baseline_model, mode)] / t0[(model, mode)])
                for idx, mode in enumerate(mode_strategy)
            )
        )

    router_summary_path = derived_dir / f"router_information_summary_{args.run_id}.json"
    router_summary = json.loads(router_summary_path.read_text(encoding="utf-8"))
    information = router_summary["by_model_and_context_examples"]
    by_key = {
        (str(row["model_key"]), int(row["context_examples"]), str(row["task_id"])): row
        for row in routers
    }

    results: dict[str, Any] = {}
    for model in config["models"]:
        results[model] = {}
        for context_text, info in sorted(information[model].items(), key=lambda item: int(item[0])):
            context = int(context_text)
            packed_values: list[float] = []
            any_values: list[float] = []
            packed_success = [0, 0]
            any_success = [0, 0]
            for task_id in sorted(bundle.problems):
                matched = mode_strategy[bundle.modes[task_id]]
                router_row = by_key[(model, context, task_id)]
                qz = tuple(int(router_row["allocation"][strategy]) for strategy in strategies)
                for stop_any, values, success in (
                    (False, packed_values, packed_success),
                    (True, any_values, any_success),
                ):
                    baseline_t, baseline_ok = replay(
                        indexed,
                        model=args.baseline_model,
                        task_id=task_id,
                        allocation=q0,
                        strategies=strategies,
                        matched_strategy=matched,
                        clock="seconds",
                        stop_on_any_success=stop_any,
                    )
                    target_t, target_ok = replay(
                        indexed,
                        model=model,
                        task_id=task_id,
                        allocation=qz,
                        strategies=strategies,
                        matched_strategy=matched,
                        clock="seconds",
                        stop_on_any_success=stop_any,
                    )
                    values.append(math.log(baseline_t) - math.log(target_t))
                    success[0] += int(baseline_ok)
                    success[1] += int(target_ok)

            packed = np.asarray(packed_values)
            any_stop = np.asarray(any_values)
            cost = math.log(rates[args.baseline_model] / rates[model])
            predicted = cost + phi[model] + float(info["G_entropy"]) - float(info["epsilon_kl"])
            results[model][context_text] = {
                "n_tasks": len(packed),
                "q0_retry_allocation": dict(zip(strategies, q0, strict=True)),
                "per_step_cost": cost,
                "competence": phi[model],
                "information": float(info["G_entropy"]),
                "routing_mismatch": float(info["epsilon_kl"]),
                "predicted_log_speedup": predicted,
                "packed_observed_log_speedup": float(np.mean(packed)),
                "packed_observed_95ci": bootstrap_mean(packed, 20260711 + context),
                "packed_closure_residual": float(np.mean(packed) - predicted),
                "packed_baseline_success_rate": packed_success[0] / len(packed),
                "packed_routed_success_rate": packed_success[1] / len(packed),
                "operational_any_success_log_speedup": float(np.mean(any_stop)),
                "operational_any_success_95ci": bootstrap_mean(any_stop, 20260721 + context),
                "operational_baseline_success_rate": any_success[0] / len(any_stop),
                "operational_routed_success_rate": any_success[1] / len(any_stop),
            }

    output = {
        "schema_version": 1,
        "run_id": args.run_id,
        "baseline_model": args.baseline_model,
        "clock": "seconds",
        "finite_horizon_attempts": attempts,
        "right_censoring_note": "Unsolved cells are evaluated at their observed finite-horizon resource.",
        "kappa_seconds_per_token": rates,
        "focused_t0_tokens": {f"{model}|{mode}": value for (model, mode), value in t0.items()},
        "results": results,
    }
    output_path = derived_dir / f"four_term_closure_{args.run_id}.json"
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
