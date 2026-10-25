from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.dataset import load_config, load_dataset
from src.run_strategy_router import MODE_ORDER, balanced_examples, normalized_allocation
from src.run_strategy_router_codex import MODEL_KEYS, DISPLAY_MODE, run_codex, schema


def frozen_split(modes: dict[str, str], path: Path, seed: int) -> dict[str, list[str]]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    rng = np.random.default_rng(seed)
    result = {"train": [], "validation": [], "test": []}
    for mode in MODE_ORDER:
        task_ids = np.asarray(sorted(task_id for task_id, value in modes.items() if value == mode))
        rng.shuffle(task_ids)
        n = len(task_ids)
        train_end = n // 2
        validation_end = train_end + (n - train_end) // 2
        result["train"].extend(task_ids[:train_end].tolist())
        result["validation"].extend(task_ids[train_end:validation_end].tolist())
        result["test"].extend(task_ids[validation_end:].tolist())
    result = {key: sorted(values) for key, values in result.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def make_prompt(
    *,
    examples: list[tuple[str, dict[str, Any], str]],
    tasks: list[tuple[str, dict[str, Any]]],
    budget: int,
) -> str:
    examples_payload = [
        {"task_id": task_id, "task": problem["prompt"], "label": DISPLAY_MODE[mode]}
        for task_id, problem, mode in examples
    ]
    tasks_payload = [{"task_id": task_id, "task": problem["prompt"]} for task_id, problem in tasks]
    return f"""Act as a calibrated router for verified Python program-synthesis tasks.

Infer the operational mode label of every held-out task from the training examples. Return a
probability distribution over mode1, mode2, and mode3. Separately allocate exactly {budget}
sequential retries for each Qwen2.5-Coder model across mode1_direct, mode2_structured, and
mode3_robust. Allocations must be nonnegative integers summing to {budget}. The probability
distribution and retry allocation are distinct outputs. Return every task_id exactly once and
only the JSON required by the schema.

Training examples:
{json.dumps(examples_payload, separators=(",", ":"))}

Held-out tasks:
{json.dumps(tasks_payload, separators=(",", ":"))}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run leakage-free router validation or test search")
    parser.add_argument("--config", default="experiments/humaneval-plus/strategy-by-difficulty-grid/configs/strategy_experiment.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--router-model", choices=("gpt-5.4", "gpt-5.5"), required=True)
    parser.add_argument("--context-examples", type=int, choices=(0, 5, 20), required=True)
    parser.add_argument("--phase", choices=("validation", "test"), required=True)
    parser.add_argument("--reasoning-effort", default="high")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(args.config)
    config["paths"]["derived"] = str(output_dir / "dataset")
    bundle = load_dataset(config)
    split = frozen_split(bundle.modes, output_dir / "split.json", int(config["router"]["seed"]) + 101)
    train_ids = split["train"]
    heldout_ids = split[args.phase]
    example_ids = balanced_examples(
        train_ids,
        bundle.modes,
        args.context_examples,
        int(config["router"]["seed"]) + args.context_examples,
    )
    budget = int(config["allocation"]["retry_budget"])
    prompt = make_prompt(
        examples=[(task_id, bundle.problems[task_id], bundle.modes[task_id]) for task_id in example_ids],
        tasks=[(task_id, bundle.problems[task_id]) for task_id in heldout_ids],
        budget=budget,
    )
    schema_path = output_dir / "router_search_schema.json"
    schema_path.write_text(json.dumps(schema(), indent=2) + "\n", encoding="utf-8")
    value, elapsed, tokens = run_codex(
        prompt,
        schema_path,
        model=args.router_model,
        reasoning_effort=args.reasoning_effort,
    )
    decisions = {str(item["task_id"]): item for item in value["decisions"]}
    if set(decisions) != set(heldout_ids):
        raise ValueError(
            f"Router output mismatch: missing={sorted(set(heldout_ids) - set(decisions))}, "
            f"extra={sorted(set(decisions) - set(heldout_ids))}"
        )
    strategies = list(config["strategies"])
    rows = []
    for task_id in heldout_ids:
        decision = decisions[task_id]
        raw = np.asarray([decision["p_mode1"], decision["p_mode2"], decision["p_mode3"]], dtype=float)
        if np.any(raw < 0) or not np.all(np.isfinite(raw)) or raw.sum() <= 0:
            raise ValueError(f"Invalid posterior for {task_id}: {raw}")
        raw /= raw.sum()
        for model_key in MODEL_KEYS:
            allocation = normalized_allocation(decision["allocations"][model_key], budget, strategies)
            rows.append(
                {
                    "schema_version": 1,
                    "search_run_id": args.run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "phase": args.phase,
                    "task_id": task_id,
                    "true_mode": bundle.modes[task_id],
                    "router_model": args.router_model,
                    "reasoning_effort": args.reasoning_effort,
                    "context_examples": args.context_examples,
                    "example_task_ids": example_ids,
                    "model_key": model_key,
                    "posterior_raw": {mode: float(raw[idx]) for idx, mode in enumerate(MODE_ORDER)},
                    "allocation": {strategy: allocation[idx] for idx, strategy in enumerate(strategies)},
                    "budget": budget,
                    "batch_wall_seconds": elapsed,
                    "batch_codex_tokens": tokens,
                }
            )
    output = output_dir / f"{args.phase}_{args.router_model}_n{args.context_examples}.jsonl"
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"Wrote {output}: {len(rows)} rows, {elapsed:.1f}s")


if __name__ == "__main__":
    main()
