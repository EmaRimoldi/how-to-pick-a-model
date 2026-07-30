#!/usr/bin/env python3
"""Run the SAI-3 eligibility scout with vLLM offline inference."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE))

from sai3 import read_jsonl, verify_completion  # noqa: E402


def gpu_snapshot() -> str:
    command = [
        "nvidia-smi",
        "--query-gpu=name,uuid,memory.total,driver_version",
        "--format=csv,noheader",
    ]
    try:
        return subprocess.check_output(command, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def render_prompts(tokenizer: Any, tasks: list[dict[str, Any]], relation: str) -> tuple[list[str], list[dict[str, Any]]]:
    prompts: list[str] = []
    metadata: list[dict[str, Any]] = []
    for task in tasks:
        shards = [task["mode"]] if relation == "matched" else [shard for shard in range(3) if shard != task["mode"]]
        for shard in shards:
            messages = [
                {"role": "system", "content": "You write small, correct Python functions. Follow the requested output format exactly."},
                {"role": "user", "content": task["prompts"][shard]},
            ]
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            prompts.append(prompt)
            metadata.append({"task": task, "shard": shard, "relation": relation})
    return prompts, metadata


def run_group(
    llm: Any,
    sampling_params_type: Any,
    prompts: list[str],
    metadata: list[dict[str, Any]],
    attempts: int,
    seed: int,
    model: str,
    output: Path,
    max_tokens: int,
) -> dict[str, Any]:
    params = sampling_params_type(
        temperature=0.8,
        top_p=0.95,
        max_tokens=max_tokens,
        min_tokens=max_tokens,
        ignore_eos=True,
        n=attempts,
        seed=seed,
    )
    started = time.perf_counter()
    request_outputs = llm.generate(prompts, params, use_tqdm=True)
    elapsed = time.perf_counter() - started
    rows = 0
    decoded_tokens = 0
    with output.open("a", encoding="utf-8") as handle:
        for request, meta in zip(request_outputs, metadata):
            task = meta["task"]
            for attempt, completion in enumerate(request.outputs):
                verification = verify_completion(task, completion.text)
                row = {
                    "schema_version": 1,
                    "model": model,
                    "task_id": task["task_id"],
                    "mode": task["mode"],
                    "shard": meta["shard"],
                    "relation": meta["relation"],
                    "attempt": attempt,
                    "seed": seed,
                    "prompt_tokens": len(request.prompt_token_ids),
                    "decoded_tokens": len(completion.token_ids),
                    "finish_reason": completion.finish_reason,
                    "text": completion.text,
                    "verification": verification,
                }
                handle.write(json.dumps(row, sort_keys=True) + "\n")
                rows += 1
                decoded_tokens += len(completion.token_ids)
    return {
        "requests": len(prompts),
        "completions": rows,
        "decoded_tokens": decoded_tokens,
        "elapsed_seconds": elapsed,
        "decoded_tokens_per_second": decoded_tokens / elapsed if elapsed else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--tasks-per-mode", type=int, default=6)
    parser.add_argument("--matched-attempts", type=int, default=4)
    parser.add_argument("--wrong-attempts", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    from vllm import LLM, SamplingParams

    all_tasks = read_jsonl(args.tasks)
    counts = {mode: 0 for mode in range(3)}
    tasks = []
    for task in all_tasks:
        mode = int(task["mode"])
        if counts[mode] < args.tasks_per_mode:
            tasks.append(task)
            counts[mode] += 1
    if any(count != args.tasks_per_mode for count in counts.values()):
        raise SystemExit(f"insufficient balanced tasks: {counts}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)

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

    matched_prompts, matched_metadata = render_prompts(tokenizer, tasks, "matched")
    wrong_prompts, wrong_metadata = render_prompts(tokenizer, tasks, "wrong")
    matched_summary = run_group(
        llm,
        SamplingParams,
        matched_prompts,
        matched_metadata,
        args.matched_attempts,
        args.seed,
        args.model,
        args.output,
        args.max_tokens,
    )
    wrong_summary = run_group(
        llm,
        SamplingParams,
        wrong_prompts,
        wrong_metadata,
        args.wrong_attempts,
        args.seed + 1,
        args.model,
        args.output,
        args.max_tokens,
    )
    metadata = {
        "schema_version": 1,
        "model": args.model,
        "model_load_seconds": load_seconds,
        "gpu": gpu_snapshot(),
        "host": platform.node(),
        "python": platform.python_version(),
        "tasks": str(args.tasks),
        "tasks_per_mode": args.tasks_per_mode,
        "matched_attempts": args.matched_attempts,
        "wrong_attempts": args.wrong_attempts,
        "max_tokens": args.max_tokens,
        "matched": matched_summary,
        "wrong": wrong_summary,
    }
    args.metadata_output.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
