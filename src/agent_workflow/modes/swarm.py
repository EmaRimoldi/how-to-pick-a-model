"""Canonical swarm mode surface."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from agent_workflow.communication.blackboard import SharedMemory


@dataclass(frozen=True)
class SwarmModeConfig:
    shared_memory_file: str = "shared_memory.jsonl"
    sync_interval_seconds: int = 10
    max_context_entries: int = 20


def create_swarm_blackboard(
    mode_dir: str | Path,
    config: SwarmModeConfig | None = None,
) -> SharedMemory:
    """Create the shared blackboard used by swarm experiments."""
    cfg = config or SwarmModeConfig()
    path = Path(mode_dir) / cfg.shared_memory_file
    return SharedMemory(path=path, max_context_entries=cfg.max_context_entries)


def run_swarm(argv=None) -> None:
    """Run the swarm runtime from the canonical surface."""
    from agent_workflow.swarm.launcher import main_swarm

    main_swarm(argv)


def main_swarm(argv=None) -> None:
    """CLI surface for swarm blackboard workflows."""
    parser = argparse.ArgumentParser(
        prog="agent-workflow swarm",
        description="Inspect or initialize the canonical swarm blackboard.",
    )
    parser.add_argument(
        "--blackboard-dir",
        type=str,
        default=None,
        help="Create a shared-memory blackboard in this directory.",
    )
    parser.add_argument(
        "--max-context-entries",
        type=int,
        default=20,
        help="Maximum entries returned by context reads.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the integrated swarm experiment runtime.",
    )
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--time-budget", type=int, default=30)
    parser.add_argument("--train-budget", type=int, default=300)
    parser.add_argument("--n-agents", type=int, default=2)
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--runs-dir", type=str, default="runs")
    args = parser.parse_args(argv)

    if args.run:
        delegated_args = [
            "--time-budget",
            str(args.time_budget),
            "--train-budget",
            str(args.train_budget),
            "--n-agents",
            str(args.n_agents),
            "--runs-dir",
            args.runs_dir,
        ]
        if args.config is not None:
            delegated_args.extend(["--config", args.config])
        if args.experiment_id is not None:
            delegated_args.extend(["--experiment-id", args.experiment_id])
        run_swarm(delegated_args)
        return

    if args.blackboard_dir:
        sm = create_swarm_blackboard(
            args.blackboard_dir,
            SwarmModeConfig(max_context_entries=args.max_context_entries),
        )
        print(f"[swarm] Blackboard ready: {sm.path}")
        return

    print("[swarm] Blackboard primitives are integrated.")
    print("[swarm] Use --run to launch the integrated swarm runtime.")


__all__ = ["SwarmModeConfig", "create_swarm_blackboard", "run_swarm", "main_swarm"]
