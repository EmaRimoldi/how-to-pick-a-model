"""Tests for runtime/autoresearch_adapter.py."""

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agent_workflow.runtime.autoresearch_adapter import (
    read_autoresearch_trajectory,
    read_all_autoresearch_trajectories,
    find_best_autoresearch_result,
    write_results_tsv_row,
    RESULTS_TSV_HEADER,
)


def _make_autoresearch_results(base: Path) -> None:
    """Create fake AutoResearch result files."""
    traj_dir = base / "trajectories" / "exp_test_001"
    traj_dir.mkdir(parents=True)

    (traj_dir / "agent_0.jsonl").write_text(
        '{"step": 350, "val_bpb": 1.150000}\n'
        '{"step": 350, "val_bpb": 1.120000}\n'
    )
    (traj_dir / "agent_1.jsonl").write_text(
        '{"step": 350, "val_bpb": 1.130000}\n'
    )


def test_reads_autoresearch_jsonl_format():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _make_autoresearch_results(base)

        entries = read_autoresearch_trajectory(base, "exp_test_001", "agent_0")
        assert len(entries) == 2
        assert entries[0].step == 350
        assert entries[0].val_bpb == 1.15
        assert entries[1].val_bpb == 1.12


def test_returns_empty_for_missing_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        entries = read_autoresearch_trajectory(base, "nonexistent_run", "agent_0")
        assert entries == []


def test_reads_all_trajectories():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _make_autoresearch_results(base)

        all_traj = read_all_autoresearch_trajectories(base)
        assert ("exp_test_001", "agent_0") in all_traj
        assert ("exp_test_001", "agent_1") in all_traj
        assert len(all_traj[("exp_test_001", "agent_0")]) == 2


def test_find_best_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _make_autoresearch_results(base)

        result = find_best_autoresearch_result(base)
        assert result is not None
        run_id, agent_id, val_bpb = result
        assert val_bpb == 1.12  # best across all entries


def test_preserves_results_tsv_schema():
    with tempfile.TemporaryDirectory() as tmpdir:
        tsv = Path(tmpdir) / "results.tsv"
        write_results_tsv_row(tsv, "abc1234", 1.102075, 44.0, "keep", "baseline run")

        lines = tsv.read_text().splitlines()
        assert lines[0] == RESULTS_TSV_HEADER
        assert len(lines) == 2
        cols = lines[1].split("\t")
        assert cols[0] == "abc1234"
        assert cols[1] == "1.102075"
        assert cols[2] == "44.0"
        assert cols[3] == "keep"
        assert cols[4] == "baseline run"


def test_results_tsv_appends():
    with tempfile.TemporaryDirectory() as tmpdir:
        tsv = Path(tmpdir) / "results.tsv"
        write_results_tsv_row(tsv, "abc1234", 1.15, 44.0, "keep", "first")
        write_results_tsv_row(tsv, "def5678", 1.10, 44.0, "keep", "second")

        lines = tsv.read_text().splitlines()
        assert len(lines) == 3  # header + 2 rows
