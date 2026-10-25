"""Canonical merge mode wrapper."""

from __future__ import annotations

from pathlib import Path

from agent_workflow.merger import MergeOrchestrator, MergeResults


def run_merge(
    experiment_dir: str | Path,
    autoresearch_dir: str | Path,
    source_mode: str = "parallel",
    agent_based: bool = True,
    agent_model: str = "claude-opus-4-6",
) -> MergeResults:
    """Run the canonical merge pipeline on a completed experiment."""
    merger = MergeOrchestrator(
        experiment_dir=Path(experiment_dir),
        autoresearch_dir=Path(autoresearch_dir),
        mode=source_mode,
    )
    return merger.run(
        agent_based=agent_based,
        agent_model=agent_model,
    )


__all__ = ["run_merge"]
