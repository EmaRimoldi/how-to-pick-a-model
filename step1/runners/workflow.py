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
            completions[str(row["task_id"])] = str(row["completion"])
    return completions


def default_completion() -> str:
    return "    pass\n"


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
) -> dict[str, Any]:
    wall_ms = int((time.perf_counter() - started) * 1000)
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


def run_baseline_instance(
    *,
    instance: dict[str, Any],
    completion: str,
    run_id: str,
) -> tuple[bool, list[dict[str, Any]]]:
    started = time.perf_counter()
    terminal = run_terminal_verifier(instance, completion)
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
        calls=1,
    )
    trace["sandbox"] = terminal.payload
    return terminal.passed, [trace]


def run_orchestration_instance(
    *,
    instance: dict[str, Any],
    profile_feature: dict[str, Any],
    completion: str,
    run_id: str,
) -> tuple[bool, list[dict[str, Any]]]:
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
    spec = spec_from_prompt(instance, profile_feature)
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
            calls=1,
        )
    )

    plan = {}
    if "plan" in route["path"]:
        started = time.perf_counter()
        plan = plan_from_spec(spec)
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
                calls=1,
            )
        )

    tests: list[str] = []
    if "generate_tests" in route["path"]:
        started = time.perf_counter()
        tests = generated_tests_from_prompt(instance)
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
                calls=1,
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
            state={"completion_chars": len(completion)},
            oracle=implement_oracle,
            calls=1,
        )
    )

    started = time.perf_counter()
    public_result = run_public_examples(instance, completion)
    generated_result = run_generated_tests(instance, completion, tests) if tests else None
    terminal_result = run_terminal_verifier(instance, completion)
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

    repaired_completion = completion
    if (not terminal_result.passed) and "repair" in route["path"]:
        started = time.perf_counter()
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
                state={"completion_chars": len(repaired_completion), "repair_summary": "mock path preserves completion"},
                oracle=repair_oracle,
                calls=1,
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
            state={"selected_completion_chars": len(repaired_completion), "selection_reason": "only candidate"},
            oracle=None,
            terminal_pass=terminal_result.passed,
        )
    )
    return terminal_result.passed, traces

