"""Run repository checks and manuscript builds with the active Python environment."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ACTIONS = {
    "indexes": {
        "description": "Regenerate repository inventory, knowledge and command/experiment maps.",
        "dependencies": (),
        "steps": (
            ("scripts/maintenance/build_repo_inventory.py", "--output", "docs/audits/repo-inventory.md"),
            ("scripts/maintenance/build_knowledge_index.py", "--output", "docs/audits/knowledge-index.md"),
            ("scripts/maintenance/build_experiment_manifest.py", "--output", "docs/audits/experiment-manifest.md"),
            ("scripts/maintenance/build_command_manifest.py", "--output", "docs/audits/command-manifest.md"),
        ),
    },
    "readiness": {
        "description": "Validate documentation, evidence links and generated-map freshness.",
        "dependencies": (),
        "steps": (("scripts/maintenance/validate_agent_readiness.py",),),
    },
    "compile": {
        "description": "Byte-compile maintained Python sources, scripts and manuscript builders.",
        "dependencies": (),
        "steps": (("-m", "compileall", "-q", "scripts", "src", "docs/paper"),),
    },
    "test": {
        "description": "Run the offline repository test suite.",
        "dependencies": (),
        "steps": (("-m", "pytest", "tests", "-q"),),
    },
    "check": {
        "description": "Run indexes, readiness, compilation and offline tests in order.",
        "dependencies": ("indexes", "readiness", "compile", "test"),
        "steps": (),
    },
    "paper-build": {
        "description": "Compile retained manuscripts out of tree with pdflatex and bibtex.",
        "dependencies": (),
        "steps": (("scripts/maintenance/check_paper_build.py",),),
    },
}


def run_action(action: str, root: Path, output_root: Path) -> None:
    """Execute each step with one interpreter; a failed step stops the workflow."""
    spec = ACTIONS[action]
    for dependency in spec["dependencies"]:
        run_action(dependency, root, output_root)
    for step in spec["steps"]:
        args = [sys.executable, *step]
        if action == "paper-build":
            args.extend(("--output-root", str(output_root)))
        subprocess.run(args, cwd=root, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=ACTIONS, nargs="?", default="check")
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("/tmp/how_to_pick_a_model_paper_build"),
        help="Out-of-tree directory for paper-build artifacts.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if not (root / "pyproject.toml").is_file():
        parser.error("Run this script from its source checkout.")
    try:
        run_action(args.action, root, args.output_root.resolve())
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
