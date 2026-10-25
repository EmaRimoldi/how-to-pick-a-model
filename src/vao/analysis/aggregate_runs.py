"""Utilities for aggregating run directories."""

from __future__ import annotations

from pathlib import Path

from vao.records import iter_run_dirs, load_step_records
from vao.schemas import StepRecord


def grouped_records(roots: list[Path]) -> dict[Path, list[StepRecord]]:
    groups: dict[Path, list[StepRecord]] = {}
    for root in roots:
        for run_dir in iter_run_dirs(root):
            records = load_step_records(run_dir)
            if records:
                groups[run_dir] = records
    return groups
