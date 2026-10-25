"""Canonical merge runtime and CLI for completed baseline experiments."""

from __future__ import annotations

import argparse
from importlib.resources import files
import sys
from pathlib import Path

from agent_workflow.merger import MergeOrchestrator, MergeResults


def run_merge(
    experiment_dir: str | Path,
    autoresearch_dir: str | Path,
    source_mode: str = "parallel",
    agent_based: bool = True,
    agent_model: str = "claude-opus-4-6",
    evaluation_workspace: str | Path | None = None,
) -> MergeResults:
    """Run the canonical merge pipeline on a completed experiment."""
    merger = MergeOrchestrator(
        experiment_dir=Path(experiment_dir),
        autoresearch_dir=Path(autoresearch_dir),
        mode=source_mode,
    )
    return merger.run(
        evaluation_workspace=Path(evaluation_workspace) if evaluation_workspace is not None else None,
        agent_based=agent_based,
        agent_model=agent_model,
    )


__all__ = ["run_merge", "main"]


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
        help="Path to autoresearch/ dir. Defaults to the installed autoresearch package.",
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

    experiment_dir = Path(args.experiment_dir).expanduser().resolve()

    if not experiment_dir.exists():
        print(f"[merge] Error: experiment directory not found: {experiment_dir}", file=sys.stderr)
        sys.exit(1)

    autoresearch_dir = (
        Path(args.autoresearch_dir).resolve()
        if args.autoresearch_dir
        else Path(str(files("autoresearch")))
    )

    agent_based = not args.deterministic
    print(f"[merge] Experiment:      {experiment_dir}")
    print(f"[merge] Source mode:     {args.source_mode}")
    print(f"[merge] Autoresearch:    {autoresearch_dir}")
    print(f"[merge] Run evaluation:  always")
    print(f"[merge] Merge mode:      {'deterministic' if args.deterministic else 'agent-based'}")
    if agent_based:
        print(f"[merge] Agent model:     {args.agent_model}")

    evaluation_workspace = (
        Path(args.evaluation_workspace).expanduser().resolve()
        if args.evaluation_workspace
        else None
    )
    results = run_merge(
        experiment_dir=experiment_dir,
        autoresearch_dir=autoresearch_dir,
        source_mode=args.source_mode,
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
