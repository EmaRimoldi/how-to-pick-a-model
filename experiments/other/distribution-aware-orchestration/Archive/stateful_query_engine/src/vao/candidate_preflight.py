"""Fast candidate API preflight before full benchmark evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from benchmarks.stateful_query_engine.dynamic_benchmark import load_candidate_class, validate_solution_source
from benchmarks.stateful_query_engine.harness.run_trace import normalize_output
from benchmarks.stateful_query_engine.reference import ReferenceQueryEngine


PREFLIGHT_INITIAL_ITEMS = {
    1: 7,
    3: 7,
    5: 10,
    8: -2,
    12: 10,
}

PREFLIGHT_OPERATIONS = [
    {"op": "aggregate_count", "lo": 1, "hi": 8},
    {"op": "range_sum", "lo": 1, "hi": 5},
    {"op": "top_k", "lo": 1, "hi": 12, "k": 3},
    {"op": "get", "key": 2},
    {"op": "put", "key": 3, "value": 11},
    {"op": "top_k", "lo": 1, "hi": 12, "k": 4},
    {"op": "delete", "key": 5},
    {"op": "get", "key": 5},
    {"op": "aggregate_count", "lo": 1, "hi": 12},
    {"op": "put", "key": 4, "value": 11},
    {"op": "top_k", "lo": 1, "hi": 4, "k": 3},
    {"op": "range_sum", "lo": 10, "hi": 2},
    {"op": "aggregate_count", "lo": 10, "hi": 2},
    {"op": "top_k", "lo": 10, "hi": 2, "k": 3},
]


def run_candidate_preflight(solution_path: Path) -> dict[str, Any]:
    """Run a small deterministic API/correctness check against the reference.

    This is not a replacement for the full hidden-workload verifier. It catches
    obvious API, state-layout, aggregate_count, and top_k ordering failures
    before spending minutes on full benchmark execution.
    """
    started = time.perf_counter()
    source = solution_path.read_text(encoding="utf-8")
    safety = validate_solution_source(source)
    if not safety["passed"]:
        return _failed("source_validation_failed", started, safety=safety)

    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        candidate_cls = load_candidate_class(solution_path, source_hash)
    except Exception as exc:  # noqa: BLE001 - return structured preflight failure.
        return _failed(
            "candidate_import_failed",
            started,
            load_error=f"{type(exc).__name__}: {exc}",
            safety=safety,
        )

    try:
        reference = ReferenceQueryEngine(dict(PREFLIGHT_INITIAL_ITEMS))
        candidate = candidate_cls(dict(PREFLIGHT_INITIAL_ITEMS))
    except Exception as exc:  # noqa: BLE001
        return _failed(
            "constructor_failed",
            started,
            exception=f"{type(exc).__name__}: {exc}",
            safety=safety,
        )

    for index, operation in enumerate(PREFLIGHT_OPERATIONS):
        try:
            expected = _apply_operation(reference, operation)
            actual = _apply_operation(candidate, operation)
        except Exception as exc:  # noqa: BLE001
            return _failed(
                "operation_exception",
                started,
                operation_index=index,
                operation=operation,
                exception=f"{type(exc).__name__}: {exc}",
                safety=safety,
            )
        expected_norm = normalize_output(expected)
        actual_norm = normalize_output(actual)
        if expected_norm != actual_norm:
            return _failed(
                "operation_divergence",
                started,
                operation_index=index,
                operation=operation,
                expected=expected_norm,
                actual=actual_norm,
                safety=safety,
            )

    return {
        "passed": True,
        "reason": None,
        "elapsed_wall_seconds": time.perf_counter() - started,
        "operation_count": len(PREFLIGHT_OPERATIONS),
        "safety": safety,
    }


def run_candidate_preflight_subprocess(solution_path: Path, timeout_seconds: int = 12) -> dict[str, Any]:
    """Run preflight in a subprocess so pathological candidates cannot hang."""
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    path_parts = [str(project_root / "src"), str(project_root), env.get("PYTHONPATH", "")]
    env["PYTHONPATH"] = os.pathsep.join(part for part in path_parts if part)
    cmd = [
        sys.executable,
        "-m",
        "vao.candidate_preflight",
        "--solution",
        str(solution_path),
    ]
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
        return {
            "passed": False,
            "reason": "preflight_timeout",
            "timeout_seconds": timeout_seconds,
        }
    if proc.returncode != 0:
        return {
            "passed": False,
            "reason": "preflight_subprocess_failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "passed": False,
            "reason": "preflight_output_not_json",
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
    return payload


def _apply_operation(engine: object, operation: dict[str, Any]) -> Any:
    op_name = operation["op"]
    if op_name == "put":
        return engine.put(operation["key"], operation["value"])
    if op_name == "delete":
        return engine.delete(operation["key"])
    if op_name == "get":
        return engine.get(operation["key"])
    if op_name == "range_sum":
        return engine.range_sum(operation["lo"], operation["hi"])
    if op_name == "aggregate_count":
        return engine.aggregate_count(operation["lo"], operation["hi"])
    if op_name == "top_k":
        return engine.top_k(operation["lo"], operation["hi"], operation["k"])
    raise ValueError(f"unknown operation: {op_name}")


def _failed(reason: str, started: float, **extra: Any) -> dict[str, Any]:
    return {
        "passed": False,
        "reason": reason,
        "elapsed_wall_seconds": time.perf_counter() - started,
        **extra,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run_candidate_preflight(Path(args.solution)), indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
