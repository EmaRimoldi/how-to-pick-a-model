"""Published commands keep working after their implementations move into vao."""

import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", [
    "analyze_context_value", "analyze_continuation_pilot",
    "analyze_feedback_routing", "analyze_recovery_transfer",
    "analyze_recovery_validation", "report_feedback_routing",
    "verify_feedback_evidence",
])
def test_published_analysis_entrypoint_uses_the_installed_implementation(name):
    facade = importlib.import_module(f"scripts.{name}")
    implementation = importlib.import_module(f"vao.analysis.{name}")
    assert facade.main is implementation.main
    result = subprocess.run(
        [sys.executable, f"scripts/{name}.py", "--help"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert "--help" in result.stdout


def test_historical_humaneval_command_matches_canonical_trace_replay():
    def replay(namespace):
        result = subprocess.run(
            [sys.executable, "-m", f"{namespace}.load_traces"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)

    canonical = replay("vao.humaneval")
    assert canonical == replay("src")
    assert canonical["n_tasks"] == 164
    assert set(canonical["counts"].values()) == {164}
