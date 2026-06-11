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
from runners.workflow import default_completion, load_completion_map, run_baseline_instance, run_orchestration_instance


def _feature_map(profile: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(row["task_id"]): row for row in profile["features"]}  # type: ignore[index]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", default=str(DATA_DIR / "humaneval_verifier.jsonl"))
    parser.add_argument("--profile", default=str(PROFILE_DIR / "task_profile.json"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--completion-jsonl", default=None, help="Rows with task_id and completion from cheap node agents.")
    parser.add_argument("--orchestration-output", default=str(LOGS_DIR / "online_loop_traces.jsonl"))
    parser.add_argument("--baseline-output", default=str(LOGS_DIR / "baseline_traces.jsonl"))
    args = parser.parse_args(argv)

    ensure_step1_dirs()
    rows = read_jsonl(Path(args.instances), limit=args.limit)
    profile = read_json(Path(args.profile))
    features = _feature_map(profile)
    completions = load_completion_map(args.completion_jsonl)

    orchestration_traces = []
    baseline_traces = []
    orchestration_successes = 0
    baseline_successes = 0
    for index, instance in enumerate(tqdm(rows, desc="online_loop", unit="task")):
        completion = completions.get(instance["task_id"], default_completion())
        source = "completion_jsonl" if instance["task_id"] in completions else "mock_default"

        baseline_passed, baseline_instance_traces = run_baseline_instance(
            instance=instance,
            completion=completion,
            run_id=f"baseline_{index:03d}_{instance['task_id'].replace('/', '_')}",
        )
        baseline_successes += int(baseline_passed)
        for trace in baseline_instance_traces:
            trace["phase"] = "F_single_agent_baseline"
            trace["completion_source"] = source
        baseline_traces.extend(baseline_instance_traces)

        orch_passed, orch_instance_traces = run_orchestration_instance(
            instance=instance,
            profile_feature=features[instance["task_id"]],
            completion=completion,
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
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

