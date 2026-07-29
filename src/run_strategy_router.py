from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from tqdm import tqdm

from src.dataset import load_config, load_dataset
from src.hf_models import TransformersGenerator
from src.run_router_experiment import ensure_folds


MODE_ORDER = ("easy", "medium", "hard")


def stable_seed(base: int, *parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return (base + int.from_bytes(digest[:4], "big")) % (2**31 - 1)


def extract_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Router output contains no JSON object")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Router output is not an object")
    return value


def normalized_probabilities(value: dict[str, Any], prior: np.ndarray) -> np.ndarray:
    raw = np.asarray([float(value.get(f"p_{mode}", 0.0)) for mode in MODE_ORDER])
    if not np.all(np.isfinite(raw)) or np.any(raw < 0) or float(np.sum(raw)) <= 0:
        return prior.copy()
    return raw / np.sum(raw)


def normalized_allocation(value: dict[str, Any], budget: int, strategies: list[str]) -> list[int]:
    raw = [max(0, int(value.get(f"n_{strategy}", 0))) for strategy in strategies]
    if sum(raw) == budget:
        return raw
    if sum(raw) <= 0:
        raw = [1] * len(strategies)
    shares = np.asarray(raw, dtype=float) / sum(raw)
    floors = np.floor(shares * budget).astype(int)
    for idx in np.argsort(-(shares * budget - floors))[: budget - int(np.sum(floors))]:
        floors[idx] += 1
    return [int(value) for value in floors]


def balanced_examples(
    train_ids: list[str],
    modes: dict[str, str],
    n: int,
    seed: int,
) -> list[str]:
    rng = np.random.default_rng(seed)
    pools = {mode: [task_id for task_id in train_ids if modes[task_id] == mode] for mode in MODE_ORDER}
    for values in pools.values():
        rng.shuffle(values)
    selected: list[str] = []
    while len(selected) < n and any(pools.values()):
        for mode in MODE_ORDER:
            if pools[mode] and len(selected) < n:
                selected.append(pools[mode].pop())
    return selected


def router_prompt(
    *,
    problem: dict[str, Any],
    examples: list[tuple[dict[str, Any], str]],
    strategies: list[str],
    budget: int,
) -> str:
    example_payload = [
        {"task": item[0]["prompt"][:900], "mode": item[1]}
        for item in examples
    ]
    keys = [f"p_{mode}" for mode in MODE_ORDER] + [f"n_{strategy}" for strategy in strategies]
    return (
        "You are a calibrated routing model for verified Python tasks. "
        "The latent modes are easy, medium, and hard. They map respectively to "
        f"the specialized strategies {strategies}. Given the examples and held-out task, "
        "return probabilities for the three modes and allocate exactly "
        f"{budget} retries across the strategies. Probabilities must be nonnegative and sum to 1. "
        f"Return only one JSON object with exactly these keys: {keys}.\n\n"
        f"Examples: {json.dumps(example_payload, separators=(',', ':'))}\n\n"
        f"Held-out task: {problem['prompt']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the posterior-and-allocation strategy router")
    parser.add_argument("--config", default="experiments/humaneval-plus/strategy-by-difficulty-grid/configs/strategy_experiment.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit-problems", type=int, default=None)
    parser.add_argument("--context-sizes", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    bundle = load_dataset(config)
    router_config = config["router"]
    base_seed = int(router_config["seed"])
    strategies = list(config["strategies"])
    budget = int(config["allocation"]["retry_budget"])
    context_sizes = list(router_config["context_examples"])
    if args.context_sizes:
        context_sizes = [int(value) for value in args.context_sizes.split(",")]
    folds_path = Path(config["paths"]["derived"]) / "strategy_folds.json"
    trace_stub = {
        task_id: {"anchor": {"mode": bundle.modes[task_id]}}
        for task_id in bundle.problems
    }
    folds = ensure_folds(
        trace_stub,
        path=folds_path,
        n_folds=int(router_config["folds"]),
        seed=base_seed,
        mode_order=list(MODE_ORDER),
    )
    prior = np.asarray([np.mean([bundle.modes[t] == mode for t in bundle.problems]) for mode in MODE_ORDER])
    generator = TransformersGenerator(str(router_config["model_id"]))
    output_path = Path(config["paths"]["raw"]) / f"router_{args.run_id}.jsonl"
    existing: set[tuple[int, int, str]] = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                existing.add((int(row["fold"]), int(row["context_examples"]), str(row["task_id"])))

    all_ids = set(bundle.problems)
    work: list[tuple[int, int, str, list[str]]] = []
    for fold in folds["folds"]:
        fold_id = int(fold["fold"])
        test_ids = list(fold["task_ids"])
        if args.limit_problems is not None:
            test_ids = test_ids[: args.limit_problems]
        train_ids = sorted(all_ids - set(fold["task_ids"]))
        for n in context_sizes:
            for task_id in test_ids:
                if (fold_id, n, task_id) not in existing:
                    work.append((fold_id, n, task_id, train_ids))

    for fold_id, n, task_id, train_ids in tqdm(work, desc="strategy router", unit="decision"):
        seed = stable_seed(base_seed, str(fold_id), str(n), task_id)
        example_ids = balanced_examples(train_ids, bundle.modes, n, seed)
        prompt = router_prompt(
            problem=bundle.problems[task_id],
            examples=[(bundle.problems[value], bundle.modes[value]) for value in example_ids],
            strategies=strategies,
            budget=budget,
        )
        generation = generator.generate(
            prompt,
            temperature=0.0,
            top_p=1.0,
            max_new_tokens=256,
            seed=seed,
        )
        parse_failed = False
        try:
            value = extract_json(generation.text)
        except Exception:
            value = {}
            parse_failed = True
        probabilities = normalized_probabilities(value, prior)
        allocation = normalized_allocation(value, budget, strategies)
        row = {
            "schema_version": 1,
            "run_id": args.run_id,
            "fold": fold_id,
            "task_id": task_id,
            "true_mode": bundle.modes[task_id],
            "context_examples": n,
            "example_task_ids": example_ids,
            "posterior_raw": {mode: float(probabilities[idx]) for idx, mode in enumerate(MODE_ORDER)},
            "allocation": {strategy: allocation[idx] for idx, strategy in enumerate(strategies)},
            "budget": budget,
            "router_model": router_config["model_id"],
            "parse_failed": parse_failed,
            "tokens_generated": generation.tokens_generated,
            "wall_seconds": generation.wall_seconds,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
