"""Tests for outputs/collector.py."""

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agent_workflow.outputs.collector import collect_experiment, collect_agent_result


def _make_agent_dir(base: Path, agent_id: str, entries: list[dict] = None) -> Path:
    agent_dir = base / agent_id
    results_dir = agent_dir / "results"
    results_dir.mkdir(parents=True)
    (agent_dir / "logs").mkdir()

    if entries:
        traj = results_dir / "trajectory.jsonl"
        traj.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    return agent_dir


def test_aggregation_works_if_one_agent_crashes():
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = Path(tmpdir)
        mode_dir = exp_dir / "mode_parallel"
        mode_dir.mkdir()

        # agent_0: has results
        _make_agent_dir(
            mode_dir, "agent_0",
            entries=[{"step": 350, "val_bpb": 1.15}, {"step": 350, "val_bpb": 1.10}],
        )
        # agent_1: no trajectory (crashed)
        _make_agent_dir(mode_dir, "agent_1", entries=None)

        summary = collect_experiment(
            experiment_dir=exp_dir,
            experiment_id="test_exp",
            mode="parallel",
            agent_ids=["agent_0", "agent_1"],
        )

        assert len(summary.agent_results) == 2
        agent_0 = next(r for r in summary.agent_results if r.agent_id == "agent_0")
        agent_1 = next(r for r in summary.agent_results if r.agent_id == "agent_1")

        assert not agent_0.failed
        assert agent_0.best_val_bpb == pytest.approx(1.10) if False else agent_0.best_val_bpb == 1.10
        assert agent_1.failed


def test_combined_summary_contains_all_agents():
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = Path(tmpdir)
        mode_dir = exp_dir / "mode_parallel"
        mode_dir.mkdir()

        for aid in ["agent_0", "agent_1"]:
            _make_agent_dir(
                mode_dir, aid,
                entries=[{"step": 350, "val_bpb": 1.12}],
            )

        summary = collect_experiment(
            experiment_dir=exp_dir,
            experiment_id="test_exp",
            mode="parallel",
            agent_ids=["agent_0", "agent_1"],
        )

        combined_path = mode_dir / "aggregate" / "combined_summary.json"
        assert combined_path.exists()
        data = json.loads(combined_path.read_text())
        result_ids = [r["agent_id"] for r in data["agent_results"]]
        assert "agent_0" in result_ids
        assert "agent_1" in result_ids


def test_comparison_table_has_at_least_one_row_per_agent():
    import csv

    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = Path(tmpdir)
        mode_dir = exp_dir / "mode_parallel"
        mode_dir.mkdir()

        _make_agent_dir(
            mode_dir, "agent_0",
            entries=[{"step": 350, "val_bpb": 1.10}],
        )
        _make_agent_dir(mode_dir, "agent_1", entries=None)

        collect_experiment(
            experiment_dir=exp_dir,
            experiment_id="test_exp",
            mode="parallel",
            agent_ids=["agent_0", "agent_1"],
        )

        csv_path = mode_dir / "aggregate" / "comparison_table.csv"
        assert csv_path.exists()
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        agent_ids_in_csv = {r["agent_id"] for r in rows}
        assert "agent_0" in agent_ids_in_csv
        assert "agent_1" in agent_ids_in_csv
