"""Phase D1 seed-solve runner.

The real seed run should use a strong model through an operator-provided
completion JSONL or backend. The default mock path is for <=3 instance smoke
tests only and does not claim solving performance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tqdm import tqdm

from runners.common import DATA_DIR, LOGS_DIR, ensure_step1_dirs, read_jsonl, write_jsonl
from runners.workflow import (
    assert_public_solving_instance,
    default_node_record,
    load_node_record_map,
    run_baseline_instance,
    validate_node_record_coverage,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", default=str(DATA_DIR / "humaneval_public.jsonl"))
    parser.add_argument("--verifier-instances", default=str(DATA_DIR / "humaneval_verifier.jsonl"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--completion-jsonl", default=None, help="Rows with task_id and per-node fields from a strong seed solver.")
    parser.add_argument("--allow-mock", action="store_true", help="Allow missing completions to use the mock default. Dev only.")
    parser.add_argument("--output", default=str(LOGS_DIR / "seed_solve_traces.jsonl"))
    args = parser.parse_args(argv)

    ensure_step1_dirs()
    rows = read_jsonl(Path(args.instances), limit=args.limit)
    for row in rows:
        assert_public_solving_instance(row, context="seed_solve input")
    verifier_rows = read_jsonl(Path(args.verifier_instances))
    verifier_tests = {str(row["task_id"]): str(row["test"]) for row in verifier_rows}
    records = load_node_record_map(args.completion_jsonl)
    validate_node_record_coverage(
        instances=rows,
        records=records,
        record_jsonl=args.completion_jsonl,
        allow_mock=args.allow_mock,
    )
    traces = []
    successes = 0
    mock_default_count = 0
    for index, instance in enumerate(tqdm(rows, desc="seed_solve", unit="task")):
        if instance["task_id"] in records:
            node_record = records[instance["task_id"]]
            source = "completion_jsonl"
        else:
            node_record = default_node_record(instance["task_id"])
            source = "mock_default"
            mock_default_count += 1
        if instance["task_id"] not in verifier_tests:
            raise KeyError(f"Missing verifier test for task_id {instance['task_id']!r}")
        passed, instance_traces = run_baseline_instance(
            instance=instance,
            verifier_test=verifier_tests[instance["task_id"]],
            node_record=node_record,
            run_id=f"seed_{index:03d}_{instance['task_id'].replace('/', '_')}",
        )
        successes += int(passed)
        for trace in instance_traces:
            trace["phase"] = "D1_seed_solve"
            trace["completion_source"] = source
        traces.extend(instance_traces)
        print(json.dumps({"task_id": instance["task_id"], "passed": passed, "running_successes": successes}))
    if mock_default_count and not args.allow_mock:
        raise RuntimeError(f"mock_default completion_source appeared {mock_default_count} times")
    write_jsonl(Path(args.output), traces)
    print(
        json.dumps(
            {
                "output": args.output,
                "instances": len(rows),
                "successes": successes,
                "mock_default_count": mock_default_count,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
