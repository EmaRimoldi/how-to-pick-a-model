"""Workspace helper for the swarm blackboard mode."""

from __future__ import annotations

import shutil
from pathlib import Path


def install_swarm_tools(
    *,
    repo_root: Path,
    workspace_path: Path,
    swarm_memory_path: Path,
) -> None:
    """Install the swarm protocol files into one agent workspace.

    The current repository's normal workspace builder creates the git-backed
    workspace and training scripts. This helper only adds the runtime
    blackboard-facing files after that setup is complete.
    """
    package_dir = Path(__file__).resolve().parent
    src_root = package_dir.parents[1]
    prompt_dir = repo_root / "prompts" / "swarm"

    coordinator_src = package_dir / "coordinator.py"
    coordinator_dst = workspace_path / "coordinator.py"
    shutil.copy2(coordinator_src, coordinator_dst)

    coordinator_local_src = package_dir / "coordinator_local.py"
    coordinator_local_dst = workspace_path / "coordinator_local.py"
    shutil.copy2(coordinator_local_src, coordinator_local_dst)

    for name in ("collab.md", "program.md"):
        src = prompt_dir / name
        if src.exists():
            shutil.copy2(src, workspace_path / name)

    env_file = workspace_path / ".swarm_env"
    env_file.write_text(
        "\n".join(
            [
                f"SWARM_MEMORY_PATH={swarm_memory_path}",
                f"AGENTOPS_LAB_SRC={src_root}",
            ]
        )
        + "\n"
    )
