#!/usr/bin/env python3
"""Generate and audit a frozen SAI-3 task split."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE))

from sai3 import audit_task, generate_tasks, write_jsonl  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--split", choices=("development", "calibration", "confirmation"), required=True)
    parser.add_argument("--tasks-per-mode", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--deterministic-reruns", type=int, default=20)
    args = parser.parse_args()

    tasks = generate_tasks(args.seed, args.split, args.tasks_per_mode)
    audits = [audit_task(task, args.deterministic_reruns) for task in tasks]
    if not all(audit["gate_passed"] for audit in audits):
        failed = [audit["task_id"] for audit in audits if not audit["gate_passed"]]
        raise SystemExit(f"verifier gate failed for {failed[:10]}")

    write_jsonl(args.output, tasks)
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": 1,
        "seed": args.seed,
        "split": args.split,
        "tasks": len(tasks),
        "tasks_per_mode": args.tasks_per_mode,
        "all_gates_passed": True,
        "minimum_mutation_score": min(audit["mutation_score"] for audit in audits),
        "wrong_reference_acceptances": sum(audit["wrong_reference_acceptances"] for audit in audits),
        "audits": audits,
    }
    args.audit_output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "audits"}, indent=2))


if __name__ == "__main__":
    main()
