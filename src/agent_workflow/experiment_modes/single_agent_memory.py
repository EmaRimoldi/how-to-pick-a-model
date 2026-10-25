"""Single agent with external memory (d10 in the 2x2 design)."""

from __future__ import annotations

from pathlib import Path

from agent_workflow.config import ExperimentConfig
from agent_workflow.experiment_modes.single_agent_double_budget import (
    run_single_long_experiment,
)


def run_single_agent_memory(
    config: ExperimentConfig,
    experiment_dir: Path,
    repo_root: Path,
    system_prompt: str,
    first_message_prompt: str,
):
    """Run a single agent with external memory enabled."""
    assert len(config.agents) == 1, f"Single-memory mode expects 1 agent, got {len(config.agents)}"
    config.mode = "single_memory"
    config.agents[0].use_external_memory = True
    return run_single_long_experiment(
        config=config,
        experiment_dir=experiment_dir,
        repo_root=repo_root,
        system_prompt=system_prompt,
        first_message_prompt=first_message_prompt,
    )
