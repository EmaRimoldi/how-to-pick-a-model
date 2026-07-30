#!/usr/bin/env python3
"""Execute a physical IID soft-allocation schedule with vLLM."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE))

from sai3 import read_jsonl, verify_completion  # noqa: E402


def generation_seed(base_seed: int, model: str, trajectory_id: str, slot: int) -> int:
    payload = f"{base_seed}|{model}|{trajectory_id}|{slot}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return 1 + int.from_bytes(digest, "big") % (2**31 - 2)


def sample_shard(q: list[float], rng: random.Random) -> int:
    draw = rng.random()
    cumulative = 0.0
    for shard, share in enumerate(q):
        cumulative += share
        if draw < cumulative or shard == len(q) - 1:
            return shard
    raise AssertionError("unreachable")


def planned_counts(q: list[float], schedule_seed: int, slots: int) -> list[int]:
    rng = random.Random(schedule_seed)
    counts = [0, 0, 0]
    for _ in range(slots):
        counts[sample_shard(q, rng)] += 1
    return counts


def gpu_snapshot() -> str:
    try:
        return subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,uuid,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def render_prompt(tokenizer: Any, task: dict[str, Any], shard: int) -> str:
    messages = [
        {"role": "system", "content": "You write small, correct Python functions. Follow the requested output format exactly."},
        {"role": "user", "content": task["prompts"][shard]},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--trajectories-output", type=Path, required=True)
    parser.add_argument("--slots-output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--max-slots", type=int, default=128)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    args = parser.parse_args()

    from vllm import LLM, SamplingParams

    tasks = {task["task_id"]: task for task in read_jsonl(args.tasks)}
    design = read_jsonl(args.design)
    if len({row["trajectory_id"] for row in design}) != len(design):
        raise SystemExit("trajectory ids must be unique")
    missing = sorted({row["task_id"] for row in design} - tasks.keys())
    if missing:
        raise SystemExit(f"design references missing tasks: {missing[:3]}")
    for row in design:
        q = [float(value) for value in row["q"]]
        if len(q) != 3 or any(value < 0.0 for value in q) or not abs(sum(q) - 1.0) < 1e-8:
            raise SystemExit(f"invalid q for {row['trajectory_id']}: {q}")

    args.trajectories_output.parent.mkdir(parents=True, exist_ok=True)
    args.slots_output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.trajectories_output.unlink(missing_ok=True)
    args.slots_output.unlink(missing_ok=True)

    model_started = time.perf_counter()
    llm = LLM(
        model=args.model,
        dtype=args.dtype,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        trust_remote_code=False,
    )
    load_seconds = time.perf_counter() - model_started
    tokenizer = llm.get_tokenizer()
    prompt_cache = {
        (task_id, shard): render_prompt(tokenizer, tasks[task_id], shard)
        for task_id in {row["task_id"] for row in design}
        for shard in range(3)
    }

    states = []
    for row in design:
        states.append(
            {
                "design": row,
                "rng": random.Random(int(row["schedule_seed"])),
                "issued": [0, 0, 0],
                "slots": 0,
                "success": False,
                "winning_shard": None,
                "verification_reason": None,
            }
        )

    rounds = []
    total_started = time.perf_counter()
    with args.slots_output.open("w", encoding="utf-8") as slot_handle:
        for round_index in range(args.max_slots):
            active = [state for state in states if not state["success"] and state["slots"] < args.max_slots]
            if not active:
                break
            prompts = []
            params = []
            request_metadata = []
            for state in active:
                design_row = state["design"]
                shard = sample_shard([float(value) for value in design_row["q"]], state["rng"])
                slot = int(state["slots"])
                seed = generation_seed(args.seed, args.model, design_row["trajectory_id"], slot)
                prompts.append(prompt_cache[(design_row["task_id"], shard)])
                params.append(
                    SamplingParams(
                        temperature=0.8,
                        top_p=0.95,
                        max_tokens=args.max_tokens,
                        min_tokens=args.max_tokens,
                        ignore_eos=True,
                        n=1,
                        seed=seed,
                    )
                )
                request_metadata.append((state, shard, slot, seed))

            round_started = time.perf_counter()
            outputs = llm.generate(prompts, params, use_tqdm=True)
            round_elapsed = time.perf_counter() - round_started
            round_tokens = 0
            for request, (state, shard, slot, seed) in zip(outputs, request_metadata):
                if len(request.outputs) != 1:
                    raise RuntimeError(f"expected one output, got {len(request.outputs)}")
                completion = request.outputs[0]
                design_row = state["design"]
                verification = verify_completion(tasks[design_row["task_id"]], completion.text)
                state["issued"][shard] += 1
                state["slots"] += 1
                if verification["passed"]:
                    state["success"] = True
                    state["winning_shard"] = shard
                    state["verification_reason"] = verification["reason"]
                slot_row = {
                    "schema_version": 1,
                    "model": args.model,
                    "trajectory_id": design_row["trajectory_id"],
                    "task_id": design_row["task_id"],
                    "mode": design_row["mode"],
                    "slot": slot,
                    "shard": shard,
                    "seed": seed,
                    "prompt_tokens": len(request.prompt_token_ids),
                    "decoded_tokens": len(completion.token_ids),
                    "finish_reason": completion.finish_reason,
                    "text": completion.text,
                    "verification": verification,
                }
                slot_handle.write(json.dumps(slot_row, sort_keys=True) + "\n")
                round_tokens += len(completion.token_ids)
            rounds.append(
                {
                    "round": round_index,
                    "requests": len(prompts),
                    "decoded_tokens": round_tokens,
                    "elapsed_seconds": round_elapsed,
                }
            )

    total_elapsed = time.perf_counter() - total_started
    with args.trajectories_output.open("w", encoding="utf-8") as trajectory_handle:
        for state in states:
            design_row = state["design"]
            slots = int(state["slots"])
            q = [float(value) for value in design_row["q"]]
            planned = planned_counts(q, int(design_row["schedule_seed"]), args.max_slots)
            trajectory_row = {
                **design_row,
                "schema_version": 2,
                "model": args.model,
                "success": bool(state["success"]),
                "censored": not bool(state["success"]),
                "total_slots": slots,
                "winning_shard": state["winning_shard"],
                "verification_reason": state["verification_reason"],
                "issued": state["issued"],
                "realized_q": [count / slots if slots else 0.0 for count in state["issued"]],
                "planned_issued": planned,
                "planned_q": [count / args.max_slots for count in planned],
            }
            trajectory_handle.write(json.dumps(trajectory_row, sort_keys=True) + "\n")

    total_tokens = sum(item["decoded_tokens"] for item in rounds)
    total_requests = sum(item["requests"] for item in rounds)
    metadata = {
        "schema_version": 1,
        "model": args.model,
        "tasks": str(args.tasks),
        "design": str(args.design),
        "trajectories": len(states),
        "successful_trajectories": sum(bool(state["success"]) for state in states),
        "censored_trajectories": sum(not bool(state["success"]) for state in states),
        "generation_slots": total_requests,
        "decoded_tokens": total_tokens,
        "generation_elapsed_seconds": total_elapsed,
        "decoded_tokens_per_second": total_tokens / total_elapsed if total_elapsed else None,
        "model_load_seconds": load_seconds,
        "max_slots": args.max_slots,
        "max_tokens": args.max_tokens,
        "seed_scheme": "blake2b(base_seed|model|trajectory_id|slot)",
        "scheduler": "iid_categorical_soft_allocation",
        "host": platform.node(),
        "python": platform.python_version(),
        "gpu": gpu_snapshot(),
        "rounds": rounds,
    }
    args.metadata_output.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in metadata.items() if key != "rounds"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
