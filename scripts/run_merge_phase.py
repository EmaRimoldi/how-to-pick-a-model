#!/usr/bin/env python3
"""CLI: run the merge phase on a completed parallel experiment.

Given an experiment directory produced by run_parallel_experiment.py, this
script:
  1. Gathers all agent snapshots, reasoning traces, and metrics
  2. Selects the best and most informative train.py variants
  3. Analyses per-parameter improvement correlations
  4. Produces a merged train.py candidate
  5. Runs evaluation via SLURM (always; workspace auto-detected if not provided)
  6. Writes a merge report and comparison table

Usage:
    python scripts/run_merge_phase.py --experiment-dir runs/experiment_parallel_20260331_120000
    python scripts/run_merge_phase.py --experiment-dir runs/exp_... --source-mode parallel
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agent_workflow.merger import MergeOrchestrator


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Run merge phase on a parallel experiment.")
    parser.add_argument(
        "--experiment-dir", required=True,
        help="Path to the experiment directory (contains mode_parallel/, config.json, etc.).",
    )
    parser.add_argument(
        "--source-mode", default="parallel",
        help="Which agent mode to read from (default: parallel).",
    )
    parser.add_argument(
        "--autoresearch-dir", default=None,
        help="Path to autoresearch/ dir. Defaults to <repo_root>/autoresearch.",
    )
    parser.add_argument(
        "--evaluation-workspace", default=None,
        help="Path to a workspace dir with submit_training.sh and check_training.sh for evaluation.",
    )
    parser.add_argument(
        "--deterministic", action="store_true",
        help="Use the deterministic parameter-level merge instead of the Claude agent merge.",
    )
    parser.add_argument(
        "--agent-model", default="claude-opus-4-6",
        help="Claude model to use for agent-based merge (default: claude-opus-4-6).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).parents[1]
    experiment_dir = Path(args.experiment_dir).expanduser().resolve()

    if not experiment_dir.exists():
        print(f"[merge] Error: experiment directory not found: {experiment_dir}", file=sys.stderr)
        sys.exit(1)

    autoresearch_dir = (
        Path(args.autoresearch_dir).resolve()
        if args.autoresearch_dir
        else repo_root / "autoresearch"
    )

    agent_based = not args.deterministic
    print(f"[merge] Experiment:      {experiment_dir}")
    print(f"[merge] Source mode:     {args.source_mode}")
    print(f"[merge] Autoresearch:    {autoresearch_dir}")
    print(f"[merge] Run evaluation:  always")
    print(f"[merge] Merge mode:      {'deterministic' if args.deterministic else 'agent-based'}")
    if agent_based:
        print(f"[merge] Agent model:     {args.agent_model}")

    merger = MergeOrchestrator(
        experiment_dir=experiment_dir,
        autoresearch_dir=autoresearch_dir,
        mode=args.source_mode,
    )
    evaluation_workspace = (
        Path(args.evaluation_workspace).expanduser().resolve()
        if args.evaluation_workspace
        else None
    )
    results = merger.run(
        evaluation_workspace=evaluation_workspace,
        agent_based=agent_based,
        agent_model=args.agent_model,
    )

    print("\n=== Merge Results ===")
    print(f"  Best individual agent:  {results.best_individual_agent}")
    print(f"  Best individual val_bpb: {results.best_individual_val_bpb}")
    print(f"  Merged val_bpb:          {results.merge_val_bpb}")
    print(f"  Merge won:               {results.merge_won}")
    print(f"  Delta val_bpb:           {results.delta_val_bpb}")
    print(f"\nMerge artifacts in: {experiment_dir}/mode_merge/")

    report_path = experiment_dir / "mode_merge" / "merge_report.txt"
    if report_path.exists():
        print("\n--- Merge Report ---")
        print(report_path.read_text())


if __name__ == "__main__":
    main()
