"""Swarm mode: N agents coordinated through a shared JSONL blackboard."""

from __future__ import annotations

from pathlib import Path

from agent_workflow.config import ExperimentConfig
from agent_workflow.swarm import SWARM_MODE
from agent_workflow.swarm.swarm_config import SwarmConfig
from agent_workflow.swarm.swarm_orchestrator import (
    SwarmOrchestrator,
)
from agent_workflow.outputs.collector import collect_experiment
from agent_workflow.outputs.reporter import write_experiment_report


def run_swarm_experiment(
    config: ExperimentConfig,
    experiment_dir: Path,
    repo_root: Path,
    system_prompt: str,
    first_message_prompt: str,
    swarm_config: SwarmConfig | None = None,
):
    """Run the swarm logic without replacing native 2x2 modes."""
    config.mode = SWARM_MODE
    if swarm_config is None:
        swarm_config = SwarmConfig()
    assert len(config.agents) >= 1, (
        f"Swarm mode expects at least 1 agent, got {len(config.agents)}"
    )

    orchestrator = SwarmOrchestrator(
        config=config,
        repo_root=repo_root,
        swarm_config=swarm_config,
    )
    orchestrator.run_swarm(
        experiment_dir=experiment_dir,
        system_prompt=system_prompt,
        first_message_prompt=first_message_prompt,
    )

    agent_ids = [a.agent_id for a in config.agents]
    summary = collect_experiment(
        experiment_dir=experiment_dir,
        experiment_id=config.experiment_id,
        mode=SWARM_MODE,
        agent_ids=agent_ids,
    )

    mode_dir = experiment_dir / f"mode_{SWARM_MODE}"
    write_experiment_report(summary, mode_dir)
    return summary
