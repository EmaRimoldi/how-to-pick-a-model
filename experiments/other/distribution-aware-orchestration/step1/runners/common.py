"""Shared utilities for HumanEval Step 1 runners."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from datasets import load_dataset


STEP1_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = STEP1_ROOT.parent
DATA_DIR = STEP1_ROOT / "data"
BLOCKS_DIR = STEP1_ROOT / "blocks"
PROFILE_DIR = STEP1_ROOT / "profile"
ARTIFACT_DIR = STEP1_ROOT / "artifact"
ORACLES_DIR = STEP1_ROOT / "oracles"
LOGS_DIR = STEP1_ROOT / "logs"
METRICS_DIR = STEP1_ROOT / "metrics"
PROMPTS_DIR = STEP1_ROOT / "prompts"


def ensure_step1_dirs() -> None:
    for path in [
        DATA_DIR,
        BLOCKS_DIR,
        PROFILE_DIR,
        ARTIFACT_DIR,
        ORACLES_DIR,
        LOGS_DIR,
        METRICS_DIR,
        PROMPTS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def load_humaneval(*, limit: int | None = None) -> list[dict[str, Any]]:
    dataset = load_dataset("openai_humaneval", split="test")
    rows = [dict(row) for row in dataset]
    if limit is not None:
        rows = rows[:limit]
    return rows


def public_instance(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": row["task_id"],
        "prompt": row["prompt"],
        "entry_point": row["entry_point"],
    }


def verifier_instance(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": row["task_id"],
        "prompt": row["prompt"],
        "entry_point": row["entry_point"],
        "test": row["test"],
    }


def gold_instance(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": row["task_id"],
        "prompt": row["prompt"],
        "entry_point": row["entry_point"],
        "canonical_solution": row["canonical_solution"],
        "test": row["test"],
    }

