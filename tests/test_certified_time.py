"""Tests for certified_time.py."""

import json
from pathlib import Path

from agent_workflow.instrumentation.certified_time import (
    collect_training_events,
    estimate_certified_times,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


def _make_agent(
    mode_dir: Path,
    agent_id: str,
    *,
    start_iso: str,
    turns: list[dict],
    runs: list[dict],
) -> None:
    results = mode_dir / agent_id / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / "metadata.json").write_text(
        json.dumps({"start_time": start_iso, "agent_id": agent_id})
    )
    _write_jsonl(results / "turns.jsonl", turns)
    _write_jsonl(results / "training_runs.jsonl", runs)


def test_collect_training_events_uses_replicate_elapsed_time(tmp_path):
    mode_dir = tmp_path / "experiment_rg_d00_rep01" / "mode_single_long"
    start = "1970-01-12T13:46:40+00:00"
    _make_agent(
        mode_dir,
        "agent_0",
        start_iso=start,
        turns=[{"timestamp": 1_000_030.0, "turn": 0, "total_tokens": 100}],
        runs=[
            {
                "run_index": 1,
                "turn": 0,
                "agent_id": "agent_0",
                "finished_at": 1_000_020.0,
                "wall_seconds": 20.0,
                "val_bpb": 0.9,
                "candidate_mean_val_bpb_after": 0.9,
                "candidate_eval_count_after": 1,
                "candidate_id": "agent_0:abc",
            }
        ],
    )

    events = collect_training_events(mode_dir)

    assert len(events) == 1
    assert events[0].wall_elapsed_seconds == 20.0
    assert events[0].cumulative_tokens == 100.0


def test_estimate_certified_times_requires_enough_hits(tmp_path):
    for rep, val in [("rep01", 0.91), ("rep02", 0.95)]:
        mode_dir = tmp_path / f"experiment_rg_d00_{rep}" / "mode_single_long"
        _make_agent(
            mode_dir,
            "agent_0",
            start_iso="1970-01-12T13:46:40+00:00",
            turns=[{"timestamp": 1_000_040.0, "turn": 0, "total_tokens": 100}],
            runs=[
                {
                    "run_index": 1,
                    "turn": 0,
                    "agent_id": "agent_0",
                    "finished_at": 1_000_030.0,
                    "wall_seconds": 30.0,
                    "val_bpb": val,
                    "candidate_mean_val_bpb_after": val,
                    "candidate_eval_count_after": 1,
                }
            ],
        )

    estimates = estimate_certified_times(
        sorted(tmp_path.glob("experiment_*/mode_single_long")),
        target_val_bpb=0.92,
        confidence=0.5,
    )

    estimate = estimates["single_long"]
    assert estimate.certified is True
    assert estimate.hit_count == 1
    assert estimate.required_hits == 1
    assert estimate.t_wall_seconds == 30.0


def test_require_reevaluation_rejects_single_shot_hit(tmp_path):
    mode_dir = tmp_path / "experiment_rg_d00_rep01" / "mode_single_long"
    _make_agent(
        mode_dir,
        "agent_0",
        start_iso="1970-01-12T13:46:40+00:00",
        turns=[{"timestamp": 1_000_040.0, "turn": 0, "total_tokens": 100}],
        runs=[
            {
                "run_index": 1,
                "turn": 0,
                "agent_id": "agent_0",
                "finished_at": 1_000_030.0,
                "wall_seconds": 30.0,
                "val_bpb": 0.91,
                "candidate_mean_val_bpb_after": 0.91,
                "candidate_eval_count_after": 1,
            }
        ],
    )

    estimates = estimate_certified_times(
        [mode_dir],
        target_val_bpb=0.92,
        confidence=1.0,
        require_reevaluation=True,
        min_evaluations=2,
    )

    assert estimates["single_long"].certified is False
    assert estimates["single_long"].hit_count == 0
