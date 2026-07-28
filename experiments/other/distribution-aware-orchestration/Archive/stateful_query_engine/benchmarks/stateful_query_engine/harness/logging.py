"""Structured logging helpers for benchmark runs."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        rows.append(json.loads(raw))
    return rows


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EventLogger:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.events_path = run_dir / "logs" / "events.jsonl"
        self.memory_path = run_dir / "logs" / "memory_events.jsonl"
        self.candidate_path = run_dir / "logs" / "candidates.jsonl"
        self._event_index = 0

    def event(self, event_type: str, **payload: Any) -> dict[str, Any]:
        record = {
            "event_index": self._event_index,
            "event_type": event_type,
            "timestamp": now_iso(),
            "monotonic_seconds": time.monotonic(),
            **payload,
        }
        self._event_index += 1
        append_jsonl(self.events_path, record)
        return record

    def memory_event(self, event_type: str, **payload: Any) -> dict[str, Any]:
        start = time.perf_counter()
        latency_ms = payload.pop("latency_ms", None)
        if latency_ms is None:
            latency_ms = (time.perf_counter() - start) * 1000.0
        record = self.event(event_type, latency_ms=latency_ms, **payload)
        append_jsonl(self.memory_path, record)
        return record

    def candidate(self, **payload: Any) -> dict[str, Any]:
        record = {
            "timestamp": now_iso(),
            **payload,
        }
        append_jsonl(self.candidate_path, record)
        return record

