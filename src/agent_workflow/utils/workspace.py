"""Workspace creation and teardown for isolated agent workspaces."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from agent_workflow.runtime.training_harness import (
    generate_check_training_sh,
    generate_run_on_worker_sh,
    generate_run_training_sh,
    generate_slurm_check_training_sh,
    generate_snapshot_helpers,
    generate_start_gpu_worker_sh,
    generate_stop_gpu_worker_sh,
    generate_submit_training_sh,
)


class WorkspaceError(Exception):
    pass


def create_workspace(
    autoresearch_dir: Path,
    workspace_path: Path,
    branch_name: str,
    train_budget_seconds: int,
    run_id: str,
    agent_id: str,
    results_root: Path,
    train_max_steps: Optional[int] = None,
    slurm_partition: str = "pi_tpoggio",
    slurm_gres: str = "gpu:1",
    slurm_time: str = "00:08:00",
    use_slurm: bool = True,
    persistent_worker: bool = True,
    agent_time_budget_minutes: int = 60,
    experiment_mode: str = "parallel",
    evaluator_lock_path: Optional[Path] = None,
) -> Path:
    """Create an isolated git-backed workspace for one agent.

    Steps:
    1. Create branch/workspace from autoresearch source
    3. Copy train.py.baseline
    4. Symlink .venv and data/
    5. Generate training scripts (SLURM: submit_training.sh + check_training.sh;
       local: run_training.sh + check_training.sh)
    6. Create results directory

    Returns workspace_path.
    """
    autoresearch_dir = autoresearch_dir.resolve()
    workspace_path = workspace_path.resolve()
    results_root = results_root.resolve()

    if _is_git_repo_root(autoresearch_dir):
        _ensure_branch(autoresearch_dir, branch_name)
        _create_worktree(autoresearch_dir, workspace_path, branch_name)
        _save_baseline(workspace_path)
        _symlink_shared(autoresearch_dir, workspace_path)
        _setup_shared_memory(workspace_path, results_root, experiment_mode)
        _override_program_md(workspace_path)
    else:
        _create_local_workspace_copy(autoresearch_dir, workspace_path)
        _override_program_md(workspace_path)
        _initialize_workspace_repo(workspace_path, branch_name)
        _save_baseline(workspace_path)
        _symlink_shared(autoresearch_dir, workspace_path)
        _setup_shared_memory(workspace_path, results_root, experiment_mode)

    if persistent_worker:
        if use_slurm:
            # Convert agent budget to HH:MM:SS, adding 10-minute safety margin
            total_minutes = agent_time_budget_minutes + 10
            worker_time = f"{total_minutes // 60:02d}:{total_minutes % 60:02d}:00"
            generate_start_gpu_worker_sh(
                workspace_path,
                agent_id=agent_id,
                results_root=results_root,
                slurm_partition=slurm_partition,
                slurm_gres=slurm_gres,
                worker_time=worker_time,
                use_slurm=True,
            )
            generate_run_on_worker_sh(
                workspace_path,
                train_budget_seconds,
                train_max_steps=train_max_steps,
                evaluator_lock_path=evaluator_lock_path,
                use_slurm=True,
            )
            generate_stop_gpu_worker_sh(workspace_path, use_slurm=True)
        else:
            generate_start_gpu_worker_sh(
                workspace_path,
                agent_id=agent_id,
                results_root=results_root,
                use_slurm=False,
            )
            generate_run_on_worker_sh(
                workspace_path,
                train_budget_seconds,
                train_max_steps=train_max_steps,
                evaluator_lock_path=evaluator_lock_path,
                use_slurm=False,
            )
            generate_stop_gpu_worker_sh(workspace_path, use_slurm=False)
    else:
        if use_slurm:
            # Legacy: one sbatch per train.py run
            generate_submit_training_sh(
                workspace_path,
                agent_id=agent_id,
                results_root=results_root,
                slurm_partition=slurm_partition,
                slurm_gres=slurm_gres,
                slurm_time=slurm_time,
            )
            generate_slurm_check_training_sh(workspace_path)
        else:
            generate_run_training_sh(workspace_path, train_budget_seconds)
            generate_check_training_sh(workspace_path)

    # Generate snapshot helper scripts (save_snapshot.py, update_snapshot.py)
    generate_snapshot_helpers(
        workspace=workspace_path,
        agent_id=agent_id,
        results_root=results_root,
    )

    # Set up per-agent output directories
    results_root.mkdir(parents=True, exist_ok=True)
    (results_root.parent / "snapshots").mkdir(parents=True, exist_ok=True)
    (results_root.parent / "reasoning").mkdir(parents=True, exist_ok=True)

    return workspace_path


def destroy_workspace(autoresearch_dir: Path, workspace_path: Path) -> None:
    """Remove a git worktree and its directory."""
    autoresearch_dir = autoresearch_dir.resolve()
    workspace_path = workspace_path.resolve()
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(workspace_path)],
            cwd=autoresearch_dir,
            check=False,
            capture_output=True,
        )
    except Exception:
        pass
    if workspace_path.exists():
        shutil.rmtree(workspace_path, ignore_errors=True)


def _ensure_branch(autoresearch_dir: Path, branch_name: str) -> None:
    result = subprocess.run(
        ["git", "show-ref", "--quiet", f"refs/heads/{branch_name}"],
        cwd=autoresearch_dir,
        capture_output=True,
    )
    if result.returncode != 0:
        subprocess.run(
            ["git", "branch", branch_name, "HEAD"],
            cwd=autoresearch_dir,
            check=True,
            capture_output=True,
        )


def _is_git_repo_root(path: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == path.resolve()


def _create_worktree(
    autoresearch_dir: Path, workspace_path: Path, branch_name: str
) -> None:
    if workspace_path.exists():
        return
    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "worktree", "add", str(workspace_path), branch_name],
        cwd=autoresearch_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise WorkspaceError(
            f"Failed to create worktree at {workspace_path}: {result.stderr}"
        )


def _create_local_workspace_copy(autoresearch_dir: Path, workspace_path: Path) -> None:
    if workspace_path.exists():
        return
    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        autoresearch_dir,
        workspace_path,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "data", ".venv"),
        dirs_exist_ok=True,
    )


def _initialize_workspace_repo(workspace_path: Path, branch_name: str) -> None:
    git_dir = workspace_path / ".git"
    if git_dir.exists():
        return

    subprocess.run(["git", "init"], cwd=workspace_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "AutoResearch Agent"],
        cwd=workspace_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "autoresearch-agent@example.com"],
        cwd=workspace_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=workspace_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=workspace_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial workspace baseline"],
        cwd=workspace_path,
        check=True,
        capture_output=True,
    )


def _override_program_md(workspace_path: Path) -> None:
    """Replace program.md with a stub that redirects to our launcher instructions.

    The original program.md instructs agents to run `uv run train.py` directly,
    which bypasses SLURM entirely. We overwrite it so agents follow the
    first_message instructions instead.
    """
    stub = """\
# DO NOT FOLLOW THESE INSTRUCTIONS

This workspace is managed by the parallel agent autoresearch framework.
Your instructions are in the first message of this session.

Follow those instructions exactly. In particular:
- DO NOT run `uv run train.py` directly.
- DO use `bash start_gpu_worker.sh` (once) and `bash run_on_worker.sh` (per iteration).
- DO NOT read or follow the original program.md workflow.
"""
    program_md = workspace_path / "program.md"
    if program_md.exists():
        program_md.write_text(stub)


def _save_baseline(workspace_path: Path) -> None:
    train_py = workspace_path / "train.py"
    baseline = workspace_path / "train.py.baseline"
    if train_py.exists() and not baseline.exists():
        shutil.copy2(train_py, baseline)


def _symlink_shared(autoresearch_dir: Path, workspace_path: Path) -> None:
    venv_src = autoresearch_dir / ".venv"
    venv_dst = workspace_path / ".venv"
    if venv_src.exists() and not venv_dst.exists():
        venv_dst.symlink_to(venv_src)

    data_src = autoresearch_dir / "data"
    data_dst = workspace_path / "data"
    if data_src.exists() and not data_dst.exists():
        data_dst.symlink_to(data_src)


def _setup_shared_memory(
    workspace_path: Path,
    results_root: Path,
    experiment_mode: str,
) -> None:
    if experiment_mode != "parallel_shared":
        return

    experiment_dir = results_root.parents[2]
    shared_log_path = experiment_dir / "shared_results_log.jsonl"
    shared_log_path.touch(exist_ok=True)

    workspace_shared_path = workspace_path / "shared_results_log.jsonl"
    if workspace_shared_path.exists() or workspace_shared_path.is_symlink():
        workspace_shared_path.unlink()
    workspace_shared_path.symlink_to(shared_log_path)
