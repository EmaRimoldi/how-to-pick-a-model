"""Verifier wrapper around the ported stateful query-engine benchmark."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from benchmarks.stateful_query_engine.dynamic_benchmark import validate_solution_source

from vao.candidate_preflight import run_candidate_preflight_subprocess
from vao.logging_utils import sha256_file, write_json
from vao.schemas import BranchEvaluation


def validate_source(source_text: str) -> dict[str, Any]:
    return validate_solution_source(source_text)


def evaluate_solution(
    solution_path: Path,
    profile_id: str,
    timeout_seconds: int,
    out_path: Path,
    *,
    branch_index: int = 0,
    primary_mode: str = "micro",
    secondary_modes: list[str] | None = None,
    declared_mode: str = "micro",
    inferred_mode: str = "micro",
    baseline_perf_path: Path | None = None,
    source_parent_hash: str | None = None,
    run_id: str | None = None,
    instance_overrides: dict[str, Any] | None = None,
    preflight_timeout_seconds: int | None = 12,
) -> BranchEvaluation:
    """Evaluate a proposed solution file in an isolated benchmark child run."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw_root = out_path.parent / "verifier_raw"
    eval_run_id = run_id or f"eval_{branch_index:02d}"
    if preflight_timeout_seconds is not None and preflight_timeout_seconds > 0:
        preflight_started = time.perf_counter()
        preflight = run_candidate_preflight_subprocess(
            solution_path,
            timeout_seconds=int(preflight_timeout_seconds),
        )
        if not preflight.get("passed"):
            elapsed = time.perf_counter() - preflight_started
            evaluation = BranchEvaluation(
                branch_index=branch_index,
                primary_mode=primary_mode,
                secondary_modes=secondary_modes or [],
                declared_mode=declared_mode,
                inferred_mode=inferred_mode,
                source_hash=sha256_file(solution_path),
                source_parent_hash=source_parent_hash,
                file_path=str(solution_path),
                correctness=False,
                latent_loss=math.inf,
                gain=0.0,
                family_losses={},
                first_divergence={"reason": "preflight_failed", "preflight": preflight},
                raw_verifier_path=str(raw_root / eval_run_id),
                elapsed_wall_seconds=elapsed,
                errors=[f"preflight_failed:{preflight.get('reason', 'unknown')}"],
            )
            write_json(out_path, evaluation)
            return evaluation
    cmd = [
        sys.executable,
        "-m",
        "benchmarks.stateful_query_engine.dynamic_benchmark",
        "--solution",
        str(solution_path),
        "--profile",
        profile_id,
        "--architecture",
        "d00",
        "--run-id",
        eval_run_id,
        "--output-dir",
        str(raw_root),
        "--candidate-index",
        str(branch_index),
    ]
    if baseline_perf_path is not None:
        cmd += ["--baseline-perf-path", str(baseline_perf_path)]
    if source_parent_hash is not None:
        cmd += ["--source-parent-hash", source_parent_hash]
    if instance_overrides:
        cmd += ["--instance-overrides-json", json.dumps(instance_overrides, sort_keys=True)]

    env = os.environ.copy()
    project_root = Path(__file__).resolve().parents[2]
    path_parts = [str(project_root / "src"), str(project_root), env.get("PYTHONPATH", "")]
    env["PYTHONPATH"] = os.pathsep.join(part for part in path_parts if part)

    started = time.perf_counter()
    errors: list[str] = []
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            cwd=project_root,
            env=env,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - started
        evaluation = BranchEvaluation(
            branch_index=branch_index,
            primary_mode=primary_mode,
            secondary_modes=secondary_modes or [],
            declared_mode=declared_mode,
            inferred_mode=inferred_mode,
            source_hash=sha256_file(solution_path),
            source_parent_hash=source_parent_hash,
            file_path=str(solution_path),
            correctness=False,
            latent_loss=math.inf,
            gain=0.0,
            family_losses={},
            first_divergence={"reason": "candidate_timeout", "timeout_seconds": timeout_seconds},
            raw_verifier_path=str(raw_root / eval_run_id),
            elapsed_wall_seconds=elapsed,
            errors=["candidate_timeout"],
        )
        write_json(out_path, evaluation)
        return evaluation

    elapsed = time.perf_counter() - started
    raw_run_dir = raw_root / eval_run_id
    summary_path = raw_run_dir / "summary.json"
    if proc.returncode != 0:
        errors.append(f"verifier_returncode={proc.returncode}")
        if proc.stderr:
            errors.append(proc.stderr[-2000:])
    if not summary_path.exists():
        evaluation = BranchEvaluation(
            branch_index=branch_index,
            primary_mode=primary_mode,
            secondary_modes=secondary_modes or [],
            declared_mode=declared_mode,
            inferred_mode=inferred_mode,
            source_hash=sha256_file(solution_path),
            source_parent_hash=source_parent_hash,
            file_path=str(solution_path),
            correctness=False,
            latent_loss=math.inf,
            gain=0.0,
            family_losses={},
            first_divergence={"reason": "verifier_failed", "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]},
            raw_verifier_path=str(raw_run_dir),
            elapsed_wall_seconds=elapsed,
            errors=errors or ["missing_summary"],
        )
        write_json(out_path, evaluation)
        return evaluation

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    score = summary.get("score", {})
    correctness = summary.get("correctness", {})
    aggregate = _candidate_perf_aggregate(raw_run_dir)
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
        median_p95_latency_ns=aggregate.get("median_p95_latency_ns"),
        median_peak_memory_bytes=aggregate.get("median_peak_memory_bytes"),
        raw_verifier_path=str(raw_run_dir),
        elapsed_wall_seconds=float(summary.get("elapsed_wall_seconds", elapsed)),
        accounting_cost=float(summary.get("accounting_cost", 0.0)),
        errors=errors,
    )
    write_json(out_path, evaluation)
    return evaluation


def _candidate_perf_aggregate(raw_run_dir: Path) -> dict[str, float | None]:
    perf_path = raw_run_dir / "artifacts" / "candidate_perf.json"
    if not perf_path.exists():
        return {"median_p95_latency_ns": None, "median_peak_memory_bytes": None}
    data = json.loads(perf_path.read_text(encoding="utf-8"))
    aggregate = data.get("aggregate") or {}
    return {
        "median_p95_latency_ns": aggregate.get("median_p95_latency_ns"),
        "median_peak_memory_bytes": aggregate.get("median_peak_memory_bytes"),
    }


def smoke_test() -> None:
    root = Path("artifacts/verifier_smoke")
    root.mkdir(parents=True, exist_ok=True)
    result = evaluate_solution(
        Path("benchmarks/stateful_query_engine/solution_template.py"),
        "hard_optimization",
        240,
        root / "baseline_verification.json",
        run_id="baseline_smoke",
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, allow_nan=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke_test", action="store_true")
    parser.add_argument("--solution")
    parser.add_argument("--profile", default="hard_optimization")
    parser.add_argument("--out", default="artifacts/verifier_eval.json")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args(argv)
    if args.smoke_test:
        smoke_test()
        return
    if not args.solution:
        parser.error("--solution is required unless --smoke_test is set")
    result = evaluate_solution(Path(args.solution), args.profile, args.timeout, Path(args.out))
    print(json.dumps(result.model_dump(mode="json"), indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
