"""Parallel agents with shared memory (d11 in the 2x2 design)."""

from __future__ import annotations

from pathlib import Path

from agent_workflow.config import ExperimentConfig
from agent_workflow.experiment_modes.parallel_two_agents import (
    run_parallel_experiment,
)


def run_parallel_shared_memory(
    config: ExperimentConfig,
    experiment_dir: Path,
    repo_root: Path,
    system_prompt: str,
    first_message_prompt: str,
):
    """Run parallel agents with shared memory enabled."""
    config.mode = "parallel_shared"
    for agent in config.agents:
        agent.use_shared_memory = True
    return run_parallel_experiment(
        config=config,
        experiment_dir=experiment_dir,
        repo_root=repo_root,
        system_prompt=system_prompt,
        first_message_prompt=first_message_prompt,
    )
