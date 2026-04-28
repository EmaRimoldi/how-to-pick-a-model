"""Benchmark-specific dispatch for prompts, summaries, classifiers, and evaluators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from vao.schemas import BranchEvaluation


@dataclass(frozen=True)
class BenchmarkSpec:
    benchmark_id: str
    prompt_template: str
    profile_summary: Callable[[str, dict[str, Any] | None], dict[str, Any]]
    task_mode_from_instance_overrides: Callable[[dict[str, Any] | None], str | None]
    validate_source: Callable[[str], dict[str, Any]]
    classify_edit_mode: Callable[[str, str], tuple[str, list[str], dict[str, Any]]]
    evaluate_solution: Callable[..., BranchEvaluation]


def get_benchmark_spec(benchmark_id: str) -> BenchmarkSpec:
    if benchmark_id == "stateful_query_engine":
        return _stateful_query_engine_spec()
    if benchmark_id == "autoresearch_cifar10":
        return _autoresearch_cifar10_spec()
    raise KeyError(f"Unknown benchmark_id {benchmark_id!r}")


def infer_benchmark_id(config: dict[str, Any]) -> str:
    return str(config.get("benchmark", {}).get("id", "stateful_query_engine"))


def _stateful_query_engine_spec() -> BenchmarkSpec:
    from benchmarks.stateful_query_engine.harness.run_benchmark import apply_instance_overrides, load_instance_config
    from vao.verifier import _evaluate_stateful_solution
    from vao.verifier import _validate_stateful_source
    from vao.taxonomy import classify_edit_mode as stateful_classify_edit_mode
    from vao.task_modes import task_mode_from_instance_overrides as stateful_task_mode_from_instance_overrides

    def stateful_profile_summary(profile_id: str, instance_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        config = load_instance_config()
        if instance_overrides:
            config = apply_instance_overrides(config, profile_id, instance_overrides)
        profile = config["profiles"][profile_id]
        return {
            "profile_id": profile_id,
            "initial_size": profile.get("initial_size"),
            "key_space": profile.get("key_space"),
            "trace_length": profile.get("trace_length"),
            "traces_per_family": profile.get("traces_per_family"),
            "families": profile.get("families"),
            "repetitions": profile.get("repetitions"),
            "warmup_prefix": profile.get("warmup_prefix"),
            "task_mode_true": stateful_task_mode_from_instance_overrides(instance_overrides),
        }

    return BenchmarkSpec(
        benchmark_id="stateful_query_engine",
        prompt_template="single_step_program.txt",
        profile_summary=stateful_profile_summary,
        task_mode_from_instance_overrides=stateful_task_mode_from_instance_overrides,
        validate_source=_validate_stateful_source,
        classify_edit_mode=stateful_classify_edit_mode,
        evaluate_solution=_evaluate_stateful_solution,
    )


def _autoresearch_cifar10_spec() -> BenchmarkSpec:
    from benchmarks.autoresearch_cifar10.task_spec import (
        classify_edit_mode as autoresearch_classify_edit_mode,
    )
    from benchmarks.autoresearch_cifar10.task_spec import (
        profile_summary as autoresearch_profile_summary,
    )
    from benchmarks.autoresearch_cifar10.task_spec import (
        task_mode_from_instance_overrides as autoresearch_task_mode_from_instance_overrides,
    )
    from benchmarks.autoresearch_cifar10.task_spec import (
        validate_solution_source as autoresearch_validate_source,
    )
    from vao.verifier import _evaluate_autoresearch_solution

    return BenchmarkSpec(
        benchmark_id="autoresearch_cifar10",
        prompt_template="autoresearch_single_step_program.txt",
        profile_summary=autoresearch_profile_summary,
        task_mode_from_instance_overrides=autoresearch_task_mode_from_instance_overrides,
        validate_source=autoresearch_validate_source,
        classify_edit_mode=autoresearch_classify_edit_mode,
        evaluate_solution=_evaluate_autoresearch_solution,
    )
