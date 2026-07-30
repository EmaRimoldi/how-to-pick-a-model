#!/usr/bin/env python3
"""Audit frozen SAI-3 confirmation artifacts before statistical analysis."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def audit_run(
    run_dir: Path,
    *,
    tasks_sha256: str,
    designs_by_sha256: dict[str, dict[str, dict[str, Any]]],
    all_generation_seeds: set[int],
) -> dict[str, Any]:
    metadata_path = run_dir / "run_metadata.json"
    trajectories_path = run_dir / "trajectories.jsonl"
    slots_path = run_dir / "slots.jsonl"
    for path in (metadata_path, trajectories_path, slots_path):
        require(path.is_file(), f"missing run artifact: {path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    model = str(metadata["model"])
    provenance = metadata["provenance"]
    design_sha256 = str(provenance["design_sha256"])
    require(design_sha256 in designs_by_sha256, f"unrecognized design hash in {run_dir}")
    require(provenance["tasks_sha256"] == tasks_sha256, f"task hash mismatch in {run_dir}")
    design = designs_by_sha256[design_sha256]

    trajectories: dict[str, dict[str, Any]] = {}
    wrong_shard_successes = 0
    for row in read_jsonl(trajectories_path):
        trajectory_id = str(row["trajectory_id"])
        require(trajectory_id not in trajectories, f"duplicate trajectory in {run_dir}: {trajectory_id}")
        require(trajectory_id in design, f"trajectory absent from design in {run_dir}: {trajectory_id}")
        require(row["model"] == model, f"trajectory model mismatch in {run_dir}")
        expected = design[trajectory_id]
        for field in ("task_id", "task_stratum", "mode", "condition", "schedule_seed"):
            require(row[field] == expected[field], f"design field {field} mismatch for {trajectory_id}")
        require(row["q"] == expected["q"], f"allocation mismatch for {trajectory_id}")
        success = bool(row["success"])
        censored = bool(row["censored"])
        total_slots = int(row["total_slots"])
        issued = [int(value) for value in row["issued"]]
        require(success != censored, f"invalid success/censor state for {trajectory_id}")
        require(0 < total_slots <= int(metadata["max_slots"]), f"invalid slot total for {trajectory_id}")
        require(sum(issued) == total_slots, f"issued slot mismatch for {trajectory_id}")
        if success and int(row["winning_shard"]) != int(row["mode"]):
            wrong_shard_successes += 1
        trajectories[trajectory_id] = row

    require(len(trajectories) == len(design), f"trajectory count does not match design in {run_dir}")
    require(len(trajectories) == int(metadata["trajectories"]), f"metadata trajectory mismatch in {run_dir}")
    require(set(trajectories) == set(design), f"run does not exactly cover its design in {run_dir}")
    require(
        sum(bool(row["success"]) for row in trajectories.values())
        == int(metadata["successful_trajectories"]),
        f"metadata success mismatch in {run_dir}",
    )
    require(
        sum(bool(row["censored"]) for row in trajectories.values())
        == int(metadata["censored_trajectories"]),
        f"metadata censor mismatch in {run_dir}",
    )

    slot_masks: dict[str, int] = collections.defaultdict(int)
    passing_slots: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    slot_rows = 0
    decoded_tokens = 0
    for row in read_jsonl(slots_path):
        require(row["model"] == model, f"slot model mismatch in {run_dir}")
        trajectory_id = str(row["trajectory_id"])
        require(trajectory_id in trajectories, f"orphan slot in {run_dir}: {trajectory_id}")
        slot = int(row["slot"])
        total_slots = int(trajectories[trajectory_id]["total_slots"])
        require(0 <= slot < total_slots, f"slot index out of range for {trajectory_id}")
        bit = 1 << slot
        require(not slot_masks[trajectory_id] & bit, f"duplicate physical slot for {trajectory_id}:{slot}")
        slot_masks[trajectory_id] |= bit
        seed = int(row["seed"])
        require(seed not in all_generation_seeds, f"duplicate generation seed: {seed}")
        all_generation_seeds.add(seed)
        if bool(row["verification"]["passed"]):
            passing_slots[trajectory_id].append((slot, int(row["shard"])))
        slot_rows += 1
        decoded_tokens += int(row["decoded_tokens"])

    expected_slot_rows = 0
    for trajectory_id, row in trajectories.items():
        total_slots = int(row["total_slots"])
        expected_slot_rows += total_slots
        require(
            slot_masks[trajectory_id] == (1 << total_slots) - 1,
            f"noncontiguous slots for {trajectory_id}",
        )
        passes = passing_slots.get(trajectory_id, [])
        if bool(row["success"]):
            require(passes == [(total_slots - 1, int(row["winning_shard"]))], f"invalid terminal success for {trajectory_id}")
        else:
            require(not passes, f"censored trajectory contains a passing slot: {trajectory_id}")

    require(slot_rows == expected_slot_rows, f"slot count mismatch in {run_dir}")
    require(slot_rows == int(metadata["generation_slots"]), f"metadata slot mismatch in {run_dir}")
    require(decoded_tokens == int(metadata["decoded_tokens"]), f"decoded token mismatch in {run_dir}")
    return {
        "run_dir": str(run_dir),
        "model": model,
        "design_sha256": design_sha256,
        "trajectories": len(trajectories),
        "successful_trajectories": sum(bool(row["success"]) for row in trajectories.values()),
        "censored_trajectories": sum(bool(row["censored"]) for row in trajectories.values()),
        "generation_slots": slot_rows,
        "decoded_tokens": decoded_tokens,
        "wrong_shard_successes": wrong_shard_successes,
        "gpu": metadata["gpu"],
        "model_revision": provenance["model_revision"],
        "tokenizer_sha256": provenance["tokenizer_sha256"],
        "code_git_commit": provenance["code_git_commit"],
        "package_versions": provenance["package_versions"],
        "slurm_job_id": provenance["slurm_job_id"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--design", type=Path, nargs="+", required=True)
    parser.add_argument("--run-dir", type=Path, nargs="+", required=True)
    parser.add_argument("--expected-model", action="append", default=[])
    parser.add_argument("--expected-max-slots", type=int, default=256)
    parser.add_argument("--expected-gpu-substring", default="A100")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    tasks_sha256 = sha256_path(args.tasks)
    designs_by_sha256: dict[str, dict[str, dict[str, Any]]] = {}
    all_design_ids: set[str] = set()
    all_schedule_seeds: set[int] = set()
    for path in args.design:
        rows = list(read_jsonl(path))
        design = {str(row["trajectory_id"]): row for row in rows}
        require(len(design) == len(rows), f"duplicate trajectory ids in design {path}")
        require(not all_design_ids.intersection(design), f"overlapping design shards at {path}")
        all_design_ids.update(design)
        seeds = {int(row["schedule_seed"]) for row in rows}
        require(len(seeds) == len(rows), f"duplicate schedule seeds in design {path}")
        require(not all_schedule_seeds.intersection(seeds), f"schedule seed collision at {path}")
        all_schedule_seeds.update(seeds)
        designs_by_sha256[sha256_path(path)] = design

    all_generation_seeds: set[int] = set()
    run_summaries = [
        audit_run(
            run_dir,
            tasks_sha256=tasks_sha256,
            designs_by_sha256=designs_by_sha256,
            all_generation_seeds=all_generation_seeds,
        )
        for run_dir in args.run_dir
    ]
    by_model: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for summary in run_summaries:
        by_model[summary["model"]].append(summary)
    if args.expected_model:
        require(set(by_model) == set(args.expected_model), "observed models do not match expected models")
    for model, summaries in by_model.items():
        require(sum(item["trajectories"] for item in summaries) == len(all_design_ids), f"incomplete design for {model}")
        require({item["design_sha256"] for item in summaries} == set(designs_by_sha256), f"missing design shard for {model}")
        require(len({item["model_revision"] for item in summaries}) == 1, f"model revision changed for {model}")
        require(len({item["tokenizer_sha256"] for item in summaries}) == 1, f"tokenizer changed for {model}")
        require(
            all(args.expected_gpu_substring in item["gpu"] for item in summaries),
            f"unexpected GPU for {model}",
        )
    require(
        all(int(json.loads((run_dir / "run_metadata.json").read_text())["max_slots"]) == args.expected_max_slots for run_dir in args.run_dir),
        "unexpected maximum slot limit",
    )

    result = {
        "schema_version": 1,
        "audit": "sai3_frozen_confirmation_integrity",
        "status": "PASS",
        "tasks": {"path": str(args.tasks), "sha256": tasks_sha256},
        "design_files": [
            {"path": str(path), "sha256": sha256_path(path)} for path in args.design
        ],
        "design_trajectories_per_model": len(all_design_ids),
        "unique_schedule_seeds": len(all_schedule_seeds),
        "unique_generation_seeds": len(all_generation_seeds),
        "models": {
            model: {
                "runs": len(summaries),
                "trajectories": sum(item["trajectories"] for item in summaries),
                "generation_slots": sum(item["generation_slots"] for item in summaries),
                "decoded_tokens": sum(item["decoded_tokens"] for item in summaries),
                "wrong_shard_successes": sum(item["wrong_shard_successes"] for item in summaries),
            }
            for model, summaries in sorted(by_model.items())
        },
        "runs": run_summaries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
