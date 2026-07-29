from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tqdm import tqdm

from src.dataset import load_config, load_dataset
from src.execute import execute_candidate
from src.hf_models import TransformersGenerator
from src.models import build_solution
from src.strategies import make_strategy_prompt


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def stable_seed(base: int, *parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return (base + int.from_bytes(digest[:4], "big")) % (2**31 - 1)


def read_completed(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    completed: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                completed.add((str(row["strategy"]), str(row["task_id"])))
    return completed


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the mode-specialized strategy experiment")
    parser.add_argument("--config", default="experiments/humaneval-plus/strategy-by-difficulty-grid/configs/strategy_experiment.yaml")
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--strategies", default=None, help="Comma-separated strategy names")
    parser.add_argument("--limit-problems", type=int, default=None)
    parser.add_argument("--attempts", type=int, default=None)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    if args.model_key not in config["models"]:
        raise ValueError(f"Unknown model key {args.model_key!r}")
    model_id = str(config["models"][args.model_key])
    strategies = config["strategies"]
    selected = list(strategies)
    if args.strategies:
        selected = [name.strip() for name in args.strategies.split(",") if name.strip()]
    unknown = sorted(set(selected) - set(strategies))
    if unknown:
        raise ValueError(f"Unknown strategies: {unknown}")

    bundle = load_dataset(config)
    task_ids = sorted(bundle.problems)
    if args.limit_problems is not None:
        by_mode: dict[str, list[str]] = {}
        for task_id in task_ids:
            by_mode.setdefault(bundle.modes[task_id], []).append(task_id)
        task_ids = []
        while len(task_ids) < args.limit_problems and any(by_mode.values()):
            for mode in sorted(by_mode):
                if by_mode[mode] and len(task_ids) < args.limit_problems:
                    task_ids.append(by_mode[mode].pop(0))
    if args.num_shards < 1 or not 0 <= args.shard_index < args.num_shards:
        raise ValueError("Require 0 <= shard-index < num-shards")
    task_ids = task_ids[args.shard_index :: args.num_shards]

    sampling = config["sampling"]
    attempts = int(args.attempts or sampling["attempts_per_task"])
    base_seed = int(sampling["seed"])
    out_path = Path(config["paths"]["raw"]) / (
        f"strategy_{safe_name(args.model_key)}_{safe_name(args.run_id)}_shard{args.shard_index:02d}.jsonl"
    )
    completed = read_completed(out_path)
    generator = TransformersGenerator(model_id)

    work = [
        (strategy, task_id)
        for strategy in selected
        for task_id in task_ids
        if (strategy, task_id) not in completed
    ]
    for strategy, task_id in tqdm(work, desc=f"{args.model_key} strategy cells", unit="cell"):
        problem = bundle.problems[task_id]
        prompt = make_strategy_prompt(problem, str(strategies[strategy]))
        attempt_tokens: list[int] = []
        attempt_seconds: list[float] = []
        attempt_generation_seconds: list[float] = []
        attempt_verification_seconds: list[float] = []
        attempt_overhead_seconds: list[float] = []
        attempt_statuses: list[str] = []
        for attempt in range(attempts):
            seed = stable_seed(base_seed, args.model_key, strategy, task_id, str(attempt))
            attempt_started = time.perf_counter()
            generation = generator.generate(
                prompt,
                temperature=float(sampling["temperature"]),
                top_p=float(sampling["top_p"]),
                max_new_tokens=int(sampling["max_new_tokens"]),
                seed=seed,
            )
            solution = build_solution(problem, generation.text)
            verification_started = time.perf_counter()
            result = execute_candidate(
                solution=solution,
                problem=problem,
                expected_output=bundle.expected_outputs[task_id],
                timeout_seconds=float(config["execution"]["timeout_seconds"]),
                checker_dataset=bundle.checker_dataset,
            )
            verification_seconds = time.perf_counter() - verification_started
            total_seconds = time.perf_counter() - attempt_started
            attempt_tokens.append(generation.tokens_generated)
            attempt_generation_seconds.append(generation.wall_seconds)
            attempt_verification_seconds.append(verification_seconds)
            attempt_overhead_seconds.append(
                max(0.0, total_seconds - generation.wall_seconds - verification_seconds)
            )
            attempt_seconds.append(total_seconds)
            attempt_statuses.append(
                "pass" if result.passed else f"{result.base_status}/{result.plus_status}"
            )

        first_pass = next(
            (idx for idx, status in enumerate(attempt_statuses, start=1) if status == "pass"),
            None,
        )
        row = {
            "schema_version": 2,
            "run_id": args.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "dataset": bundle.dataset_name,
            "dataset_hash": bundle.dataset_hash,
            "task_id": task_id,
            "task_mode": bundle.modes[task_id],
            "model_key": args.model_key,
            "model_id": model_id,
            "strategy": strategy,
            "strategy_kind": strategies[strategy],
            "attempts_requested": attempts,
            "attempt_token_counts": attempt_tokens,
            "attempt_seconds": attempt_seconds,
            "attempt_generation_seconds": attempt_generation_seconds,
            "attempt_verification_seconds": attempt_verification_seconds,
            "attempt_overhead_seconds": attempt_overhead_seconds,
            "attempt_statuses": attempt_statuses,
            "first_pass_attempt": first_pass,
            "solved": first_pass is not None,
            "tau_tokens": (
                sum(attempt_tokens[:first_pass]) if first_pass is not None else math.inf
            ),
            "tau_seconds": (
                sum(attempt_seconds[:first_pass]) if first_pass is not None else math.inf
            ),
            "temperature": float(sampling["temperature"]),
            "top_p": float(sampling["top_p"]),
            "max_new_tokens": int(sampling["max_new_tokens"]),
            "seed_base": base_seed,
        }
        append_jsonl(out_path, row)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
