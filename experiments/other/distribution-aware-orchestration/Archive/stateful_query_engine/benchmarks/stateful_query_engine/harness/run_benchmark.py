"""CLI runner for stateful query-engine benchmark profiles."""

from __future__ import annotations

import argparse
import copy
import json
import math
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from benchmarks.stateful_query_engine.candidate import BaselineQueryEngine, CANDIDATE_REGISTRY
from benchmarks.stateful_query_engine.generators.workload_gen import generate_trace_suite
from benchmarks.stateful_query_engine.harness.evaluate_perf import evaluate_performance
from benchmarks.stateful_query_engine.harness.logging import EventLogger, append_jsonl, file_sha256, now_iso, sha256_text
from benchmarks.stateful_query_engine.harness.score import compute_score
from benchmarks.stateful_query_engine.harness.verify_correctness import verify_correctness
from benchmarks.stateful_query_engine.reference import ReferenceQueryEngine


EngineFactory = Callable[[dict[int, int]], object]
REPO_TASK_ROOT = Path(__file__).resolve().parents[1]


def candidate_factory(name: str) -> tuple[EngineFactory, Path, str]:
    try:
        spec = CANDIDATE_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unknown candidate {name!r}") from exc
    return spec["factory"], REPO_TASK_ROOT / str(spec["file"]), str(spec["mode"])


def load_instance_config() -> dict:
    return json.loads((REPO_TASK_ROOT / "metadata" / "instance_config.json").read_text())


def run_benchmark(
    *,
    candidate_name: str,
    profile: str,
    architecture: str,
    run_id: str,
    output_dir: Path,
    parent_candidate_id: str | None = None,
    baseline_perf_path: Path | None = None,
    instance_overrides: dict | None = None,
) -> dict:
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

    candidate_cls, candidate_path, mode_label = candidate_factory(candidate_name)
    candidate_hash = file_sha256(candidate_path)
    candidate_id = f"{candidate_name}:{candidate_hash[:12]}"
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
        active_context_tokens=context_tokens,
        context_ceiling_tokens=context_ceiling,
        context_pressure=context_pressure,
    )

    if arch["external_memory"]:
        memory_start = time.perf_counter()
        prior_payload = _read_memory(run_dir)
        logger.memory_event(
            "memory_read",
            run_id=run_id,
            architecture=architecture,
            agent_id=arch["agent_ids"][0],
            payload_bytes=len(prior_payload.encode("utf-8")),
            retrieval_count=1 if prior_payload else 0,
            provenance=str(run_dir / "logs" / "memory_state.jsonl"),
            latency_ms=(time.perf_counter() - memory_start) * 1000.0,
        )

    traces = generate_trace_suite(profile, config)
    trace_manifest = [trace.to_public_dict() for trace in traces]
    (run_dir / "artifacts" / "trace_manifest.json").write_text(json.dumps(trace_manifest, indent=2))
    family_tags = sorted({trace.family for trace in traces})

    dispatch_event = logger.event(
        "evaluation_dispatch",
        run_id=run_id,
        candidate_id=candidate_id,
        candidate_clock=0,
        profile=profile,
        trace_count=len(traces),
        workload_families=family_tags,
    )

    correctness = verify_correctness(candidate_cls, ReferenceQueryEngine, traces)
    logger.event(
        "correctness_result",
        run_id=run_id,
        candidate_id=candidate_id,
        candidate_clock=0,
        correctness=correctness.passed,
        first_divergence=correctness.first_divergence,
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

    candidate_perf = None
    if correctness.passed:
        candidate_perf = evaluate_performance(
            candidate_cls,
            traces,
            repetitions=int(profile_config["repetitions"]),
            warmup_prefix=int(profile_config["warmup_prefix"]),
        )
        (run_dir / "artifacts" / "candidate_perf.json").write_text(json.dumps(candidate_perf.to_dict(), indent=2))
        for family, metrics in candidate_perf.family_metrics.items():
            logger.event(
                "performance_result",
                run_id=run_id,
                candidate_id=candidate_id,
                candidate_clock=0,
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
        memory_ops=1 if arch["external_memory"] else 0,
        active_context_tokens=context_tokens,
        trace_ops=sum(len(trace.operations) for trace in traces),
    )
    improved = correctness.passed and math.isfinite(score.latent_loss) and score.latent_loss < 1.0
    candidate_record = {
        "run_id": run_id,
        "candidate_index": 0,
        "candidate_id": candidate_id,
        "parent_candidate_id": parent_candidate_id,
        "agent_id": arch["agent_ids"][0],
        "architecture": architecture,
        "profile": profile,
        "mode_label": mode_label,
        "artifact_hash": candidate_hash,
        "patch_fingerprint": sha256_text(candidate_name + candidate_hash),
        "changed_files": [str(candidate_path.relative_to(REPO_TASK_ROOT))],
        "diff_size_lines": _approx_diff_size(candidate_path),
        "correctness": correctness.passed,
        "first_divergence": correctness.first_divergence,
        "development_score": score.latent_loss if profile != "holdout" else None,
        "holdout_score": score.latent_loss if profile == "holdout" else None,
        "latent_loss": score.latent_loss,
        "family_losses": score.family_losses,
        "workload_families": family_tags,
        "elapsed_wall_seconds": elapsed_wall,
        "accounting_cost": accounting_cost,
        "memory_reads": 1 if arch["external_memory"] else 0,
        "memory_writes": 1 if arch["external_memory"] else 0,
        "retrieval_payload_bytes": len(context_payload.encode("utf-8")) if arch["external_memory"] else 0,
        "active_context_tokens": context_tokens,
        "context_ceiling_tokens": context_ceiling,
        "context_pressure": context_pressure,
        "improved": improved,
        "non_duplicate": True,
        "best_so_far": True,
        "event_index": dispatch_event["event_index"],
    }
    logger.candidate(**candidate_record)

    if arch["external_memory"]:
        memory_record = {
            "timestamp": now_iso(),
            "candidate_id": candidate_id,
            "claim": f"{candidate_name} score {score.latent_loss}",
            "workload_families": family_tags,
            "productive": improved,
        }
        append_jsonl(run_dir / "logs" / "memory_state.jsonl", memory_record)
        logger.memory_event(
            "memory_write",
            run_id=run_id,
            architecture=architecture,
            agent_id=arch["agent_ids"][0],
            payload_bytes=len(json.dumps(memory_record)),
            provenance=str(run_dir / "logs" / "memory_state.jsonl"),
        )

    summary = {
        "run_id": run_id,
        "timestamp": now_iso(),
        "candidate": candidate_name,
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
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
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


def _read_memory(run_dir: Path) -> str:
    path = run_dir / "logs" / "memory_state.jsonl"
    return path.read_text() if path.exists() else ""


def _reset_run_logs(run_dir: Path) -> None:
    for relative in [
        "logs/events.jsonl",
        "logs/candidates.jsonl",
        "logs/memory_events.jsonl",
        "logs/memory_state.jsonl",
    ]:
        path = run_dir / relative
        if path.exists():
            path.unlink()


def _build_context_payload(architecture: str, run_dir: Path) -> str:
    base = f"architecture={architecture}\napi_contract=stateful_query_engine/api_contract.md\n"
    memory_path = run_dir / "logs" / "memory_state.jsonl"
    if memory_path.exists():
        return base + memory_path.read_text()
    return base


def _accounting_cost(
    *,
    config: dict,
    eval_calls: int,
    memory_ops: int,
    active_context_tokens: int,
    trace_ops: int,
) -> float:
    constants = config["cost_model"]
    return (
        float(constants["eval_call"]) * eval_calls
        + float(constants["memory_op"]) * memory_ops
        + float(constants["context_token"]) * active_context_tokens
        + float(constants["trace_op"]) * trace_ops
    )


def _approx_diff_size(candidate_path: Path) -> int:
    try:
        return len(candidate_path.read_text().splitlines())
    except OSError:
        return 0


def apply_instance_overrides(config: dict, profile: str, overrides: dict) -> dict:
    if profile not in config["profiles"]:
        raise KeyError(f"Unknown profile {profile!r}")
    copied = copy.deepcopy(config)
    allowed = {
        "seed",
        "initial_size",
        "key_space",
        "trace_length",
        "traces_per_family",
        "families",
        "repetitions",
        "warmup_prefix",
        "value_max",
    }
    unknown = sorted(set(overrides) - allowed)
    if unknown:
        raise ValueError(f"Unsupported instance override key(s): {unknown}")
    copied["profiles"][profile].update(overrides)
    return copied


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=sorted(CANDIDATE_REGISTRY), required=True)
    parser.add_argument(
        "--profile",
        choices=sorted(load_instance_config()["profiles"]),
        required=True,
    )
    parser.add_argument("--architecture", choices=["d00", "d10", "d01", "d11"], required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", default=str(REPO_TASK_ROOT / "runs"))
    parser.add_argument("--parent-candidate-id", default=None)
    parser.add_argument("--baseline-perf-path", default=None)
    parser.add_argument("--instance-overrides-json", default=None)
    args = parser.parse_args(argv)
    instance_overrides = json.loads(args.instance_overrides_json) if args.instance_overrides_json else None
    summary = run_benchmark(
        candidate_name=args.candidate,
        profile=args.profile,
        architecture=args.architecture,
        run_id=args.run_id,
        output_dir=Path(args.output_dir),
        parent_candidate_id=args.parent_candidate_id,
        baseline_perf_path=Path(args.baseline_perf_path) if args.baseline_perf_path else None,
        instance_overrides=instance_overrides,
    )
    print(json.dumps({
        "run_id": summary["run_id"],
        "candidate_id": summary["candidate_id"],
        "correct": summary["correctness"]["passed"],
        "latent_loss": summary["score"]["latent_loss"],
        "elapsed_wall_seconds": summary["elapsed_wall_seconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
