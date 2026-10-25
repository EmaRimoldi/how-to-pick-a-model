"""Maintenance fails fast and resolves the checkout independently of caller cwd."""

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_readiness_failure_stops_checks_before_compilation_and_tests(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/maintenance"))
    import workflow

    calls = []

    def failing_readiness(args, *, cwd, check):
        calls.append(args)
        assert cwd == ROOT and check
        assert args[0] == sys.executable
        if args[1].endswith("validate_agent_readiness.py"):
            raise subprocess.CalledProcessError(7, args)

    monkeypatch.setattr(workflow.subprocess, "run", failing_readiness)
    with pytest.raises(subprocess.CalledProcessError) as failure:
        workflow.run_action("check", ROOT, tmp_path)
    assert failure.value.returncode == 7
    assert calls[-1][1].endswith("validate_agent_readiness.py")
    assert not any("compileall" in args or "pytest" in args for args in calls)


def test_cli_resolves_checkout_from_outside_and_returns_child_failure(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/maintenance"))
    import workflow

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", [str(ROOT / "scripts/maintenance/workflow.py"), "check"])

    def fail(action, root, output_root):
        assert action == "check" and root == ROOT
        assert output_root.is_absolute()
        raise subprocess.CalledProcessError(7, ["failing-check"])

    monkeypatch.setattr(workflow, "run_action", fail)
    assert workflow.main() == 7
