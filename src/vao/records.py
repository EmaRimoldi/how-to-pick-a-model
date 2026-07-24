"""Record loading helpers."""

from __future__ import annotations

from pathlib import Path

from vao.logging_utils import read_jsonl
from vao.schemas import StepRecord


def iter_run_dirs(root: Path) -> list[Path]:
    if (root / "evaluations.jsonl").exists():
        return [root]
    return sorted(path for path in root.glob("**/evaluations.jsonl") if path.is_file() for path in [path.parent])


def load_step_records(run_dir: Path) -> list[StepRecord]:
    return [StepRecord.model_validate(row) for row in read_jsonl(run_dir / "evaluations.jsonl")]


def load_records_from_roots(roots: list[Path]) -> list[StepRecord]:
    records: list[StepRecord] = []
    for root in roots:
        for run_dir in iter_run_dirs(root):
            records.extend(load_step_records(run_dir))
    return records
