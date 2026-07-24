"""Mode 1: N fully independent agents × T budget."""

from __future__ import annotations

from pathlib import Path

from agent_workflow.config import ExperimentConfig
from agent_workflow.orchestrator import Orchestrator
from agent_workflow.outputs.collector import collect_experiment
from agent_workflow.outputs.reporter import write_experiment_report


def run_parallel_experiment(
    config: ExperimentConfig,
    experiment_dir: Path,
    repo_root: Path,
    system_prompt: str,
    first_message_prompt: str,
) -> None:
    """Run Mode 1: N agents x T budget.

    Agents are:
    - Fully independent (no shared context, workspace, or files)
    - Launched simultaneously
    - All given the same time budget T
    - Results collected only AFTER all finish

    Total compute = N×T. Wall-clock time ≈ T.
    """
    assert config.mode in {"parallel", "parallel_shared"}, (
        f"Expected mode=parallel or parallel_shared, got {config.mode}"
    )
    assert len(config.agents) >= 1, f"Parallel mode expects at least 1 agent, got {len(config.agents)}"

    orchestrator = Orchestrator(config=config, repo_root=repo_root)
    orchestrator.run_parallel(
        experiment_dir=experiment_dir,
        system_prompt=system_prompt,
        first_message_prompt=first_message_prompt,
    )

    # Collect after all agents finish
    agent_ids = [a.agent_id for a in config.agents]
    summary = collect_experiment(
        experiment_dir=experiment_dir,
        experiment_id=config.experiment_id,
        mode=config.mode,
        agent_ids=agent_ids,
    )

    mode_dir = experiment_dir / f"mode_{config.mode}"
    write_experiment_report(summary, mode_dir)

    return summary
