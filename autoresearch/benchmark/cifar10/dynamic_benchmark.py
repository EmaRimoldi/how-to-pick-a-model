"""Dynamic benchmark wrapper for AutoResearch-style CIFAR-10 optimization."""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from autoresearch.benchmark.cifar10.task_spec import (
    apply_instance_overrides,
    load_instance_config,
    profile_summary,
    runtime_env,
    validate_solution_source,
)


METRIC_PATTERN = re.compile(r"^([a-zA-Z0-9_]+):\s+(.+?)\s*$")


def load_candidate_module(source_path: Path) -> ast.Module:
    return ast.parse(source_path.read_text(encoding="utf-8"))


def _parse_metrics(stdout: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for line in stdout.splitlines():
        match = METRIC_PATTERN.match(line.strip())
        if not match:
            continue
        key, raw_value = match.groups()
        value: Any = raw_value
        try:
            if raw_value.lower() == "nan":
                value = math.nan
            elif raw_value.lower() in {"none", "null"}:
                value = None
            elif "." in raw_value or "e" in raw_value.lower():
                value = float(raw_value)
            else:
                value = int(raw_value)
        except ValueError:
            value = raw_value
        metrics[key] = value
    return metrics


def run_candidate(
    solution_path: Path,
    profile_id: str,
    output_dir: Path,
    *,
    run_id: str,
    timeout_seconds: int = 300,
    instance_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_instance_config()
    effective = apply_instance_overrides(config, profile_id, instance_overrides)
    task_summary = profile_summary(profile_id, instance_overrides)

    raw_run_dir = output_dir / run_id
    workspace_dir = raw_run_dir / "workspace"
    artifacts_dir = raw_run_dir / "artifacts"
    logs_dir = raw_run_dir / "logs"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    train_path = workspace_dir / "train.py"
    prepare_src = Path(__file__).resolve().parent / "prepare.py"
    prepare_dst = workspace_dir / "prepare.py"
    shutil.copy2(solution_path, train_path)
    shutil.copy2(prepare_src, prepare_dst)

    validation = validate_solution_source(train_path.read_text(encoding="utf-8"))
    if not validation.get("passed"):
        summary = {
            "profile_id": profile_id,
            "task_summary": task_summary,
            "metrics": {},
            "score": {
                "latent_loss": math.inf,
                "family_losses": {str(task_summary.get("task_mode_true") or "unknown"): math.inf},
            },
            "correctness": {
                "passed": False,
                "first_divergence": {"reason": "source_validation_failed", "errors": validation.get("errors", [])},
            },
            "elapsed_wall_seconds": 0.0,
            "accounting_cost": 0.0,
        }
        (raw_run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
        return summary

    cmd = [sys.executable, "train.py"]
    env = os.environ.copy()
    env.update(runtime_env(profile_id, instance_overrides))

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=workspace_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - started
        summary = {
            "profile_id": profile_id,
            "task_summary": task_summary,
            "metrics": {},
            "score": {
                "latent_loss": math.inf,
                "family_losses": {str(task_summary.get("task_mode_true") or "unknown"): math.inf},
            },
            "correctness": {
                "passed": False,
                "first_divergence": {"reason": "candidate_timeout", "timeout_seconds": timeout_seconds},
            },
            "elapsed_wall_seconds": elapsed,
            "accounting_cost": elapsed,
        }
        (raw_run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
        return summary

    elapsed = time.perf_counter() - started
    stdout = proc.stdout
    stderr = proc.stderr
    (logs_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
    (logs_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    metrics = _parse_metrics(stdout)
    val_loss = float(metrics.get("val_loss", math.inf))
    val_accuracy = float(metrics.get("val_accuracy", 0.0))
    training_seconds = float(metrics.get("training_seconds", elapsed))
    correctness = proc.returncode == 0 and math.isfinite(val_loss) and val_loss > 0.0
    task_mode = str(task_summary.get("task_mode_true") or "unknown")
    summary = {
        "profile_id": profile_id,
        "task_summary": task_summary,
        "metrics": {
            **metrics,
            "val_loss": val_loss,
            "val_accuracy": val_accuracy,
            "training_seconds": training_seconds,
            "returncode": proc.returncode,
        },
        "score": {
            "latent_loss": val_loss if correctness else math.inf,
            "family_losses": {task_mode: val_loss if correctness else math.inf},
        },
        "correctness": {
            "passed": correctness,
            "first_divergence": None if correctness else {"reason": "runtime_failed", "stderr_tail": stderr[-2000:], "stdout_tail": stdout[-2000:]},
        },
        "elapsed_wall_seconds": elapsed,
        "accounting_cost": training_seconds,
    }
    (artifacts_dir / "candidate_metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    (raw_run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True)
    parser.add_argument("--profile", default="autoresearch_cifar10")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--instance-overrides-json", default=None)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)

    instance_overrides = json.loads(args.instance_overrides_json) if args.instance_overrides_json else None
    summary = run_candidate(
        Path(args.solution),
        args.profile,
        Path(args.output_dir),
        run_id=args.run_id,
        timeout_seconds=args.timeout,
        instance_overrides=instance_overrides,
    )
    print(json.dumps(summary, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
