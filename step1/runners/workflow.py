"""Deterministic HumanEval orchestration helpers used by seed and online runners."""

from __future__ import annotations

import ast
import doctest
import time
from typing import Any

from oracles.check_generate_tests import check as check_generate_tests
from oracles.check_implement import check as check_implement
from oracles.check_repair import check as check_repair
from oracles.check_route import check as check_route
from oracles.check_understand_spec import check as check_understand_spec
from oracles.common import function_signature, public_examples
from runners.sandbox import run_generated_tests, run_public_examples, run_terminal_verifier


FORBIDDEN_SOLVING_FIELDS = {"canonical_solution", "test"}
MODEL_NODE_IDS = ("understand_spec", "plan", "generate_tests", "implement", "repair")


def assert_public_solving_instance(instance: dict[str, Any], *, context: str) -> None:
    forbidden = sorted(FORBIDDEN_SOLVING_FIELDS.intersection(instance))
    if forbidden:
        raise ValueError(f"{context} received non-public solving fields: {forbidden}")


def verifier_instance_from_public(instance: dict[str, Any], verifier_test: str) -> dict[str, Any]:
    assert_public_solving_instance(instance, context="verifier_instance_from_public")
    return {
        "task_id": instance["task_id"],
        "prompt": instance["prompt"],
        "entry_point": instance["entry_point"],
        "test": verifier_test,
    }


def load_completion_map(path: str | None) -> dict[str, str]:
    if path is None:
        return {}
    import json
    from pathlib import Path

    completions: dict[str, str] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if "task_id" not in row or "completion" not in row:
                raise ValueError(f"Completion row must contain task_id and completion keys: {row}")
            task_id = str(row["task_id"])
            if task_id in completions:
                raise ValueError(f"Duplicate completion row for task_id {task_id!r}")
            if not isinstance(row["completion"], str) or not row["completion"].strip():
                raise ValueError(f"Completion for task_id {task_id!r} is empty or non-string")
            completions[str(row["task_id"])] = str(row["completion"])
    return completions


def load_node_record_map(path: str | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    import json
    from pathlib import Path

    records: dict[str, dict[str, Any]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            _validate_node_record(row)
            task_id = str(row["task_id"])
            if task_id in records:
                raise ValueError(f"Duplicate per-node record for task_id {task_id!r}")
            records[task_id] = row
    return records


def _validate_node_record(row: dict[str, Any]) -> None:
    if "task_id" not in row:
        raise ValueError(f"Per-node record is missing task_id: {row}")
    missing = [node_id for node_id in MODEL_NODE_IDS if node_id not in row]
    if missing:
        raise ValueError(f"Per-node record for {row.get('task_id')!r} is missing node field(s): {missing}")
    if not isinstance(row["understand_spec"], dict):
        raise ValueError(f"understand_spec must be an object for {row['task_id']!r}")
    if not isinstance(row["plan"], dict):
        raise ValueError(f"plan must be an object for {row['task_id']!r}")
    if not isinstance(row["generate_tests"], dict):
        raise ValueError(f"generate_tests must be an object for {row['task_id']!r}")
    for node_id in ("implement", "repair"):
        node_payload = row[node_id]
        if not isinstance(node_payload, dict):
            raise ValueError(f"{node_id} must be an object for {row['task_id']!r}")
        completion = node_payload.get("completion")
        if not isinstance(completion, str) or not completion.strip():
            raise ValueError(f"{node_id}.completion is empty or non-string for {row['task_id']!r}")


def validate_completion_coverage(
    *,
    instances: list[dict[str, Any]],
    completions: dict[str, str],
    completion_jsonl: str | None,
    allow_mock: bool,
) -> None:
    task_ids = [str(instance["task_id"]) for instance in instances]
    missing = sorted(task_id for task_id in task_ids if task_id not in completions)
    extra = sorted(task_id for task_id in completions if task_id not in set(task_ids))
    if missing and not allow_mock:
        raise ValueError(
            "Completion coverage check failed: "
            f"{len(missing)} missing task_id(s) in {completion_jsonl!r}; first missing={missing[:10]}"
        )
    if extra:
        print(
            {
                "warning": "completion_jsonl_contains_extra_task_ids",
                "extra_count": len(extra),
                "first_extra": extra[:10],
            }
        )


def validate_node_record_coverage(
    *,
    instances: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    record_jsonl: str | None,
    allow_mock: bool,
) -> None:
    task_ids = [str(instance["task_id"]) for instance in instances]
    missing = sorted(task_id for task_id in task_ids if task_id not in records)
    extra = sorted(task_id for task_id in records if task_id not in set(task_ids))
    if missing and not allow_mock:
        raise ValueError(
            "Per-node record coverage check failed: "
            f"{len(missing)} missing task_id(s) in {record_jsonl!r}; first missing={missing[:10]}"
        )
    if extra:
        print(
            {
                "warning": "per_node_jsonl_contains_extra_task_ids",
                "extra_count": len(extra),
                "first_extra": extra[:10],
            }
        )


def default_completion() -> str:
    return "    pass\n"


def default_node_record(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "understand_spec": {
            "signature": {"name": None, "args": []},
            "docstring_summary": "",
            "input_types": [],
            "output_type": "unknown",
            "examples": [],
            "edge_cases": [],
            "invariants": [],
        },
        "plan": {"algorithm": "", "cases": [], "complexity": "", "implementation_notes": []},
        "generate_tests": {"tests": [], "rationale": ""},
        "implement": {"completion": default_completion(), "notes": "mock default"},
        "repair": {"completion": default_completion(), "repair_summary": "mock default"},
        "node_usage": {},
    }


def completion_from_record(record: dict[str, Any], *, prefer_repair: bool = False) -> str:
    if prefer_repair:
        repair = record.get("repair", {})
        if isinstance(repair, dict) and isinstance(repair.get("completion"), str) and repair["completion"].strip():
            return repair["completion"]
    implement = record.get("implement", {})
    if isinstance(implement, dict) and isinstance(implement.get("completion"), str) and implement["completion"].strip():
        return implement["completion"]
    return default_completion()


def spec_from_prompt(instance: dict[str, Any], profile_feature: dict[str, Any] | None = None) -> dict[str, Any]:
    signature = function_signature(instance["prompt"])
    examples = public_examples(instance["prompt"], instance["entry_point"])
    feature = profile_feature or {}
    return {
        "signature": signature,
        "docstring_summary": "Prompt-derived HumanEval function specification.",
        "input_types": sorted((feature.get("example_arg_types") or {}).keys()),
        "output_type": next(iter((feature.get("example_return_types") or {"unknown": 1}).keys())),
        "examples": examples,
        "edge_cases": feature.get("edge_case_terms", []),
        "invariants": feature.get("reasoning_terms", []),
    }


def plan_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "algorithm": "Implement the function directly from the prompt and validate against public examples.",
        "cases": spec.get("edge_cases", []),
        "complexity": "Prefer linear scans or direct Python built-ins unless the prompt implies nested structure.",
        "implementation_notes": ["Return only the completion body.", "Do not use hidden tests or gold code."],
    }


def generated_tests_from_prompt(instance: dict[str, Any]) -> list[str]:
    tests: list[str] = []
    try:
        tree = ast.parse(instance["prompt"])
    except SyntaxError:
        return tests
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == instance["entry_point"]:
            doc = ast.get_docstring(node) or ""
            for example in doctest.DocTestParser().get_examples(doc):
                want = example.want.strip()
                if not want:
                    continue
                try:
                    expected = ast.literal_eval(want)
                except Exception:
                    if want in {"True", "False"}:
                        expected = want == "True"
                    else:
                        continue
                source = example.source.strip()
                tests.append(f"assert ({source}) == {expected!r}")
    return tests


def route_from_feature(feature: dict[str, Any]) -> dict[str, Any]:
    difficulty = feature.get("difficulty", "medium")
    if difficulty == "easy":
        return {
            "difficulty": "easy",
            "path": ["understand_spec", "implement", "run_tests"],
            "repair_rounds": 0,
            "model_tier": "cheap_fast",
        }
    if difficulty == "hard":
        return {
            "difficulty": "hard",
            "path": ["understand_spec", "plan", "generate_tests", "implement", "run_tests", "repair"],
            "repair_rounds": 2,
            "model_tier": "mid",
        }
    return {
        "difficulty": "medium",
        "path": ["understand_spec", "plan", "implement", "run_tests", "repair"],
        "repair_rounds": 1,
        "model_tier": "cheap_fast",
    }


def _trace(
    *,
    run_id: str,
    task_id: str,
    node_id: str,
    node_type: str,
    model_tier: str,
    started: float,
    state: dict[str, Any],
    oracle: dict[str, Any] | None,
    terminal_pass: bool | None = None,
    verifier_calls: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    calls: int = 0,
    wall_ms_override: int | None = None,
) -> dict[str, Any]:
    wall_ms = int(wall_ms_override if wall_ms_override is not None else (time.perf_counter() - started) * 1000)
    return {
        "run_id": run_id,
        "task_id": task_id,
        "node_id": node_id,
        "node_type": node_type,
        "model_tier": model_tier,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "calls": calls,
        "wall_ms": wall_ms,
        "verifier_calls": verifier_calls,
        "T_k": tokens_in + tokens_out + verifier_calls + wall_ms / 1000.0,
        "oracle_passed": None if oracle is None else bool(oracle.get("passed")),
        "oracle": oracle,
        "terminal_pass": terminal_pass,
        "state": state,
    }


def _node_usage(record: dict[str, Any], node_id: str) -> dict[str, Any]:
    usage = record.get("node_usage", {})
    if not isinstance(usage, dict):
        return {}
    node_usage = usage.get(node_id, {})
    return node_usage if isinstance(node_usage, dict) else {}


def _usage_trace_kwargs(record: dict[str, Any], node_id: str, *, default_calls: int) -> dict[str, Any]:
    usage = _node_usage(record, node_id)
    tokens_in = int(usage.get("tokens_in") or usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    tokens_out = int(usage.get("tokens_out") or usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or 0)
    if total_tokens and not (tokens_in or tokens_out):
        tokens_in = total_tokens
    return {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "calls": int(usage.get("calls") or default_calls),
        "wall_ms_override": int(usage["wall_ms"]) if "wall_ms" in usage else None,
    }


def run_baseline_instance(
    *,
    instance: dict[str, Any],
    verifier_test: str,
    node_record: dict[str, Any],
    run_id: str,
) -> tuple[bool, list[dict[str, Any]]]:
    assert_public_solving_instance(instance, context="run_baseline_instance")
    started = time.perf_counter()
    completion = completion_from_record(node_record, prefer_repair=False)
    terminal = run_terminal_verifier(verifier_instance_from_public(instance, verifier_test), completion)
    trace = _trace(
        run_id=run_id,
        task_id=instance["task_id"],
        node_id="single_agent_baseline",
        node_type="llm",
        model_tier="cheap_fast",
        started=started,
        state={"completion_chars": len(completion)},
        oracle=None,
        terminal_pass=terminal.passed,
        verifier_calls=1,
        **_usage_trace_kwargs(node_record, "implement", default_calls=1),
    )
    trace["sandbox"] = terminal.payload
    return terminal.passed, [trace]


def run_orchestration_instance(
    *,
    instance: dict[str, Any],
    verifier_test: str,
    profile_feature: dict[str, Any],
    node_record: dict[str, Any],
    run_id: str,
) -> tuple[bool, list[dict[str, Any]]]:
    assert_public_solving_instance(instance, context="run_orchestration_instance")
    traces: list[dict[str, Any]] = []

    started = time.perf_counter()
    route = route_from_feature(profile_feature)
    route_oracle = check_route(instance, {"route_decision": route})
    traces.append(
        _trace(
            run_id=run_id,
            task_id=instance["task_id"],
            node_id="route",
            node_type="code",
            model_tier="deterministic",
            started=started,
            state={"route_decision": route},
            oracle=route_oracle,
        )
    )

    started = time.perf_counter()
    spec = node_record["understand_spec"]
    spec_oracle = check_understand_spec(instance, {"spec_struct": spec})
    traces.append(
        _trace(
            run_id=run_id,
            task_id=instance["task_id"],
            node_id="understand_spec",
            node_type="llm",
            model_tier=route["model_tier"],
            started=started,
            state={"spec_struct": spec},
            oracle=spec_oracle,
            **_usage_trace_kwargs(node_record, "understand_spec", default_calls=1),
        )
    )

    plan = {}
    if "plan" in route["path"]:
        started = time.perf_counter()
        plan = node_record["plan"]
        traces.append(
            _trace(
                run_id=run_id,
                task_id=instance["task_id"],
                node_id="plan",
                node_type="llm",
                model_tier=route["model_tier"],
                started=started,
                state={"plan_struct": plan},
                oracle={"passed": None, "kind": "rubric", "reason": "not_scored_in_smoke"},
                **_usage_trace_kwargs(node_record, "plan", default_calls=1),
            )
        )

    tests: list[str] = []
    implementation = node_record["implement"]
    completion = completion_from_record(node_record, prefer_repair=False)
    if "generate_tests" in route["path"]:
        started = time.perf_counter()
        generated_payload = node_record["generate_tests"]
        tests = list(generated_payload.get("tests", [])) if isinstance(generated_payload, dict) else []
        test_oracle = check_generate_tests(
            instance,
            {"test_suite": {"tests": tests}, "candidate_completion": completion},
        )
        traces.append(
            _trace(
                run_id=run_id,
                task_id=instance["task_id"],
                node_id="generate_tests",
                node_type="llm",
                model_tier=route["model_tier"],
                started=started,
                state={"test_suite": {"tests": tests}},
                oracle=test_oracle,
                **_usage_trace_kwargs(node_record, "generate_tests", default_calls=1),
            )
        )

    started = time.perf_counter()
    implement_oracle = check_implement(instance, {"candidate_completion": completion})
    traces.append(
        _trace(
            run_id=run_id,
            task_id=instance["task_id"],
            node_id="implement",
            node_type="llm",
            model_tier=route["model_tier"],
            started=started,
            state={"candidate_completion": completion, "notes": implementation.get("notes", "")},
            oracle=implement_oracle,
            **_usage_trace_kwargs(node_record, "implement", default_calls=1),
        )
    )

    started = time.perf_counter()
    public_result = run_public_examples(instance, completion)
    generated_result = run_generated_tests(instance, completion, tests) if tests else None
    terminal_result = run_terminal_verifier(verifier_instance_from_public(instance, verifier_test), completion)
    traces.append(
        _trace(
            run_id=run_id,
            task_id=instance["task_id"],
            node_id="run_tests",
            node_type="code",
            model_tier="deterministic",
            started=started,
            state={
                "public_examples_pass": public_result.passed,
                "generated_tests_pass": None if generated_result is None else generated_result.passed,
                "terminal_pass": terminal_result.passed,
            },
            oracle=None,
            terminal_pass=terminal_result.passed,
            verifier_calls=1,
        )
    )

    final_terminal_result = terminal_result
    repaired_completion = completion
    if (not terminal_result.passed) and "repair" in route["path"]:
        started = time.perf_counter()
        repair_payload = node_record["repair"]
        if isinstance(repair_payload, dict) and isinstance(repair_payload.get("completion"), str):
            repaired_completion = repair_payload["completion"]
        repair_oracle = check_repair(
            instance,
            {"candidate_completion": repaired_completion, "test_suite": {"tests": tests}},
        )
        traces.append(
            _trace(
                run_id=run_id,
                task_id=instance["task_id"],
                node_id="repair",
                node_type="llm",
                model_tier=route["model_tier"],
                started=started,
                state={
                    "candidate_completion": repaired_completion,
                    "repair_summary": repair_payload.get("repair_summary", ""),
                },
                oracle=repair_oracle,
                **_usage_trace_kwargs(node_record, "repair", default_calls=1),
            )
        )
        started = time.perf_counter()
        repair_public_result = run_public_examples(instance, repaired_completion)
        repair_generated_result = run_generated_tests(instance, repaired_completion, tests) if tests else None
        final_terminal_result = run_terminal_verifier(verifier_instance_from_public(instance, verifier_test), repaired_completion)
        traces.append(
            _trace(
                run_id=run_id,
                task_id=instance["task_id"],
                node_id="run_tests",
                node_type="code",
                model_tier="deterministic",
                started=started,
                state={
                    "public_examples_pass": repair_public_result.passed,
                    "generated_tests_pass": None if repair_generated_result is None else repair_generated_result.passed,
                    "terminal_pass": final_terminal_result.passed,
                    "after_repair": True,
                },
                oracle=None,
                terminal_pass=final_terminal_result.passed,
                verifier_calls=1,
            )
        )

    started = time.perf_counter()
    traces.append(
        _trace(
            run_id=run_id,
            task_id=instance["task_id"],
            node_id="aggregate",
            node_type="code",
            model_tier="deterministic",
            started=started,
            state={
                "selected_completion_chars": len(repaired_completion),
                "selection_reason": "repair" if repaired_completion != completion else "implement",
            },
            oracle=None,
            terminal_pass=final_terminal_result.passed,
        )
    )
    return final_terminal_result.passed, traces
