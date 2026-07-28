"""Write a leakage-safe stratified HumanEval subset for mini-smoke runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runners.common import DATA_DIR, PROFILE_DIR, read_json, read_jsonl, write_jsonl


def _task_num(task_id: str) -> int:
    return int(task_id.rsplit("/", 1)[-1])


def select_task_ids(profile: dict[str, Any], *, limit: int) -> list[str]:
    by_difficulty: dict[str, list[str]] = {"easy": [], "medium": [], "hard": []}
    for row in profile["features"]:
        difficulty = str(row["difficulty"])
        if difficulty in by_difficulty:
            by_difficulty[difficulty].append(str(row["task_id"]))
    for values in by_difficulty.values():
        values.sort(key=_task_num)
    quotas = {"easy": limit // 3, "medium": limit // 3, "hard": limit // 3}
    for difficulty in ("easy", "medium", "hard")[: limit % 3]:
        quotas[difficulty] += 1
    selected: list[str] = []
    for difficulty in ("easy", "medium", "hard"):
        selected.extend(by_difficulty[difficulty][: quotas[difficulty]])
    if len(selected) < limit:
        used = set(selected)
        leftovers = sorted(
            [row["task_id"] for row in profile["features"] if row["task_id"] not in used],
            key=_task_num,
        )
        selected.extend(leftovers[: limit - len(selected)])
    return selected[:limit]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=9)
    parser.add_argument("--profile", default=str(PROFILE_DIR / "task_profile.json"))
    parser.add_argument("--public-instances", default=str(DATA_DIR / "humaneval_public.jsonl"))
    parser.add_argument("--verifier-instances", default=str(DATA_DIR / "humaneval_verifier.jsonl"))
    parser.add_argument("--public-output", default=str(DATA_DIR / "humaneval_public_smoke_stratified.jsonl"))
    parser.add_argument("--verifier-output", default=str(DATA_DIR / "humaneval_verifier_smoke_stratified.jsonl"))
    parser.add_argument("--ids-output", default=str(DATA_DIR / "humaneval_smoke_stratified_ids.json"))
    args = parser.parse_args(argv)

    profile = read_json(Path(args.profile))
    task_ids = select_task_ids(profile, limit=args.limit)
    task_id_set = set(task_ids)
    public_rows = [row for row in read_jsonl(Path(args.public_instances)) if row["task_id"] in task_id_set]
    verifier_rows = [row for row in read_jsonl(Path(args.verifier_instances)) if row["task_id"] in task_id_set]
    public_rows.sort(key=lambda row: task_ids.index(row["task_id"]))
    verifier_rows.sort(key=lambda row: task_ids.index(row["task_id"]))
    write_jsonl(Path(args.public_output), public_rows)
    write_jsonl(Path(args.verifier_output), verifier_rows)
    Path(args.ids_output).write_text(json.dumps({"task_ids": task_ids}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "task_ids": task_ids,
                "public_output": args.public_output,
                "verifier_output": args.verifier_output,
                "ids_output": args.ids_output,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

