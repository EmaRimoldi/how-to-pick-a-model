#!/usr/bin/env python3
"""Generate frozen randomized-allocation designs for physical SAI-3 runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Iterable


BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE))

from sai3 import read_jsonl, write_jsonl  # noqa: E402


PRIOR = (1.0 / 3.0,) * 3


def stable_seed(base_seed: int, key: str) -> int:
    digest = hashlib.blake2b(f"{base_seed}|{key}".encode(), digest_size=8).digest()
    return 1 + int.from_bytes(digest, "big") % (2**31 - 2)


def select_balanced_tasks(
    tasks: Iterable[dict[str, Any]], tasks_per_mode: int, offset_per_mode: int
) -> list[dict[str, Any]]:
    seen = {mode: 0 for mode in range(3)}
    selected_counts = {mode: 0 for mode in range(3)}
    selected: list[dict[str, Any]] = []
    for task in tasks:
        mode = int(task["mode"])
        mode_index = seen[mode]
        seen[mode] += 1
        if mode_index < offset_per_mode:
            continue
        if selected_counts[mode] < tasks_per_mode:
            selected.append(task)
            selected_counts[mode] += 1
    if any(count != tasks_per_mode for count in selected_counts.values()):
        raise ValueError(f"insufficient balanced tasks after offset {offset_per_mode}: {selected_counts}")
    return selected


def posterior(alpha: float, z: int) -> tuple[float, float, float]:
    other = (1.0 - alpha) / 2.0
    return tuple(alpha if mode == z else other for mode in range(3))  # type: ignore[return-value]


def allocation(alpha: float, z: int, name: str) -> tuple[float, float, float]:
    post = posterior(alpha, z)
    if name == "matched":
        return post
    if name == "half_prior":
        return tuple(0.5 * value + 0.5 / 3.0 for value in post)  # type: ignore[return-value]
    if name == "prior":
        return PRIOR
    if name == "half_anti":
        rotated = (post[2], post[0], post[1])
        return tuple(0.5 * value + 0.5 / 3.0 for value in rotated)  # type: ignore[return-value]
    raise ValueError(f"unknown allocation: {name}")


def channel_probability(alpha: float, mode: int, z: int) -> float:
    return alpha if mode == z else (1.0 - alpha) / 2.0


def information(alpha: float) -> float:
    return sum(
        PRIOR[mode] * channel_probability(alpha, mode, z) * math.log(channel_probability(alpha, mode, z) / PRIOR[z])
        for mode in range(3)
        for z in range(3)
    )


def mismatch(alpha: float, name: str) -> float:
    total = 0.0
    for z in range(3):
        post = posterior(alpha, z)
        q = allocation(alpha, z, name)
        total += PRIOR[z] * sum(p * math.log(p / share) for p, share in zip(post, q) if p > 0.0)
    return total


def inverse_share_rows(
    tasks: list[dict[str, Any]], q_values: list[float], repetitions: int, seed: int
) -> list[dict[str, Any]]:
    rows = []
    for task in tasks:
        mode = int(task["mode"])
        for q_true in q_values:
            q = [(1.0 - q_true) / 2.0] * 3
            q[mode] = q_true
            for repetition in range(repetitions):
                trajectory_id = f"inverse|{task['task_id']}|q={q_true:.8f}|r={repetition}"
                rows.append(
                    {
                        "schema_version": 1,
                        "design": "inverse_share",
                        "trajectory_id": trajectory_id,
                        "task_id": task["task_id"],
                        "task_stratum": task.get("task_stratum", task["normalization"]["kind"]),
                        "mode": mode,
                        "q": q,
                        "q_true": q_true,
                        "repetition": repetition,
                        "schedule_seed": stable_seed(seed, trajectory_id),
                    }
                )
    return rows


def four_term_rows(
    tasks: list[dict[str, Any]], alphas: list[float], allocations: list[str], repetitions: int, seed: int
) -> list[dict[str, Any]]:
    rows = []
    for task in tasks:
        mode = int(task["mode"])
        for repetition in range(repetitions):
            baseline_id = f"baseline|{task['task_id']}|r={repetition}"
            rows.append(
                {
                    "schema_version": 1,
                    "design": "four_term",
                    "condition": "baseline_prior",
                    "trajectory_id": baseline_id,
                    "task_id": task["task_id"],
                    "task_stratum": task.get("task_stratum", task["normalization"]["kind"]),
                    "mode": mode,
                    "q": list(PRIOR),
                    "q_true": PRIOR[mode],
                    "repetition": repetition,
                    "schedule_seed": stable_seed(seed, baseline_id),
                    "analysis_weight": 1.0,
                }
            )
        for alpha in alphas:
            for name in allocations:
                for z in range(3):
                    for repetition in range(repetitions):
                        trajectory_id = (
                            f"four|{task['task_id']}|a={alpha:.8f}|alloc={name}|z={z}|r={repetition}"
                        )
                        q = allocation(alpha, z, name)
                        rows.append(
                            {
                                "schema_version": 1,
                                "design": "four_term",
                                "condition": f"alpha={alpha:.8f}|allocation={name}",
                                "trajectory_id": trajectory_id,
                                "task_id": task["task_id"],
                                "task_stratum": task.get("task_stratum", task["normalization"]["kind"]),
                                "mode": mode,
                                "alpha": alpha,
                                "allocation": name,
                                "z": z,
                                "q": list(q),
                                "q_true": q[mode],
                                "repetition": repetition,
                                "schedule_seed": stable_seed(seed, trajectory_id),
                                "analysis_weight": channel_probability(alpha, mode, z),
                            }
                        )
    return rows


def parse_floats(value: str) -> list[float]:
    return [float(item) for item in value.split(",") if item]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--design", choices=("inverse_share", "four_term"), required=True)
    parser.add_argument("--tasks-per-mode", type=int, required=True)
    parser.add_argument("--task-offset-per-mode", type=int, default=0)
    parser.add_argument("--repetitions", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--q-values", default="0.10,0.20,0.3333333333,0.50,0.80,1.0")
    parser.add_argument("--alphas", default="0.60,0.80")
    parser.add_argument("--allocations", default="matched,prior,half_anti")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()

    tasks = select_balanced_tasks(read_jsonl(args.tasks), args.tasks_per_mode, args.task_offset_per_mode)
    if args.design == "inverse_share":
        q_values = parse_floats(args.q_values)
        if any(not 0.0 < value <= 1.0 for value in q_values):
            raise SystemExit("all q values must lie in (0, 1]")
        rows = inverse_share_rows(tasks, q_values, args.repetitions, args.seed)
        design_quantities: dict[str, Any] = {"q_values": q_values}
    else:
        alphas = parse_floats(args.alphas)
        allocation_names = [item for item in args.allocations.split(",") if item]
        rows = four_term_rows(tasks, alphas, allocation_names, args.repetitions, args.seed)
        design_quantities = {
            "alphas": alphas,
            "allocations": allocation_names,
            "terms": [
                {
                    "alpha": alpha,
                    "allocation": name,
                    "information_nats": information(alpha),
                    "mismatch_nats": mismatch(alpha, name),
                }
                for alpha in alphas
                for name in allocation_names
            ],
        }

    write_jsonl(args.output, rows)
    manifest = {
        "schema_version": 1,
        "design": args.design,
        "source_tasks": str(args.tasks),
        "source_tasks_sha256": hashlib.sha256(args.tasks.read_bytes()).hexdigest(),
        "design_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "tasks_per_mode": args.tasks_per_mode,
        "task_offset_per_mode": args.task_offset_per_mode,
        "repetitions": args.repetitions,
        "seed": args.seed,
        "trajectories": len(rows),
        **design_quantities,
    }
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
