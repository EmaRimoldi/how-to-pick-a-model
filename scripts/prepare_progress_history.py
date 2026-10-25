"""Prepare offline-only development fixtures for the progress-history design; no API calls."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from vao.decisions.progress_history import Attempt, branch_pair, checkpoint, development_tasks, digest, verify


CONFIG = Path("experiments/finite-domain/progress-history/configs/offline-development.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Fresh directory for development fixtures only")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    if args.output is None:
        print(json.dumps({"mode": "offline_plan", "config": config,
                          "live_collection_implemented": False, "api_calls": 0}, indent=2))
        return
    tasks = development_tasks(config["seed"], config["tasks"])
    rows = []
    for task in tasks:
        reference = task.reference_expression()
        if not verify(task, reference)["passed"]:
            raise ValueError("Oracle/interpreter disagreement")
        attempts = [Attempt(candidate, 0) for candidate in config["fixture_candidates"]]
        state = checkpoint(task, attempts, config["illustrative_budget_nanousd"])
        rows.append({"kind": "handwritten_development_fixture", "split": "development",
                     "oracle_parameters_for_engineering_only": asdict(task),
                     "reference_for_engineering_only": reference,
                     "state": state, "branch_requests": branch_pair(state)})
    summary = {"status": "offline_fixtures_only", "model_responses": 0, "api_calls": 0,
               "actual_api_cost_usd": 0, "tasks": len(rows), "inputs_per_task": 256,
               "reference_checks": len(rows) * 256, "config_sha256": digest(config),
               "fixtures_sha256": digest(rows),
               "warning": "Synthetic engineering checks, not evidence for either recovery action."}
    # Atomic directory creation prevents overwriting prior fixtures or run data.
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "fixtures.json").write_text(json.dumps(rows, indent=2) + "\n")
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
