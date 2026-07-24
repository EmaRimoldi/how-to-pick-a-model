"""Preflight checks for live Agent Workflow runs."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str
    required: bool = True


def _run(command: list[str], cwd: Path, timeout: int = 10) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def run_checks(repo_root: Path | None = None) -> list[CheckResult]:
    root = (repo_root or Path.cwd()).resolve()
    checks: list[CheckResult] = []

    checks.append(
        CheckResult(
            "python package",
            (root / "src" / "agent_workflow").is_dir(),
            "src/agent_workflow is present" if (root / "src" / "agent_workflow").is_dir() else "src/agent_workflow is missing",
        )
    )

    checks.append(
        CheckResult(
            "autoresearch task",
            (root / "autoresearch" / "train.py").is_file()
            and (root / "autoresearch" / "program.md").is_file(),
            "autoresearch task files are present"
            if (root / "autoresearch" / "train.py").is_file()
            and (root / "autoresearch" / "program.md").is_file()
            else "autoresearch/train.py or autoresearch/program.md is missing",
        )
    )

    checks.append(
        CheckResult(
            "default config",
            (root / "configs" / "experiment.yaml").is_file(),
            "configs/experiment.yaml is present"
            if (root / "configs" / "experiment.yaml").is_file()
            else "configs/experiment.yaml is missing",
        )
    )

    git = shutil.which("git")
    checks.append(CheckResult("git", git is not None, f"found {git}" if git else "git is not on PATH"))

    if git:
        inside = _run(["git", "rev-parse", "--is-inside-work-tree"], root)
        checks.append(
            CheckResult(
                "git repository",
                inside is not None and inside.returncode == 0 and inside.stdout.strip() == "true",
                "inside a git repository"
                if inside is not None and inside.returncode == 0 and inside.stdout.strip() == "true"
                else "not inside a git repository",
            )
        )

        status = _run(["git", "status", "--short"], root)
        clean = status is not None and status.returncode == 0 and not status.stdout.strip()
        checks.append(
            CheckResult(
                "clean worktree",
                clean,
                "git worktree is clean"
                if clean
                else "git worktree has uncommitted changes; use a disposable worktree for live runs",
                required=False,
            )
        )

    uv = shutil.which("uv")
    checks.append(CheckResult("uv", uv is not None, f"found {uv}" if uv else "uv is not on PATH"))

    claude = shutil.which("claude")
    checks.append(
        CheckResult(
            "claude cli",
            claude is not None,
            f"found {claude}" if claude else "claude is not on PATH; live runs are unavailable",
        )
    )

    if claude:
        version = _run(["claude", "--version"], root)
        checks.append(
            CheckResult(
                "claude version",
                version is not None and version.returncode == 0,
                version.stdout.strip() or "claude --version failed",
                required=False,
            )
        )

        auth = _run(["claude", "auth", "status"], root)
        checks.append(
            CheckResult(
                "claude auth",
                auth is not None and auth.returncode == 0,
                "authenticated" if auth is not None and auth.returncode == 0 else "not authenticated or auth status failed",
                required=False,
            )
        )

    checks.append(
        CheckResult(
            "claude project agents",
            (root / ".claude" / "agents").is_dir(),
            ".claude/agents templates are present"
            if (root / ".claude" / "agents").is_dir()
            else ".claude/agents templates are missing",
            required=False,
        )
    )

    return checks


def format_checks(checks: list[CheckResult]) -> str:
    lines = []
    for check in checks:
        marker = "ok" if check.ok else ("warn" if not check.required else "fail")
        lines.append(f"[{marker}] {check.name}: {check.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="agent-workflow doctor",
        description="Check whether this checkout is ready for live Agent Workflow runs.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    checks = run_checks(args.repo_root)
    print(format_checks(checks))

    if any(not check.ok and check.required for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
