#!/usr/bin/env python3
"""CLI: compare two experiment directories (parallel vs single)."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agent_workflow.outputs.collector import collect_experiment
from agent_workflow.outputs.reporter import write_final_comparison


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare parallel vs single-long experiment results."
    )
    parser.add_argument("parallel_dir", help="Path to parallel experiment directory")
    parser.add_argument("single_dir", help="Path to single-long experiment directory")
    parser.add_argument("--output-dir", default=None, help="Where to write comparison (default: parallel_dir)")
    args = parser.parse_args()

    parallel_dir = Path(args.parallel_dir)
    single_dir = Path(args.single_dir)
    output_dir = Path(args.output_dir) if args.output_dir else parallel_dir

    # Read config.json to find agent IDs
    def _agent_ids(exp_dir: Path, mode: str) -> list[str]:
        config_path = exp_dir / "config.json"
        if config_path.exists():
            cfg = json.loads(config_path.read_text())
            return [a["agent_id"] for a in cfg.get("agents", [])]
        mode_dir = exp_dir / f"mode_{mode}"
        if mode_dir.exists():
            return [d.name for d in sorted(mode_dir.iterdir()) if d.is_dir() and d.name != "aggregate"]
        return ["agent_0", "agent_1"]

    parallel_summary = collect_experiment(
        experiment_dir=parallel_dir,
        experiment_id=parallel_dir.name,
        mode="parallel",
        agent_ids=_agent_ids(parallel_dir, "parallel"),
    )

    single_summary = collect_experiment(
        experiment_dir=single_dir,
        experiment_id=single_dir.name,
        mode="single_long",
        agent_ids=_agent_ids(single_dir, "single_long"),
    )

    report_path = write_final_comparison(parallel_summary, single_summary, output_dir)
    print(f"Comparison report: {report_path}")
    print(f"Parallel best val_bpb: {parallel_summary.best_val_bpb()}")
    print(f"Single best val_bpb:   {single_summary.best_val_bpb()}")


if __name__ == "__main__":
    main()
