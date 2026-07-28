"""Phase B: leakage-safe HumanEval prompt profiling.

This runner reads HumanEval prompts, extracts observable features, and builds
distribution-level difficulty clusters. It does not solve instances and does
not use ``canonical_solution`` for any feature.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tqdm import tqdm

from runners.common import (
    DATA_DIR,
    PROFILE_DIR,
    ensure_step1_dirs,
    load_humaneval,
    public_instance,
    verifier_instance,
    write_json,
    write_jsonl,
)


EXAMPLE_RE = re.compile(r"^\s*>>>\s*(?P<expr>.+?)\s*$", re.MULTILINE)
EDGE_KEYWORDS = {
    "empty",
    "none",
    "negative",
    "zero",
    "duplicate",
    "sorted",
    "case",
    "large",
    "small",
    "edge",
    "corner",
}
REASONING_KEYWORDS = {
    "if",
    "only if",
    "return true",
    "prime",
    "palindrome",
    "subsequence",
    "substring",
    "permutation",
    "sorted",
    "monotonic",
    "matrix",
    "graph",
}


def _safe_literal_type(value: str) -> str:
    try:
        parsed = ast.literal_eval(value)
    except Exception:
        lowered = value.strip().lower()
        if lowered in {"true", "false"}:
            return "bool"
        if lowered in {"none", "null"}:
            return "none"
        if re.fullmatch(r"-?\d+", value.strip()):
            return "int"
        if re.fullmatch(r"-?\d+\.\d+", value.strip()):
            return "float"
        return "unknown"
    if isinstance(parsed, bool):
        return "bool"
    if isinstance(parsed, int):
        return "int"
    if isinstance(parsed, float):
        return "float"
    if isinstance(parsed, str):
        return "str"
    if isinstance(parsed, list):
        return "list"
    if isinstance(parsed, tuple):
        return "tuple"
    if isinstance(parsed, dict):
        return "dict"
    if parsed is None:
        return "none"
    return type(parsed).__name__


def _split_call_args(expr: str, entry_point: str) -> list[str]:
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return []
    body = tree.body
    if isinstance(body, ast.Compare):
        call = body.left
    else:
        call = body
    if not isinstance(call, ast.Call):
        return []
    if not isinstance(call.func, ast.Name) or call.func.id != entry_point:
        return []
    return [ast.unparse(arg) for arg in call.args]


def _example_return_type(expr: str) -> str:
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return "unknown"
    body = tree.body
    if isinstance(body, ast.Compare) and body.comparators:
        return _safe_literal_type(ast.unparse(body.comparators[-1]))
    return "unknown"


def _signature(prompt: str) -> dict[str, Any]:
    try:
        tree = ast.parse(prompt)
    except SyntaxError:
        return {"name": None, "args": []}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return {"name": node.name, "args": [arg.arg for arg in node.args.args]}
    return {"name": None, "args": []}


def extract_features(row: dict[str, Any]) -> dict[str, Any]:
    prompt = row["prompt"]
    entry_point = row["entry_point"]
    examples = EXAMPLE_RE.findall(prompt)
    signature = _signature(prompt)
    arg_type_counter: Counter[str] = Counter()
    return_type_counter: Counter[str] = Counter()
    for expr in examples:
        for arg in _split_call_args(expr, entry_point):
            arg_type_counter[_safe_literal_type(arg)] += 1
        return_type_counter[_example_return_type(expr)] += 1
    lowered = prompt.lower()
    edge_hits = sorted(keyword for keyword in EDGE_KEYWORDS if keyword in lowered)
    reasoning_hits = sorted(keyword for keyword in REASONING_KEYWORDS if keyword in lowered)
    score = 0
    score += min(len(prompt) // 450, 3)
    score += 1 if len(signature["args"]) >= 2 else 0
    score += 1 if len(signature["args"]) >= 3 else 0
    score += 1 if len(examples) == 0 else 0
    score += 1 if edge_hits else 0
    score += 1 if len(reasoning_hits) >= 2 else 0
    score += 1 if any(kind in arg_type_counter for kind in ["list", "tuple", "dict"]) else 0
    if score <= 2:
        difficulty = "easy"
    elif score <= 4:
        difficulty = "medium"
    else:
        difficulty = "hard"
    task_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    return {
        "task_id": row["task_id"],
        "entry_point": entry_point,
        "prompt_sha256_16": task_hash,
        "signature": signature,
        "prompt_chars": len(prompt),
        "prompt_lines": len(prompt.splitlines()),
        "docstring_examples": len(examples),
        "example_arg_types": dict(sorted(arg_type_counter.items())),
        "example_return_types": dict(sorted(return_type_counter.items())),
        "edge_case_terms": edge_hits,
        "reasoning_terms": reasoning_hits,
        "difficulty_score": score,
        "difficulty": difficulty,
        "has_edge_cases": bool(edge_hits),
        "has_public_examples": bool(examples),
    }


def _cluster_summary(features: list[dict[str, Any]]) -> dict[str, Any]:
    by_difficulty: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in features:
        by_difficulty[item["difficulty"]].append(item)
    counts = {key: len(value) for key, value in sorted(by_difficulty.items())}
    prompt_lengths = [item["prompt_chars"] for item in features]
    example_counts = [item["docstring_examples"] for item in features]
    return {
        "difficulty_counts": counts,
        "difficulty_frequencies": {
            key: count / len(features) for key, count in counts.items()
        }
        if features
        else {},
        "prompt_chars": {
            "mean": statistics.fmean(prompt_lengths) if prompt_lengths else 0.0,
            "max": max(prompt_lengths, default=0),
            "min": min(prompt_lengths, default=0),
        },
        "docstring_examples": {
            "mean": statistics.fmean(example_counts) if example_counts else 0.0,
            "max": max(example_counts, default=0),
            "min": min(example_counts, default=0),
        },
    }


def _routing_calibration(features: list[dict[str, Any]]) -> dict[str, Any]:
    scores = sorted(item["difficulty_score"] for item in features)
    if not scores:
        easy_max = medium_max = 0
    else:
        easy_max = scores[min(len(scores) - 1, max(0, int(0.40 * len(scores)) - 1))]
        medium_max = scores[min(len(scores) - 1, max(0, int(0.80 * len(scores)) - 1))]
    return {
        "estimator": "prompt_feature_heuristic_lifted_to_distribution",
        "thresholds": {
            "easy_max_score": easy_max,
            "medium_max_score": medium_max,
            "hard_min_score": medium_max + 1,
        },
        "allocation": {
            "easy": {"path": ["understand_spec", "implement", "run_tests"], "repair_rounds": 0, "model_tier": "cheap_fast"},
            "medium": {"path": ["understand_spec", "plan", "implement", "run_tests", "repair"], "repair_rounds": 1, "model_tier": "cheap_fast"},
            "hard": {"path": ["understand_spec", "plan", "generate_tests", "implement", "run_tests", "repair"], "repair_rounds": 2, "model_tier": "mid"},
        },
    }


def build_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    features = [extract_features(row) for row in tqdm(rows, desc="profile", unit="task")]
    return {
        "schema_version": 1,
        "task": "humaneval",
        "source_dataset": "openai_humaneval",
        "source_split": "test",
        "sample_size": len(features),
        "leakage_policy": {
            "feature_source_fields": ["task_id", "prompt", "entry_point"],
            "canonical_solution_used": False,
            "test_used_for_profile_features": False,
            "verifier_tests_cached_separately": True,
        },
        "features": features,
        "clusters": _cluster_summary(features),
        "daao_distribution_estimator": _routing_calibration(features),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Optional smoke-test instance cap.")
    parser.add_argument("--output", default=str(PROFILE_DIR / "task_profile.json"))
    parser.add_argument("--public-data", default=str(DATA_DIR / "humaneval_public.jsonl"))
    parser.add_argument("--verifier-data", default=str(DATA_DIR / "humaneval_verifier.jsonl"))
    args = parser.parse_args(argv)

    ensure_step1_dirs()
    rows = load_humaneval(limit=args.limit)
    write_jsonl(Path(args.public_data), (public_instance(row) for row in rows))
    write_jsonl(Path(args.verifier_data), (verifier_instance(row) for row in rows))
    profile = build_profile(rows)
    write_json(Path(args.output), profile)
    print(
        json.dumps(
            {
                "output": args.output,
                "sample_size": profile["sample_size"],
                "difficulty_counts": profile["clusters"]["difficulty_counts"],
                "canonical_solution_used": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
