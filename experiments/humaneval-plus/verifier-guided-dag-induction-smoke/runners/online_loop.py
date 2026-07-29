"""Phases D-E-F live orchestration runner for HumanEval.

This runner writes raw node traces only. Metrics and plots are computed later by
``metrics.compute_step1`` so reports can be regenerated without rerunning.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tqdm import tqdm

from runners.common import DATA_DIR, LOGS_DIR, PROFILE_DIR, ensure_step1_dirs, read_json, read_jsonl, write_jsonl
from runners.workflow import (
    assert_public_solving_instance,
    default_node_record,
    load_node_record_map,
    run_baseline_instance,
    run_orchestration_instance,
    validate_node_record_coverage,
)


def _feature_map(profile: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(row["task_id"]): row for row in profile["features"]}  # type: ignore[index]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", default=str(DATA_DIR / "humaneval_public.jsonl"))
    parser.add_argument("--verifier-instances", default=str(DATA_DIR / "humaneval_verifier.jsonl"))
    parser.add_argument("--profile", default=str(PROFILE_DIR / "task_profile.json"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--completion-jsonl", default=None, help="Rows with task_id and per-node fields from cheap node agents.")
    parser.add_argument("--allow-mock", action="store_true", help="Allow missing completions to use the mock default. Dev only.")
    parser.add_argument("--orchestration-output", default=str(LOGS_DIR / "online_loop_traces.jsonl"))
    parser.add_argument("--baseline-output", default=str(LOGS_DIR / "baseline_traces.jsonl"))
    args = parser.parse_args(argv)

    ensure_step1_dirs()
    rows = read_jsonl(Path(args.instances), limit=args.limit)
    for row in rows:
        assert_public_solving_instance(row, context="online_loop input")
    verifier_rows = read_jsonl(Path(args.verifier_instances))
    verifier_tests = {str(row["task_id"]): str(row["test"]) for row in verifier_rows}
    profile = read_json(Path(args.profile))
    features = _feature_map(profile)
    records = load_node_record_map(args.completion_jsonl)
    validate_node_record_coverage(
        instances=rows,
        records=records,
        record_jsonl=args.completion_jsonl,
        allow_mock=args.allow_mock,
    )

    orchestration_traces = []
    baseline_traces = []
    orchestration_successes = 0
    baseline_successes = 0
    mock_default_count = 0
    for index, instance in enumerate(tqdm(rows, desc="online_loop", unit="task")):
        if instance["task_id"] in records:
            node_record = records[instance["task_id"]]
            source = "completion_jsonl"
        else:
            node_record = default_node_record(instance["task_id"])
            source = "mock_default"
            mock_default_count += 1
        if instance["task_id"] not in verifier_tests:
            raise KeyError(f"Missing verifier test for task_id {instance['task_id']!r}")

        baseline_passed, baseline_instance_traces = run_baseline_instance(
            instance=instance,
            verifier_test=verifier_tests[instance["task_id"]],
            node_record=node_record,
            run_id=f"baseline_{index:03d}_{instance['task_id'].replace('/', '_')}",
        )
        baseline_successes += int(baseline_passed)
        for trace in baseline_instance_traces:
            trace["phase"] = "F_single_agent_baseline"
            trace["completion_source"] = source
        baseline_traces.extend(baseline_instance_traces)

        orch_passed, orch_instance_traces = run_orchestration_instance(
            instance=instance,
            verifier_test=verifier_tests[instance["task_id"]],
            profile_feature=features[instance["task_id"]],
            node_record=node_record,
            run_id=f"online_{index:03d}_{instance['task_id'].replace('/', '_')}",
        )
        orchestration_successes += int(orch_passed)
        for trace in orch_instance_traces:
            trace["phase"] = "D_E_online_loop"
            trace["completion_source"] = source
        orchestration_traces.extend(orch_instance_traces)
        print(
            json.dumps(
                {
                    "task_id": instance["task_id"],
                    "orchestration_passed": orch_passed,
                    "baseline_passed": baseline_passed,
                    "running_orchestration_successes": orchestration_successes,
                    "running_baseline_successes": baseline_successes,
                },
                sort_keys=True,
            )
        )

    if mock_default_count and not args.allow_mock:
        raise RuntimeError(f"mock_default completion_source appeared {mock_default_count} times")
    write_jsonl(Path(args.orchestration_output), orchestration_traces)
    write_jsonl(Path(args.baseline_output), baseline_traces)
    print(
        json.dumps(
            {
                "orchestration_output": args.orchestration_output,
                "baseline_output": args.baseline_output,
                "instances": len(rows),
                "orchestration_successes": orchestration_successes,
                "baseline_successes": baseline_successes,
                "mock_default_count": mock_default_count,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
