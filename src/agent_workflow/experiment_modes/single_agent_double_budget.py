"""Mode 2: 1 agent × 2T budget."""

from __future__ import annotations

from pathlib import Path

from agent_workflow.config import ExperimentConfig
from agent_workflow.orchestrator import Orchestrator
from agent_workflow.outputs.collector import collect_experiment
from agent_workflow.outputs.reporter import write_experiment_report


def run_single_long_experiment(
    config: ExperimentConfig,
    experiment_dir: Path,
    repo_root: Path,
    system_prompt: str,
    first_message_prompt: str,
) -> None:
    """Run Mode 2: 1 agent × 2T budget.

    Total compute = 2T. Wall-clock time ≈ 2T.

    Direct comparison condition against Mode 1 (parallel_two_agents).
    Both modes consume the same total compute budget.
    """
    assert config.mode in {"single_long", "single_memory"}, (
        f"Expected mode=single_long or single_memory, got {config.mode}"
    )
    assert len(config.agents) == 1, f"Single-long mode expects 1 agent, got {len(config.agents)}"

    orchestrator = Orchestrator(config=config, repo_root=repo_root)
    orchestrator.run_single(
        experiment_dir=experiment_dir,
        system_prompt=system_prompt,
        first_message_prompt=first_message_prompt,
    )

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
