"""Evaluate an arbitrary editable solution file for the query-engine task."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import math
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from benchmarks.stateful_query_engine.candidate import BaselineQueryEngine
from benchmarks.stateful_query_engine.generators.workload_gen import generate_trace_suite
from benchmarks.stateful_query_engine.harness.evaluate_perf import evaluate_performance
from benchmarks.stateful_query_engine.harness.logging import EventLogger, file_sha256, now_iso, sha256_text
from benchmarks.stateful_query_engine.harness.run_benchmark import (
    _accounting_cost,
    _build_context_payload,
    _reset_run_logs,
    apply_instance_overrides,
    load_instance_config,
)
from benchmarks.stateful_query_engine.harness.score import compute_score
from benchmarks.stateful_query_engine.harness.verify_correctness import CorrectnessResult, verify_correctness
from benchmarks.stateful_query_engine.reference import ReferenceQueryEngine


EngineFactory = Callable[[dict[int, int]], object]
REPO_TASK_ROOT = Path(__file__).resolve().parent

ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "array",
    "bisect",
    "collections",
    "dataclasses",
    "heapq",
    "itertools",
    "math",
    "typing",
}
BANNED_CALL_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
    "vars",
}
BANNED_ATTRIBUTE_NAMES = {
    "connect",
    "mkdir",
    "open",
    "popen",
    "read_bytes",
    "read_text",
    "remove",
    "rename",
    "replace",
    "rmdir",
    "socket",
    "system",
    "unlink",
    "write_bytes",
    "write_text",
}


def run_dynamic_benchmark(
    *,
    candidate_file: Path,
    profile: str,
    architecture: str,
    run_id: str,
    output_dir: Path,
    parent_candidate_id: str | None = None,
    baseline_perf_path: Path | None = None,
    instance_overrides: dict[str, Any] | None = None,
    candidate_index: int = 0,
    source_parent_hash: str | None = None,
) -> dict[str, Any]:
    """Run correctness and performance evaluation for a solution.py artifact."""
    config = load_instance_config()
    if instance_overrides:
        config = apply_instance_overrides(config, profile, instance_overrides)
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)
    (run_dir / "analysis").mkdir(exist_ok=True)
    _reset_run_logs(run_dir)
    logger = EventLogger(run_dir)
    start_monotonic = time.monotonic()

    source_text = candidate_file.read_text(encoding="utf-8")
    candidate_hash = sha256_text(source_text)
    archived_source = run_dir / "artifacts" / "solution.py"
    archived_source.write_text(source_text, encoding="utf-8")
    candidate_id = f"open_step_{candidate_index:04d}:{candidate_hash[:12]}"

    arch = config["architectures"][architecture]
    context_ceiling = int(config["measurement"]["context_ceiling_tokens"])
    context_payload = _build_context_payload(architecture, run_dir)
    context_tokens = max(1, len(context_payload) // 4)
    context_pressure = context_tokens / context_ceiling

    logger.event(
        "run_start",
        run_id=run_id,
        architecture=architecture,
        candidate_id=candidate_id,
        parent_candidate_id=parent_candidate_id,
        agent_id=arch["agent_ids"][0],
        candidate_file=str(candidate_file),
        source_hash=candidate_hash,
        source_parent_hash=source_parent_hash,
        active_context_tokens=context_tokens,
        context_ceiling_tokens=context_ceiling,
        context_pressure=context_pressure,
    )

    traces = generate_trace_suite(profile, config)
    trace_manifest = [trace.to_public_dict() for trace in traces]
    (run_dir / "artifacts" / "trace_manifest.json").write_text(json.dumps(trace_manifest, indent=2))
    family_tags = sorted({trace.family for trace in traces})

    dispatch_event = logger.event(
        "evaluation_dispatch",
        run_id=run_id,
        candidate_id=candidate_id,
        candidate_clock=candidate_index,
        profile=profile,
        trace_count=len(traces),
        workload_families=family_tags,
    )

    profile_config = config["profiles"][profile]
    if baseline_perf_path is not None:
        baseline_perf_dict = json.loads(baseline_perf_path.read_text())
        baseline_perf = SimpleNamespace(family_metrics=baseline_perf_dict["family_metrics"])
        logger.event(
            "baseline_perf_reused",
            run_id=run_id,
            candidate_id=candidate_id,
            source=str(baseline_perf_path),
        )
    else:
        baseline_perf = evaluate_performance(
            BaselineQueryEngine,
            traces,
            repetitions=int(profile_config["repetitions"]),
            warmup_prefix=int(profile_config["warmup_prefix"]),
        )
        baseline_perf_dict = baseline_perf.to_dict()
    (run_dir / "artifacts" / "baseline_perf.json").write_text(json.dumps(baseline_perf_dict, indent=2))

    safety = validate_solution_source(source_text)
    candidate_cls: type | None = None
    load_error: str | None = None
    if safety["passed"]:
        try:
            candidate_cls = load_candidate_class(archived_source, candidate_hash)
        except Exception as exc:  # noqa: BLE001 - log import failures as candidate failures.
            load_error = f"{type(exc).__name__}: {exc}"

    if not safety["passed"] or candidate_cls is None:
        reason = "safety_check_failed" if not safety["passed"] else "candidate_import_failed"
        correctness = CorrectnessResult(
            passed=False,
            trace_count=len(traces),
            query_output_count=0,
            first_divergence={
                "reason": reason,
                "safety": safety,
                "load_error": load_error,
            },
            family_results={},
        )
        candidate_perf = None
        logger.event(
            "correctness_result",
            run_id=run_id,
            candidate_id=candidate_id,
            candidate_clock=candidate_index,
            correctness=False,
            first_divergence=correctness.first_divergence,
            workload_families=family_tags,
        )
    else:
        correctness = verify_correctness(candidate_cls, ReferenceQueryEngine, traces)
        logger.event(
            "correctness_result",
            run_id=run_id,
            candidate_id=candidate_id,
            candidate_clock=candidate_index,
            correctness=correctness.passed,
            first_divergence=correctness.first_divergence,
            workload_families=family_tags,
        )
        candidate_perf = None
        if correctness.passed:
            candidate_perf = evaluate_performance(
                candidate_cls,
                traces,
                repetitions=int(profile_config["repetitions"]),
                warmup_prefix=int(profile_config["warmup_prefix"]),
            )
            (run_dir / "artifacts" / "candidate_perf.json").write_text(
                json.dumps(candidate_perf.to_dict(), indent=2)
            )
            for family, metrics in candidate_perf.family_metrics.items():
                logger.event(
                    "performance_result",
                    run_id=run_id,
                    candidate_id=candidate_id,
                    candidate_clock=candidate_index,
                    family=family,
                    median_p95_latency_ns=metrics["median_p95_latency_ns"],
                    median_throughput_ops_per_sec=metrics["median_throughput_ops_per_sec"],
                    median_peak_memory_bytes=metrics["median_peak_memory_bytes"],
                    latency_iqr_ns=metrics["latency_iqr_ns"],
                )

    score = compute_score(
        correctness,
        candidate_perf,
        baseline_perf,
        latency_weight=float(config["score"]["latency_weight"]),
        memory_weight=float(config["score"]["memory_weight"]),
    )
    elapsed_wall = time.monotonic() - start_monotonic
    accounting_cost = _accounting_cost(
        config=config,
        eval_calls=1,
        memory_ops=0,
        active_context_tokens=context_tokens,
        trace_ops=sum(len(trace.operations) for trace in traces),
    )
    improved = correctness.passed and math.isfinite(score.latent_loss) and score.latent_loss < 1.0
    candidate_record = {
        "run_id": run_id,
        "candidate_index": candidate_index,
        "candidate_id": candidate_id,
        "parent_candidate_id": parent_candidate_id,
        "agent_id": arch["agent_ids"][0],
        "architecture": architecture,
        "profile": profile,
        "mode_label": "open_ended_patch",
        "artifact_hash": candidate_hash,
        "source_hash": candidate_hash,
        "source_parent_hash": source_parent_hash,
        "patch_fingerprint": sha256_text(source_text),
        "changed_files": [str(candidate_file)],
        "diff_size_lines": len(source_text.splitlines()),
        "safety": safety,
        "load_error": load_error,
        "correctness": correctness.passed,
        "first_divergence": correctness.first_divergence,
        "development_score": score.latent_loss if profile != "holdout" else None,
        "holdout_score": score.latent_loss if profile == "holdout" else None,
        "latent_loss": score.latent_loss,
        "family_losses": score.family_losses,
        "workload_families": family_tags,
        "elapsed_wall_seconds": elapsed_wall,
        "accounting_cost": accounting_cost,
        "memory_reads": 0,
        "memory_writes": 0,
        "retrieval_payload_bytes": 0,
        "active_context_tokens": context_tokens,
        "context_ceiling_tokens": context_ceiling,
        "context_pressure": context_pressure,
        "improved": improved,
        "non_duplicate": True,
        "best_so_far": True,
        "event_index": dispatch_event["event_index"],
    }
    logger.candidate(**candidate_record)

    summary = {
        "run_id": run_id,
        "timestamp": now_iso(),
        "candidate": "open_ended_solution",
        "candidate_file": str(candidate_file),
        "candidate_id": candidate_id,
        "architecture": architecture,
        "profile": profile,
        "instance_overrides": instance_overrides or {},
        "correctness": correctness.to_dict(),
        "score": score.to_dict(),
        "elapsed_wall_seconds": elapsed_wall,
        "accounting_cost": accounting_cost,
        "trace_manifest": trace_manifest,
        "candidate_record": candidate_record,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=True))
    logger.event(
        "run_complete",
        run_id=run_id,
        candidate_id=candidate_id,
        latent_loss=score.latent_loss,
        elapsed_wall_seconds=elapsed_wall,
        accounting_cost=accounting_cost,
        correct=correctness.passed,
    )
    return summary


def validate_solution_source(source_text: str) -> dict[str, Any]:
    """Static safety screen for generated candidate code."""
    errors: list[str] = []
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        return {"passed": False, "errors": [f"SyntaxError: {exc}"]}

    has_candidate = any(
        isinstance(node, ast.ClassDef) and node.name == "CandidateQueryEngine"
        for node in tree.body
    )
    if not has_candidate:
        errors.append("missing CandidateQueryEngine class")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in ALLOWED_IMPORT_ROOTS:
                    errors.append(f"disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root not in ALLOWED_IMPORT_ROOTS:
                errors.append(f"disallowed import-from: {module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_CALL_NAMES:
                errors.append(f"banned call: {node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in BANNED_ATTRIBUTE_NAMES:
                errors.append(f"banned attribute call: {node.func.attr}")
        elif isinstance(node, ast.Name):
            if node.id in {"__builtins__", "__loader__", "__spec__"}:
                errors.append(f"banned name: {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                errors.append(f"banned dunder attribute: {node.attr}")

    return {
        "passed": not errors,
        "errors": sorted(set(errors)),
        "allowed_import_roots": sorted(ALLOWED_IMPORT_ROOTS),
    }


def load_candidate_class(candidate_file: Path, source_hash: str) -> type:
    module_name = f"stateful_query_engine_open_candidate_{source_hash[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, candidate_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not build import spec for {candidate_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate_cls = getattr(module, "CandidateQueryEngine")
    required = ["put", "delete", "get", "range_sum", "aggregate_count", "top_k"]
    missing = [name for name in required if not hasattr(candidate_cls, name)]
    if missing:
        raise TypeError(f"CandidateQueryEngine missing methods: {missing}")
    return candidate_cls


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-file", "--solution", dest="candidate_file", required=True)
    parser.add_argument("--profile", choices=sorted(load_instance_config()["profiles"]), required=True)
    parser.add_argument("--architecture", choices=["d00", "d10", "d01", "d11"], default="d00")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", default=str(REPO_TASK_ROOT / "runs"))
    parser.add_argument("--out", default=None, help="Optional path for a copy of the full summary JSON.")
    parser.add_argument("--parent-candidate-id", default=None)
    parser.add_argument("--baseline-perf-path", default=None)
    parser.add_argument("--instance-overrides-json", default=None)
    parser.add_argument("--candidate-index", type=int, default=0)
    parser.add_argument("--source-parent-hash", default=None)
    args = parser.parse_args(argv)
    instance_overrides = json.loads(args.instance_overrides_json) if args.instance_overrides_json else None
    run_id = args.run_id
    if run_id is None:
        run_id = Path(args.out).stem if args.out else f"dynamic_eval_{int(time.time())}"
    summary = run_dynamic_benchmark(
        candidate_file=Path(args.candidate_file),
        profile=args.profile,
        architecture=args.architecture,
        run_id=run_id,
        output_dir=Path(args.output_dir),
        parent_candidate_id=args.parent_candidate_id,
        baseline_perf_path=Path(args.baseline_perf_path) if args.baseline_perf_path else None,
        instance_overrides=instance_overrides,
        candidate_index=args.candidate_index,
        source_parent_hash=args.source_parent_hash,
    )
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    print(json.dumps({
        "run_id": summary["run_id"],
        "candidate_id": summary["candidate_id"],
        "correct": summary["correctness"]["passed"],
        "latent_loss": summary["score"]["latent_loss"],
        "elapsed_wall_seconds": summary["elapsed_wall_seconds"],
    }, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
