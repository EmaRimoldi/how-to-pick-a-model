"""Verifier wrappers for active AutoResearch offline evaluation."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from vao.logging_utils import sha256_file, write_json
from vao.schemas import BranchEvaluation
from vao.taxonomy import DEFAULT_MODE


def validate_source(source_text: str, *, benchmark_id: str = "autoresearch_cifar10") -> dict[str, Any]:
    if benchmark_id != "autoresearch_cifar10":
        raise KeyError(f"Archived benchmark_id {benchmark_id!r} is not part of the active verifier")
    from autoresearch.benchmark.cifar10.task_spec import validate_solution_source as validate_autoresearch_source

    return validate_autoresearch_source(source_text)


def evaluate_solution(
    solution_path: Path,
    profile_id: str,
    timeout_seconds: int,
    out_path: Path,
    *,
    branch_index: int = 0,
    primary_mode: str = DEFAULT_MODE,
    secondary_modes: list[str] | None = None,
    declared_mode: str = DEFAULT_MODE,
    inferred_mode: str = DEFAULT_MODE,
    baseline_perf_path: Path | None = None,
    source_parent_hash: str | None = None,
    run_id: str | None = None,
    instance_overrides: dict[str, Any] | None = None,
    preflight_timeout_seconds: int | None = None,
    benchmark_id: str = "autoresearch_cifar10",
) -> BranchEvaluation:
    if baseline_perf_path is not None or preflight_timeout_seconds is not None:
        pass
    if benchmark_id != "autoresearch_cifar10":
        raise KeyError(f"Archived benchmark_id {benchmark_id!r} is not part of the active verifier")
    return _evaluate_autoresearch_solution(
        solution_path,
        profile_id,
        timeout_seconds,
        out_path,
        branch_index=branch_index,
        primary_mode=primary_mode,
        secondary_modes=secondary_modes,
        declared_mode=declared_mode,
        inferred_mode=inferred_mode,
        source_parent_hash=source_parent_hash,
        run_id=run_id,
        instance_overrides=instance_overrides,
    )


def _evaluate_autoresearch_solution(
    solution_path: Path,
    profile_id: str,
    timeout_seconds: int,
    out_path: Path,
    *,
    branch_index: int = 0,
    primary_mode: str = DEFAULT_MODE,
    secondary_modes: list[str] | None = None,
    declared_mode: str = DEFAULT_MODE,
    inferred_mode: str = DEFAULT_MODE,
    source_parent_hash: str | None = None,
    run_id: str | None = None,
    instance_overrides: dict[str, Any] | None = None,
) -> BranchEvaluation:
    from autoresearch.benchmark.cifar10.dynamic_benchmark import run_candidate

    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw_root = out_path.parent / "verifier_raw"
    eval_run_id = run_id or f"eval_{branch_index:02d}"
    started = time.perf_counter()
    summary = run_candidate(
        solution_path,
        profile_id,
        raw_root,
        run_id=eval_run_id,
        timeout_seconds=timeout_seconds,
        instance_overrides=instance_overrides,
    )
    elapsed = time.perf_counter() - started
    score = summary.get("score", {})
    correctness = summary.get("correctness", {})
    metrics = summary.get("metrics", {})
    evaluation = BranchEvaluation(
        branch_index=branch_index,
        primary_mode=primary_mode,
        secondary_modes=secondary_modes or [],
        declared_mode=declared_mode,
        inferred_mode=inferred_mode,
        source_hash=sha256_file(solution_path),
        source_parent_hash=source_parent_hash,
        file_path=str(solution_path),
        correctness=bool(correctness.get("passed")),
        latent_loss=float(score.get("latent_loss", math.inf)),
        gain=0.0,
        family_losses={str(k): float(v) for k, v in (score.get("family_losses") or {}).items()},
        first_divergence=correctness.get("first_divergence"),
        raw_verifier_path=str(raw_root / eval_run_id),
        elapsed_wall_seconds=float(summary.get("elapsed_wall_seconds", elapsed)),
        accounting_cost=float(summary.get("accounting_cost", metrics.get("training_seconds", 0.0) or 0.0)),
        errors=[] if correctness.get("passed") else ["autoresearch_runtime_failed"],
    )
    write_json(out_path, evaluation)
    return evaluation


def smoke_test() -> None:
    root = Path("artifacts/verifier_smoke")
    root.mkdir(parents=True, exist_ok=True)
    result = evaluate_solution(
        Path("autoresearch/benchmark/cifar10/solution_template.py"),
        "autoresearch_cifar10",
        120,
        root / "baseline_verification.json",
        run_id="baseline_smoke",
        instance_overrides={
            "workloads": ["cnn_compact"],
            "families": ["cnn_compact"],
            "train_subset_size": 128,
            "val_subset_size": 64,
            "max_train_steps": 1,
            "seed": 7001,
        },
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, allow_nan=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke_test", action="store_true")
    parser.add_argument("--solution")
    parser.add_argument("--profile", default="autoresearch_cifar10")
    parser.add_argument("--out", default="artifacts/verifier_eval.json")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--benchmark-id", default="autoresearch_cifar10")
    args = parser.parse_args(argv)
    if args.smoke_test:
        smoke_test()
        return
    if not args.solution:
        parser.error("--solution is required unless --smoke_test is set")
    result = evaluate_solution(
        Path(args.solution),
        args.profile,
        args.timeout,
        Path(args.out),
        benchmark_id=args.benchmark_id,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
