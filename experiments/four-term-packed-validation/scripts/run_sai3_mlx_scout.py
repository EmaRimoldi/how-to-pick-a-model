#!/usr/bin/env python3
"""Run a development-only SAI-3 scout with MLX on Apple silicon."""

from __future__ import annotations

import argparse
import importlib.metadata
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


def system_snapshot() -> dict[str, str]:
    command = [
        "system_profiler",
        "SPHardwareDataType",
        "-detailLevel",
        "mini",
    ]
    try:
        hardware = subprocess.check_output(command, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        hardware = "unavailable"
    return {
        "host": platform.node(),
        "machine": platform.machine(),
        "macos": platform.mac_ver()[0],
        "hardware": hardware,
    }


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def select_balanced_tasks(rows: list[dict[str, Any]], tasks_per_mode: int) -> list[dict[str, Any]]:
    counts = {mode: 0 for mode in range(3)}
    selected = []
    for task in rows:
        mode = int(task["mode"])
        if counts[mode] < tasks_per_mode:
            selected.append(task)
            counts[mode] += 1
    if any(count != tasks_per_mode for count in counts.values()):
        raise SystemExit(f"insufficient balanced tasks: {counts}")
    return selected


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


def make_eos_suppressor(mx: Any, eos_token_ids: list[int]) -> Any:
    def suppress_eos(_tokens: Any, logits: Any) -> Any:
        token_ids = mx.arange(logits.shape[-1])
        mask = mx.zeros(token_ids.shape, dtype=mx.bool_)
        for token_id in eos_token_ids:
            mask = mx.logical_or(mask, token_ids == token_id)
        return mx.where(mask[None, :], -mx.inf, logits)

    return suppress_eos


def run_group(
    model: Any,
    tokenizer: Any,
    mx: Any,
    stream_generate: Any,
    sampler: Any,
    logits_processors: list[Any],
    prompts: list[str],
    metadata: list[dict[str, Any]],
    attempts: int,
    seed: int,
    model_name: str,
    output: Path,
    max_tokens: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    rows = 0
    decoded_tokens = 0
    successful = 0
    with output.open("a", encoding="utf-8") as handle:
        for prompt_index, (prompt, meta) in enumerate(zip(prompts, metadata)):
            task = meta["task"]
            for attempt in range(attempts):
                completion_seed = seed + prompt_index * attempts + attempt
                mx.random.seed(completion_seed)
                completion_started = time.perf_counter()
                chunks = []
                final_response = None
                for response in stream_generate(
                    model,
                    tokenizer,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    sampler=sampler,
                    logits_processors=logits_processors,
                ):
                    chunks.append(response.text)
                    final_response = response
                completion_seconds = time.perf_counter() - completion_started
                if final_response is None:
                    raise RuntimeError("MLX returned no generation response")
                text = "".join(chunks)
                verification = verify_completion(task, text)
                successful += int(verification["passed"])
                generated = int(final_response.generation_tokens)
                row = {
                    "schema_version": 1,
                    "backend": "mlx",
                    "model": model_name,
                    "task_id": task["task_id"],
                    "mode": task["mode"],
                    "shard": meta["shard"],
                    "relation": meta["relation"],
                    "attempt": attempt,
                    "seed": completion_seed,
                    "prompt_tokens": int(final_response.prompt_tokens),
                    "decoded_tokens": generated,
                    "finish_reason": final_response.finish_reason,
                    "completion_seconds": completion_seconds,
                    "generation_tokens_per_second": float(final_response.generation_tps),
                    "peak_memory_gb": float(final_response.peak_memory),
                    "text": text,
                    "verification": verification,
                }
                handle.write(json.dumps(row, sort_keys=True) + "\n")
                rows += 1
                decoded_tokens += generated
    elapsed = time.perf_counter() - started
    return {
        "requests": len(prompts),
        "completions": rows,
        "successful_completions": successful,
        "decoded_tokens": decoded_tokens,
        "elapsed_seconds": elapsed,
        "decoded_tokens_per_second": decoded_tokens / elapsed if elapsed else None,
    }


def run_group_batched(
    model: Any,
    tokenizer: Any,
    mx: Any,
    batch_generator_type: Any,
    sampler: Any,
    prompts: list[str],
    metadata: list[dict[str, Any]],
    attempts: int,
    seed: int,
    model_name: str,
    output: Path,
    max_tokens: int,
    completion_batch_size: int,
) -> dict[str, Any]:
    expanded_prompts: list[list[int]] = []
    expanded_metadata: list[dict[str, Any]] = []
    for prompt, meta in zip(prompts, metadata):
        add_special_tokens = tokenizer.bos_token is None or not prompt.startswith(tokenizer.bos_token)
        prompt_tokens = tokenizer.encode(prompt, add_special_tokens=add_special_tokens)
        for attempt in range(attempts):
            expanded_prompts.append(prompt_tokens)
            expanded_metadata.append({**meta, "attempt": attempt})

    mx.random.seed(seed)
    prefill_batch_size = min(4, completion_batch_size)
    generator = batch_generator_type(
        model,
        stop_tokens=set(),
        sampler=sampler,
        completion_batch_size=completion_batch_size,
        prefill_batch_size=prefill_batch_size,
    )
    started = time.perf_counter()
    uids = generator.insert(expanded_prompts, max_tokens)
    token_results = {uid: [] for uid in uids}
    finish_reasons: dict[int, str] = {}
    while responses := generator.next():
        for response in responses:
            token_results[response.uid].append(response.token)
            if response.finish_reason is not None:
                finish_reasons[response.uid] = response.finish_reason
    elapsed = time.perf_counter() - started
    stats = generator.stats()

    successful = 0
    with output.open("a", encoding="utf-8") as handle:
        for sample_index, (uid, meta, prompt_tokens) in enumerate(zip(uids, expanded_metadata, expanded_prompts)):
            task = meta["task"]
            generated_tokens = token_results[uid]
            text = tokenizer.decode(generated_tokens, skip_special_tokens=True)
            verification = verify_completion(task, text)
            successful += int(verification["passed"])
            row = {
                "schema_version": 1,
                "backend": "mlx_batch",
                "model": model_name,
                "task_id": task["task_id"],
                "mode": task["mode"],
                "shard": meta["shard"],
                "relation": meta["relation"],
                "attempt": meta["attempt"],
                "seed": seed,
                "sample_index": sample_index,
                "prompt_tokens": len(prompt_tokens),
                "decoded_tokens": len(generated_tokens),
                "finish_reason": finish_reasons.get(uid),
                "completion_seconds": None,
                "generation_tokens_per_second": float(stats.generation_tps),
                "peak_memory_gb": float(stats.peak_memory),
                "text": text,
                "verification": verification,
            }
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    decoded_tokens = sum(len(tokens) for tokens in token_results.values())
    return {
        "requests": len(prompts),
        "completions": len(expanded_prompts),
        "successful_completions": successful,
        "decoded_tokens": decoded_tokens,
        "elapsed_seconds": elapsed,
        "decoded_tokens_per_second": decoded_tokens / elapsed if elapsed else None,
        "generation_tokens_per_second": float(stats.generation_tps),
        "prompt_tokens_per_second": float(stats.prompt_tps),
        "completion_batch_size": completion_batch_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--tasks-per-mode", type=int, default=2)
    parser.add_argument("--matched-attempts", type=int, default=2)
    parser.add_argument("--wrong-attempts", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--completion-batch-size", type=int, default=1)
    args = parser.parse_args()

    try:
        import mlx.core as mx
        from mlx_lm import load, stream_generate
        from mlx_lm.generate import BatchGenerator
        from mlx_lm.sample_utils import make_sampler
    except ImportError as exc:
        raise SystemExit(
            "MLX scout dependencies are missing. Run with "
            "`uv run --with mlx-lm==0.28.3 --with transformers==4.57.6 ...`."
        ) from exc

    tasks = select_balanced_tasks(read_jsonl(args.tasks), args.tasks_per_mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)

    mx.reset_peak_memory()
    model_started = time.perf_counter()
    model, tokenizer = load(args.model)
    model_load_seconds = time.perf_counter() - model_started
    eos_ids = [int(token_id) for token_id in tokenizer.eos_token_ids]
    logits_processors = [make_eos_suppressor(mx, eos_ids)]
    sampler = make_sampler(temp=0.8, top_p=0.95)

    matched_prompts, matched_metadata = render_prompts(tokenizer, tasks, "matched")
    wrong_prompts, wrong_metadata = render_prompts(tokenizer, tasks, "wrong")
    if args.completion_batch_size > 1:
        matched_summary = run_group_batched(
            model,
            tokenizer,
            mx,
            BatchGenerator,
            sampler,
            matched_prompts,
            matched_metadata,
            args.matched_attempts,
            args.seed,
            args.model,
            args.output,
            args.max_tokens,
            args.completion_batch_size,
        )
        wrong_summary = run_group_batched(
            model,
            tokenizer,
            mx,
            BatchGenerator,
            sampler,
            wrong_prompts,
            wrong_metadata,
            args.wrong_attempts,
            args.seed + 1_000_000,
            args.model,
            args.output,
            args.max_tokens,
            args.completion_batch_size,
        )
    else:
        matched_summary = run_group(
            model,
            tokenizer,
            mx,
            stream_generate,
            sampler,
            logits_processors,
            matched_prompts,
            matched_metadata,
            args.matched_attempts,
            args.seed,
            args.model,
            args.output,
            args.max_tokens,
        )
        wrong_summary = run_group(
            model,
            tokenizer,
            mx,
            stream_generate,
            sampler,
            logits_processors,
            wrong_prompts,
            wrong_metadata,
            args.wrong_attempts,
            args.seed + 1_000_000,
            args.model,
            args.output,
            args.max_tokens,
        )
    metadata = {
        "schema_version": 1,
        "evidence_status": "development_only_nonconfirmatory",
        "backend": "mlx",
        "model": args.model,
        "model_load_seconds": model_load_seconds,
        "peak_memory_gb": float(mx.get_peak_memory() / 1e9),
        "system": system_snapshot(),
        "python": platform.python_version(),
        "packages": {
            "mlx": package_version("mlx"),
            "mlx-lm": package_version("mlx-lm"),
            "transformers": package_version("transformers"),
        },
        "tasks": str(args.tasks),
        "tasks_per_mode": args.tasks_per_mode,
        "matched_attempts": args.matched_attempts,
        "wrong_attempts": args.wrong_attempts,
        "max_tokens": args.max_tokens,
        "completion_batch_size": args.completion_batch_size,
        "matched": matched_summary,
        "wrong": wrong_summary,
    }
    args.metadata_output.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
