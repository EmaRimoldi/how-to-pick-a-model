from __future__ import annotations

from pathlib import Path

from vao.taxonomy import MODES
from vao.workspaces import create_step_branches, promote_branch_to_parent, sha256_file


def test_branch_workspace_parent_hashes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    parent = run_dir / "workspace" / "solution.py"
    parent.parent.mkdir(parents=True)
    parent.write_text("class CandidateQueryEngine:\n    pass\n", encoding="utf-8")
    branches = create_step_branches(run_dir, 0, parent, MODES)
    parent_hash = sha256_file(parent)
    assert set(branches) == set(MODES)
    for branch_dir in branches.values():
        assert sha256_file(branch_dir / "parent_solution.py") == parent_hash
        assert sha256_file(branch_dir / "proposed_solution.py") == parent_hash


def test_promote_branch_to_parent(tmp_path: Path) -> None:
    branch_solution = tmp_path / "branch.py"
    workspace_solution = tmp_path / "workspace" / "solution.py"
    branch_solution.write_text("x = 1\n", encoding="utf-8")
    promote_branch_to_parent(branch_solution, workspace_solution)
    assert workspace_solution.read_text(encoding="utf-8") == "x = 1\n"
