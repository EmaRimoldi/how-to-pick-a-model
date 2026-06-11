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
from runners.workflow import default_completion, load_completion_map, run_baseline_instance


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", default=str(DATA_DIR / "humaneval_verifier.jsonl"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--completion-jsonl", default=None, help="Rows with task_id and completion from a strong seed solver.")
    parser.add_argument("--output", default=str(LOGS_DIR / "seed_solve_traces.jsonl"))
    args = parser.parse_args(argv)

    ensure_step1_dirs()
    rows = read_jsonl(Path(args.instances), limit=args.limit)
    completions = load_completion_map(args.completion_jsonl)
    traces = []
    successes = 0
    for index, instance in enumerate(tqdm(rows, desc="seed_solve", unit="task")):
        completion = completions.get(instance["task_id"], default_completion())
        passed, instance_traces = run_baseline_instance(
            instance=instance,
            completion=completion,
            run_id=f"seed_{index:03d}_{instance['task_id'].replace('/', '_')}",
        )
        successes += int(passed)
        for trace in instance_traces:
            trace["phase"] = "D1_seed_solve"
            trace["completion_source"] = "completion_jsonl" if instance["task_id"] in completions else "mock_default"
        traces.extend(instance_traces)
        print(json.dumps({"task_id": instance["task_id"], "passed": passed, "running_successes": successes}))
    write_jsonl(Path(args.output), traces)
    print(json.dumps({"output": args.output, "instances": len(rows), "successes": successes}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

