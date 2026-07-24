"""Run and branch workspace helpers."""

from __future__ import annotations

import difflib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from vao.logging_utils import sha256_file, write_json
from vao.taxonomy import MODES, validate_mode


def create_run_dir(root: Path, config: dict[str, Any], run_id: str | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if run_id is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{config.get('experiment', {}).get('name', 'run')}_{stamp}"
    run_dir = root / run_id
    suffix = 1
    base = run_dir
    while run_dir.exists():
        suffix += 1
        run_dir = Path(f"{base}_{suffix:02d}")
    for child in ["workspace", "steps", "logs", "artifacts"]:
        (run_dir / child).mkdir(parents=True, exist_ok=True)
    (run_dir / "config_resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return run_dir


def init_workspace(run_dir: Path, template_path: Path) -> Path:
    workspace_solution = run_dir / "workspace" / "solution.py"
    workspace_solution.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, workspace_solution)
    return workspace_solution


def create_step_branches(run_dir: Path, step: int, parent_solution: Path, modes: list[str] | None = None) -> dict[str, Path]:
    modes = modes or MODES
    parent_hash = sha256_file(parent_solution)
    branches: dict[str, Path] = {}
    for mode in modes:
        validate_mode(mode)
        branch_dir = run_dir / "steps" / f"step_{step:04d}" / "branches" / mode
        branch_dir.mkdir(parents=True, exist_ok=True)
        parent_copy = branch_dir / "parent_solution.py"
        proposed = branch_dir / "proposed_solution.py"
        shutil.copy2(parent_solution, parent_copy)
        shutil.copy2(parent_solution, proposed)
        if sha256_file(parent_copy) != parent_hash:
            raise RuntimeError(f"Branch {mode} parent hash mismatch")
        branches[mode] = branch_dir
    manifest = {
        "step": step,
        "parent_solution": str(parent_solution),
        "parent_solution_hash": parent_hash,
        "modes": modes,
        "branches": {mode: str(path) for mode, path in branches.items()},
    }
    write_json(run_dir / "steps" / f"step_{step:04d}" / "branch_manifest.json", manifest)
    return branches


def promote_branch_to_parent(branch_solution: Path, workspace_solution: Path) -> None:
    workspace_solution.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(branch_solution, workspace_solution)


def write_diff(pre: str, post: str, out_path: Path) -> None:
    diff = difflib.unified_diff(
        pre.splitlines(),
        post.splitlines(),
        fromfile="parent_solution.py",
        tofile="proposed_solution.py",
        lineterm="",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(diff) + "\n", encoding="utf-8")
