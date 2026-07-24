"""Tests for canonical diversity metrics."""

import json
from pathlib import Path

import pytest

from agent_workflow.analysis.diversity import (
    dtw_distance,
    load_trajectory,
    mean_pairwise_dtw_distance,
    measure_h_post_trajectory,
)


def test_dtw_distance_identical_series_is_zero():
    assert dtw_distance([1.0, 1.1, 1.2], [1.0, 1.1, 1.2]) == 0.0


def test_mean_pairwise_dtw_distance():
    assert mean_pairwise_dtw_distance([[1.0, 1.1], [1.0, 1.2]]) == pytest.approx(0.1)


def test_measure_h_post_trajectory_loads_jsonl(tmp_path: Path):
    run_dir = tmp_path / "trajectories" / "run_1"
    run_dir.mkdir(parents=True)
    (run_dir / "agent_0.jsonl").write_text(
        "\n".join(json.dumps({"val_bpb": v}) for v in [1.0, 1.1]) + "\n"
    )
    (run_dir / "agent_1.jsonl").write_text(
        "\n".join(json.dumps({"val_bpb": v}) for v in [1.0, 1.2]) + "\n"
    )

    assert load_trajectory(run_dir / "agent_0.jsonl") == [1.0, 1.1]
    assert measure_h_post_trajectory(tmp_path / "trajectories", "run_1") == pytest.approx(0.1)
