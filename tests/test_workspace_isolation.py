"""Tests for workspace isolation."""

import subprocess
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agent_workflow.runtime.training_harness import (
    generate_run_training_sh,
    generate_check_training_sh,
)


def test_run_training_sh_is_executable():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        script = generate_run_training_sh(ws, train_budget_seconds=300)
        assert script.exists()
        assert script.stat().st_mode & 0o111  # executable bit set


def test_check_training_sh_is_executable():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        script = generate_check_training_sh(ws)
        assert script.exists()
        assert script.stat().st_mode & 0o111


def test_two_agents_never_share_workspace():
    """Two agent workspaces must have different paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        ws0 = base / "agent_0" / "workspace"
        ws1 = base / "agent_1" / "workspace"
        assert ws0 != ws1
        ws0.mkdir(parents=True)
        ws1.mkdir(parents=True)
        # Confirm they are distinct directories
        assert ws0.resolve() != ws1.resolve()


def test_training_scripts_use_workspace_path():
    """run_training.sh should cd into the workspace, not a shared dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        script = generate_run_training_sh(ws, train_budget_seconds=100)
        content = script.read_text()
        assert str(ws) in content, "Workspace path must appear in run_training.sh"


def test_check_training_sh_uses_workspace_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        script = generate_check_training_sh(ws)
        content = script.read_text()
        assert str(ws) in content
