"""Benchmark-specific dispatch for prompts, summaries, classifiers, and evaluators."""

from __future__ import annotations

from dataclasses import dataclass
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
    if benchmark_id == "autoresearch_cifar10":
        return _autoresearch_cifar10_spec()
    raise KeyError(f"Unknown benchmark_id {benchmark_id!r}")


def infer_benchmark_id(config: dict[str, Any]) -> str:
    return str(config.get("benchmark", {}).get("id", "autoresearch_cifar10"))


def _autoresearch_cifar10_spec() -> BenchmarkSpec:
    from autoresearch.benchmark.cifar10.task_spec import (
        classify_edit_mode as autoresearch_classify_edit_mode,
    )
    from autoresearch.benchmark.cifar10.task_spec import (
        profile_summary as autoresearch_profile_summary,
    )
    from autoresearch.benchmark.cifar10.task_spec import (
        task_mode_from_instance_overrides as autoresearch_task_mode_from_instance_overrides,
    )
    from autoresearch.benchmark.cifar10.task_spec import (
        validate_solution_source as autoresearch_validate_source,
    )
    from vao.verifier import _evaluate_autoresearch_solution

    return BenchmarkSpec(
        benchmark_id="autoresearch_cifar10",
        prompt_template="autoresearch_program.txt",
        profile_summary=autoresearch_profile_summary,
        task_mode_from_instance_overrides=autoresearch_task_mode_from_instance_overrides,
        validate_source=autoresearch_validate_source,
        classify_edit_mode=autoresearch_classify_edit_mode,
        evaluate_solution=_evaluate_autoresearch_solution,
    )
