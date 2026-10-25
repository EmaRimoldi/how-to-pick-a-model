from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.dataset import load_config, load_dataset
from src.run_router_experiment import ensure_folds
from src.run_strategy_router import MODE_ORDER, balanced_examples, normalized_allocation


DISPLAY_MODE = {"easy": "mode1", "medium": "mode2", "hard": "mode3"}
MODEL_KEYS = ("1.5b", "7b", "32b")


def stable_seed(base: int, *parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return (base + int.from_bytes(digest[:4], "big")) % (2**31 - 1)


def schema() -> dict[str, Any]:
    allocation = {
        "type": "object",
        "properties": {
            "n_mode1_direct": {"type": "integer", "minimum": 0},
            "n_mode2_structured": {"type": "integer", "minimum": 0},
            "n_mode3_robust": {"type": "integer", "minimum": 0},
        },
        "required": ["n_mode1_direct", "n_mode2_structured", "n_mode3_robust"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "p_mode1": {"type": "number", "minimum": 0},
                        "p_mode2": {"type": "number", "minimum": 0},
                        "p_mode3": {"type": "number", "minimum": 0},
                        "allocations": {
                            "type": "object",
                            "properties": {key: allocation for key in MODEL_KEYS},
                            "required": list(MODEL_KEYS),
                            "additionalProperties": False,
                        },
                    },
                    "required": [
                        "task_id",
                        "p_mode1",
                        "p_mode2",
                        "p_mode3",
                        "allocations",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["decisions"],
        "additionalProperties": False,
    }


def make_prompt(
    *,
    examples: list[tuple[str, dict[str, Any], str]],
    tasks: list[tuple[str, dict[str, Any]]],
    budget: int,
) -> str:
    example_payload = [
        {
            "task_id": task_id,
            "task": problem["prompt"],
            "label": DISPLAY_MODE[mode],
        }
        for task_id, problem, mode in examples
    ]
    task_payload = [
        {"task_id": task_id, "task": problem["prompt"]}
        for task_id, problem in tasks
    ]
    return f"""Act as a calibrated router for verified Python program-synthesis tasks.

Infer the mode label of every held-out task from the labeled cross-fit examples. The labels mode1,
mode2, and mode3 are operational labels; do not assume access to a hidden test label. Return a
probability distribution over the three labels for each task. Also allocate exactly {budget} retries
for each model across these strategies:
- mode1_direct: shortest direct construction;
- mode2_structured: specification, invariants, boundary cases, then implementation;
- mode3_robust: decomposition and adversarial edge-case analysis.

Allocate retries independently for Qwen2.5-Coder 1.5B, 7B, and 32B. Every allocation must use
nonnegative integers summing exactly to {budget}. Return every task_id exactly once and only the JSON
required by the output schema. Probabilities must be nonnegative and sum to one.

Cross-fit examples:
{json.dumps(example_payload, separators=(",", ":"))}

Held-out tasks:
{json.dumps(task_payload, separators=(",", ":"))}
"""


def run_codex(
    prompt: str,
    schema_path: Path,
    attempts: int = 3,
    *,
    model: str = "gpt-5.4",
    reasoning_effort: str = "high",
) -> tuple[dict[str, Any], float, int | None]:
    last_error = ""
    for attempt in range(1, attempts + 1):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
            output_path = Path(handle.name)
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "-m",
            model,
            "-c",
            f'model_reasoning_effort="{reasoning_effort}"',
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "-C",
            "/tmp",
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            "-",
        ]
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=1800,
        )
        elapsed = time.perf_counter() - started
        try:
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr[-4000:])
            value = json.loads(output_path.read_text(encoding="utf-8"))
            token_match = re.search(r"tokens used\s+([\d,]+)", completed.stderr)
            tokens = int(token_match.group(1).replace(",", "")) if token_match else None
            return value, elapsed, tokens
        except Exception as exc:
            last_error = f"attempt {attempt}: {exc}"
        finally:
            output_path.unlink(missing_ok=True)
    raise RuntimeError(f"Codex router failed after {attempts} attempts: {last_error}")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the GPT-5.4 high-reasoning cross-fit router")
    parser.add_argument("--config", default="experiments/humaneval-plus/strategy-by-difficulty-grid/configs/strategy_experiment.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--context-sizes", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(args.config)
    config["paths"]["raw"] = str(output_dir)
    config["paths"]["derived"] = str(output_dir.parent / "derived")
    bundle = load_dataset(config)
    schema_path = output_dir / "router_output_schema.json"
    schema_path.write_text(json.dumps(schema(), indent=2) + "\n", encoding="utf-8")
    output_path = output_dir / f"router_{args.run_id}.jsonl"

    router_config = config["router"]
    base_seed = int(router_config["seed"])
    context_sizes = list(router_config["context_examples"])
    if args.context_sizes:
        context_sizes = [int(value) for value in args.context_sizes.split(",")]
    budget = int(config["allocation"]["retry_budget"])
    strategies = list(config["strategies"])

    trace_stub = {
        task_id: {"anchor": {"mode": bundle.modes[task_id]}}
        for task_id in bundle.problems
    }
    folds = ensure_folds(
        trace_stub,
        path=output_dir / "strategy_folds.json",
        n_folds=int(router_config["folds"]),
        seed=base_seed,
        mode_order=list(MODE_ORDER),
    )
    completed_batches: set[tuple[int, int]] = set()
    if output_path.exists():
        rows_by_batch: dict[tuple[int, int], dict[str, set[str]]] = {}
        with output_path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                key = (int(row["fold"]), int(row["context_examples"]))
                by_task = rows_by_batch.setdefault(key, {})
                by_task.setdefault(str(row["task_id"]), set()).add(str(row["model_key"]))
        for fold in folds["folds"]:
            test_ids = set(fold["task_ids"])
            for n in context_sizes:
                by_task = rows_by_batch.get((int(fold["fold"]), n), {})
                if set(by_task) == test_ids and all(
                    models == set(MODEL_KEYS) for models in by_task.values()
                ):
                    completed_batches.add((int(fold["fold"]), n))

    all_ids = set(bundle.problems)
    for fold in folds["folds"]:
        fold_id = int(fold["fold"])
        test_ids = list(fold["task_ids"])
        train_ids = sorted(all_ids - set(test_ids))
        for n in context_sizes:
            if (fold_id, n) in completed_batches:
                continue
            seed = stable_seed(base_seed, str(fold_id), str(n))
            example_ids = balanced_examples(train_ids, bundle.modes, n, seed)
            prompt = make_prompt(
                examples=[
                    (task_id, bundle.problems[task_id], bundle.modes[task_id])
                    for task_id in example_ids
                ],
                tasks=[(task_id, bundle.problems[task_id]) for task_id in test_ids],
                budget=budget,
            )
            value, elapsed, codex_tokens = run_codex(prompt, schema_path)
            decisions = {str(item["task_id"]): item for item in value["decisions"]}
            if set(decisions) != set(test_ids):
                missing = sorted(set(test_ids) - set(decisions))
                extra = sorted(set(decisions) - set(test_ids))
                raise ValueError(f"Router batch mismatch: missing={missing}, extra={extra}")
            for task_id in test_ids:
                decision = decisions[task_id]
                raw_p = np.asarray(
                    [decision["p_mode1"], decision["p_mode2"], decision["p_mode3"]],
                    dtype=float,
                )
                if np.any(raw_p < 0) or not np.all(np.isfinite(raw_p)) or raw_p.sum() <= 0:
                    raw_p = np.ones(3, dtype=float)
                probabilities = raw_p / raw_p.sum()
                for model_key in MODEL_KEYS:
                    allocation_value = decision["allocations"][model_key]
                    allocation = normalized_allocation(allocation_value, budget, strategies)
                    append_jsonl(
                        output_path,
                        {
                            "schema_version": 2,
                            "run_id": args.run_id,
                            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            "fold": fold_id,
                            "task_id": task_id,
                            "true_mode": bundle.modes[task_id],
                            "context_examples": n,
                            "example_task_ids": example_ids,
                            "model_key": model_key,
                            "posterior_raw": {
                                mode: float(probabilities[idx])
                                for idx, mode in enumerate(MODE_ORDER)
                            },
                            "allocation": {
                                strategy: allocation[idx]
                                for idx, strategy in enumerate(strategies)
                            },
                            "budget": budget,
                            "router_model": "gpt-5.4",
                            "reasoning_effort": "high",
                            "parse_failed": False,
                            "batch_wall_seconds": elapsed,
                            "batch_codex_tokens": codex_tokens,
                        },
                    )
            print(
                f"completed fold={fold_id} context={n}: "
                f"{len(test_ids)} tasks, {elapsed:.1f}s, tokens={codex_tokens}",
                flush=True,
            )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
