"""Validate per-node HumanEval handoff records before runner execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runners.workflow import MODEL_NODE_IDS, load_node_record_map, validate_node_record_coverage
from runners.common import DATA_DIR, read_jsonl


ALWAYS_DISTINCT_HANDOFF_KEYS = (
    "spec_struct",
    "plan_struct",
    "test_suite",
    "completion",
)


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def validate_records(records: dict[str, dict[str, Any]], instances: list[dict[str, Any]]) -> dict[str, Any]:
    validate_node_record_coverage(
        instances=instances,
        records=records,
        record_jsonl="<loaded>",
        allow_mock=False,
    )
    failures: list[str] = []
    for task_id, record in sorted(records.items()):
        handoffs = {key: _stable(record[key]) for key in ALWAYS_DISTINCT_HANDOFF_KEYS}
        unique_count = len(set(handoffs.values()))
        if unique_count != len(handoffs):
            failures.append(f"{task_id}:core_handoff_states_not_distinct:{unique_count}")
        repair_unchanged = record["completion"] == record["repaired_completion"]
        if repair_unchanged and record.get("repair_status") != "unchanged_candidate_passed_self_tests":
            failures.append(f"{task_id}:unchanged_repair_without_pass_status")
        if not repair_unchanged and _stable(record["repaired_completion"]) in set(handoffs.values()):
            failures.append(f"{task_id}:repair_handoff_not_distinct")
        usage = record.get("node_usage", {})
        for node_id in MODEL_NODE_IDS:
            node_usage = usage.get(node_id)
            if not isinstance(node_usage, dict):
                failures.append(f"{task_id}:{node_id}:missing_usage")
                continue
            calls = int(node_usage.get("calls") or 0)
            wall_ms = int(node_usage.get("wall_ms") or 0)
            prompt_tokens = int(node_usage.get("prompt_tokens") or 0)
            completion_tokens = int(node_usage.get("completion_tokens") or 0)
            total_tokens = int(node_usage.get("total_tokens") or 0)
            if calls <= 0:
                failures.append(f"{task_id}:{node_id}:calls_not_positive")
            if wall_ms <= 0:
                failures.append(f"{task_id}:{node_id}:wall_ms_not_positive")
            if prompt_tokens + completion_tokens <= 0 and total_tokens <= 0:
                failures.append(f"{task_id}:{node_id}:tokens_not_positive")
    if failures:
        raise SystemExit("Per-node record validation failed:\n" + "\n".join(failures[:50]))
    return {
        "records": len(records),
        "instances": len(instances),
        "validated_nodes": list(MODEL_NODE_IDS),
        "status": "passed",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True)
    parser.add_argument("--instances", default=str(DATA_DIR / "humaneval_public.jsonl"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    records = load_node_record_map(args.records)
    instances = read_jsonl(Path(args.instances), limit=args.limit)
    result = validate_records(records, instances)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
