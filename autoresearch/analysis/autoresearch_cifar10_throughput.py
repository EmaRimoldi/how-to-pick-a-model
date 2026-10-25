"""Measure AutoResearch inner-loop training throughput across task modes.

This script runs the benchmark directly on mode-specific initial templates and
records how many *training* steps per second each mode achieves on CPU. The
result is used to calibrate the feasible outer-loop horizon ``H`` in the paper.
"""

from __future__ import annotations

import argparse
import json
import statistics
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from autoresearch.benchmark.cifar10.dynamic_benchmark import run_candidate
from autoresearch.benchmark.cifar10.task_spec import ALL_FAMILIES, single_family_instance_overrides, task_mode_template_path


def one_run(output_root: Path, *, mode: str, max_train_steps: int, seed: int, repeat: int, timeout: int) -> dict[str, Any]:
    solution = task_mode_template_path(mode)
    run_dir = output_root / mode / f"steps_{max_train_steps}" / f"seed_{seed}" / f"rep_{repeat}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = run_candidate(
        solution,
        "autoresearch_cifar10",
        run_dir,
        run_id=f"{mode}_steps{max_train_steps}_seed{seed}_rep{repeat}",
        timeout_seconds=timeout,
        instance_overrides=single_family_instance_overrides(mode, seed=seed, max_train_steps=max_train_steps),
    )
    metrics = summary.get("metrics") or {}
    training_seconds = float(metrics.get("training_seconds") or summary.get("elapsed_wall_seconds") or 0.0)
    return {
        "mode": mode,
        "max_train_steps": max_train_steps,
        "seed": seed,
        "repeat": repeat,
        "training_seconds": training_seconds,
        "elapsed_wall_seconds": float(summary.get("elapsed_wall_seconds") or 0.0),
        "steps_per_second": (max_train_steps / training_seconds) if training_seconds > 0 else 0.0,
        "val_loss": float(metrics.get("val_loss") or summary.get("score", {}).get("latent_loss") or 0.0),
        "val_accuracy": float(metrics.get("val_accuracy") or 0.0),
        "passed": bool(summary.get("correctness", {}).get("passed")),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["mode"], row["max_train_steps"]), []).append(row)
    out: list[dict[str, Any]] = []
    for (mode, steps), items in sorted(grouped.items()):
        out.append(
            {
                "mode": mode,
                "max_train_steps": steps,
                "runs": len(items),
                "median_training_seconds": statistics.median(item["training_seconds"] for item in items),
                "median_steps_per_second": statistics.median(item["steps_per_second"] for item in items),
                "median_val_loss": statistics.median(item["val_loss"] for item in items),
                "median_val_accuracy": statistics.median(item["val_accuracy"] for item in items),
            }
        )
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--steps", default="2,4,6,8,12,16")
    parser.add_argument("--modes", default=",".join(ALL_FAMILIES))
    parser.add_argument("--seed", type=int, default=7001)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    steps_grid = [int(token) for token in args.steps.split(",") if token.strip()]
    modes = [token.strip() for token in args.modes.split(",") if token.strip()]

    jobs: list[tuple[str, int, int, int]] = []
    for mode in modes:
        for max_train_steps in steps_grid:
            for repeat in range(args.repeats):
                jobs.append((mode, max_train_steps, args.seed + repeat, repeat))

    rows: list[dict[str, Any]] = []
    if args.workers <= 1:
        for mode, max_train_steps, seed, repeat in jobs:
            rows.append(one_run(output_root, mode=mode, max_train_steps=max_train_steps, seed=seed, repeat=repeat, timeout=args.timeout))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [
                pool.submit(
                    one_run,
                    output_root,
                    mode=mode,
                    max_train_steps=max_train_steps,
                    seed=seed,
                    repeat=repeat,
                    timeout=args.timeout,
                )
                for mode, max_train_steps, seed, repeat in jobs
            ]
            for future in futures:
                rows.append(future.result())

    report = {
        "rows": rows,
        "summary": summarize(rows),
        "steps_grid": steps_grid,
        "modes": modes,
        "seed": args.seed,
        "repeats": args.repeats,
        "workers": args.workers,
    }
    output_path = output_root / "throughput_report.json"
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
