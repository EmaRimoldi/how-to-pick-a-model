"""Phase C: induce the first HumanEval DAG from the block library and profile.

The default path is deterministic and credential-free: it implements the
SELECT/ADAPT/IMPLEMENT structure from the plan using the Phase-A closed library
and Phase-B distribution profile. A future LLM-backed meta-designer can replace
the selection text, but the output schema remains the same.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from runners.common import ARTIFACT_DIR, BLOCKS_DIR, PROFILE_DIR, PROMPTS_DIR, ensure_step1_dirs, read_json, write_json


SELECTED_NODE_IDS = [
    "route",
    "understand_spec",
    "plan",
    "generate_tests",
    "implement",
    "run_tests",
    "repair",
    "aggregate",
]

SELECTED_EDGES = [
    ["route", "understand_spec"],
    ["understand_spec", "plan"],
    ["understand_spec", "implement"],
    ["plan", "generate_tests"],
    ["plan", "implement"],
    ["generate_tests", "implement"],
    ["implement", "run_tests"],
    ["run_tests", "repair"],
    ["repair", "run_tests"],
    ["run_tests", "aggregate"],
]


def _load_library(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _operator_by_id(library: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in library["operators"]}


def _role_prompt_ref(node_id: str) -> str | None:
    if node_id in {"route", "run_tests", "aggregate"}:
        return None
    return f"prompts/roles/{node_id}.txt"


def _verification_criterion(node_id: str) -> str:
    criteria = {
        "route": "route decision uses only prompt-profile features and selects an allowed path",
        "understand_spec": "signature and doctest examples are internally consistent with the prompt",
        "plan": "plan covers algorithm, cases, and implementation notes without gold access",
        "generate_tests": "generated tests execute on the produced candidate and include public examples",
        "implement": "candidate completion parses and passes public doctest examples in the sandbox",
        "run_tests": "sandboxed verifier returns structured public/generated/terminal verdicts",
        "repair": "repaired completion improves the sandboxed self-test verdict or preserves a pass",
        "aggregate": "selected completion comes from candidates that passed the deepest available verifier",
    }
    return criteria[node_id]


def _adapted_description(node_id: str) -> str:
    descriptions = {
        "route": "Deterministically map HumanEval prompt features to an easy/medium/hard path.",
        "understand_spec": "Extract a compact HumanEval spec from signature, docstring, examples, and stated edge cases.",
        "plan": "Write a short Python implementation plan that names edge cases and complexity risks.",
        "generate_tests": "Create candidate-only tests from public examples plus inferred edge cases.",
        "implement": "Produce only the function body completion needed after the HumanEval prompt.",
        "run_tests": "Run public examples, generated tests, and the terminal verifier in an isolated subprocess.",
        "repair": "Revise the completion using only sandbox failures and prompt-derived evidence.",
        "aggregate": "Select the cheapest passing candidate, preferring terminal pass over self-test pass.",
    }
    return descriptions[node_id]


def build_dag_candidate(library: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    operators = _operator_by_id(library)
    selected_nodes = []
    for node_id in SELECTED_NODE_IDS:
        operator = operators[node_id]
        selected_nodes.append(
            {
                "id": node_id,
                "type": operator["type"],
                "role": operator["role"],
                "adapted_description": _adapted_description(node_id),
                "io_contract": operator["io_contract"],
                "system_prompt_ref": _role_prompt_ref(node_id),
                "verification_criterion": _verification_criterion(node_id),
                "oracle": operator["oracle"],
                "model_tier": operator["model_tier"],
                "forbidden_signals": operator["forbidden_signals"],
                "cost_keys": operator["cost_keys"],
            }
        )
    edge_set = {tuple(edge) for edge in library["valid_edges"]}
    invalid_edges = [edge for edge in SELECTED_EDGES if tuple(edge) not in edge_set]
    if invalid_edges:
        raise ValueError(f"Selected edges are not in Phase-A library: {invalid_edges}")
    return {
        "schema_version": 1,
        "artifact_format": "meta_agent_typed_dag",
        "phase": "C",
        "task": "humaneval",
        "select": {
            "selected_blocks": SELECTED_NODE_IDS,
            "selection_reason": (
                "HumanEval needs prompt understanding, implementation, sandbox verification, "
                "conditional repair, and generated tests only for harder clusters."
            ),
            "profile_sample_size": profile["sample_size"],
            "difficulty_counts": profile["clusters"]["difficulty_counts"],
        },
        "adapt": {
            "task_specific_constraints": [
                "Never expose canonical_solution to solving nodes.",
                "Use docstring examples and generated tests only on the candidate.",
                "Run all candidate code in the sandbox.",
                "Keep per-instance node agents cheap/fast; reserve top model for design-time work.",
            ]
        },
        "implement": {
            "nodes": selected_nodes,
            "edges": SELECTED_EDGES,
            "routing_dimensions": ["difficulty", "has_edge_cases", "has_public_examples"],
            "terminal_node": "run_tests",
        },
        "cost_success": {
            "R": library["utility"]["R"],
            "c": library["utility"]["c"],
            "U": library["utility"]["U"],
            "T": library["utility"]["T"],
        },
    }


def _routing_rules(profile: dict[str, Any]) -> list[dict[str, Any]]:
    allocation = profile["daao_distribution_estimator"]["allocation"]
    return [
        {
            "if": {"difficulty": "easy"},
            "then": allocation["easy"],
            "rationale": "short path for prompts with public examples and low structural complexity",
        },
        {
            "if": {"difficulty": "medium"},
            "then": allocation["medium"],
            "rationale": "planned path plus one repair for moderate edge-case risk",
        },
        {
            "if": {"difficulty": "hard", "has_edge_cases": True},
            "then": allocation["hard"],
            "rationale": "TDAG-style conditional expansion with generated tests and two repair rounds",
        },
    ]


def _orchestration_yaml(dag: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    for node in dag["implement"]["nodes"]:
        nodes.append(
            {
                "id": node["id"],
                "type": node["type"],
                "io_contract": node["io_contract"],
                "system_prompt_ref": node["system_prompt_ref"],
                "oracle": node["oracle"],
                "model_tier": node["model_tier"],
                "verification_criterion": node["verification_criterion"],
            }
        )
    return {
        "meta": {
            "task": "humaneval",
            "description": "Prompt-only Python function synthesis with verifier-guided repair over HumanEval-164.",
            "bespoke": True,
            "meta_model": "gpt-5.5 xhigh",
            "source_plan": "swebench/step_1_induction/PLAN.md",
        },
        "roles_and_dag": {
            "nodes": nodes,
            "edges": dag["implement"]["edges"],
        },
        "routing_rules": _routing_rules(profile),
        "routing_calibration": {
            "method": "DAAO difficulty estimator lifted to HumanEval distribution clusters",
            "thresholds": profile["daao_distribution_estimator"]["thresholds"],
            "cluster_counts": profile["clusters"]["difficulty_counts"],
            "tdag_policy": {
                "expand_when": [
                    "difficulty == hard",
                    "has_edge_cases == true",
                    "public examples are missing or generated tests are needed for repair signal",
                ],
                "fixed_short_path_when": ["difficulty == easy", "public examples are present"],
                "error_propagation_control": (
                    "hard paths add generate_tests and bounded repair; easy paths skip those nodes "
                    "to avoid unnecessary cost and static-decomposition failures"
                ),
            },
        },
        "handoff_oracles": {
            node["id"]: {
                "inference": node["oracle"]["inference"]["kind"],
                "discriminates": None,
                "diagnostic": node["oracle"]["diagnostic"]["kind"],
            }
            for node in dag["implement"]["nodes"]
        },
        "cost_success": {
            "R": 1.0,
            "c": dag["cost_success"]["c"],
            "U": "R * pass - c * sum(T_k)",
            "T": "sum(T_k)",
            "criterion": "U(h) = R·1[pass] − c·T(h), T(h) = Σ T_k",
        },
        "provenance": {
            "profile_sample_size": profile["sample_size"],
            "difficulty_counts": profile["clusters"]["difficulty_counts"],
            "seed_ids": [],
            "inference_oracle_discriminating_fraction": None,
        },
    }


def write_orchestration_md(path: Path, dag: dict[str, Any], profile: dict[str, Any]) -> None:
    payload = _orchestration_yaml(dag, profile)
    body = [
        "# HumanEval Step 1 Orchestration",
        "",
        "This artifact is task-bespoke by design and is not intended to transfer unchanged to other benchmarks.",
        "Live solving nodes may use only the prompt, public docstring examples, generated tests run on the candidate, self-consistency, and the terminal verifier.",
        "`canonical_solution` is reserved for offline diagnostic oracles only.",
        "",
        "```yaml",
        yaml.safe_dump(payload, sort_keys=False).rstrip(),
        "```",
        "",
        "## Notes",
        "",
        "- The graph is a typed DAG with one bounded repair back-edge implemented as an iteration limit in the runner.",
        "- `run_tests`, `aggregate`, and `route` are deterministic code nodes.",
        "- The live utility notation is `U(h) = R·1[pass] − c·T(h)`, `T(h) = Σ T_k`.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def _write_role_prompts() -> None:
    prompts = {
        "understand_spec": "Extract HumanEval signature, examples, edge cases, invariants, and I/O hints. Do not solve the task and never request canonical_solution.",
        "plan": "Given a prompt-derived spec, write a concise implementation plan with edge cases and complexity notes. Do not include code.",
        "generate_tests": "Generate Python assertions from public examples and prompt-derived edge cases. Tests must run only on the candidate function.",
        "implement": "Return only the HumanEval completion body after the prompt. Use the spec, plan, and candidate-only tests; never use gold code.",
        "repair": "Repair the completion using sandbox failures and prompt-derived evidence only. Return a replacement completion body.",
    }
    roles_dir = PROMPTS_DIR / "roles"
    roles_dir.mkdir(parents=True, exist_ok=True)
    for name, text in prompts.items():
        (roles_dir / f"{name}.txt").write_text(text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=str(PROFILE_DIR / "task_profile.json"))
    parser.add_argument("--library", default=str(BLOCKS_DIR / "library.yaml"))
    parser.add_argument("--dag-output", default=str(ARTIFACT_DIR / "dag_candidate.json"))
    parser.add_argument("--md-output", default=str(ARTIFACT_DIR / "orchestration.md"))
    args = parser.parse_args(argv)

    ensure_step1_dirs()
    library = _load_library(Path(args.library))
    profile = read_json(Path(args.profile))
    dag = build_dag_candidate(library, profile)
    write_json(Path(args.dag_output), dag)
    write_orchestration_md(Path(args.md_output), dag, profile)
    _write_role_prompts()
    print(
        json.dumps(
            {
                "dag_output": args.dag_output,
                "md_output": args.md_output,
                "nodes": len(dag["implement"]["nodes"]),
                "edges": len(dag["implement"]["edges"]),
                "profile_sample_size": profile["sample_size"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
