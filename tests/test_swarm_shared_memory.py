from __future__ import annotations

import json
import multiprocessing
import time
from pathlib import Path

from agent_workflow.swarm.shared_memory import (
    ENTRY_RESULT,
    ENTRY_STATUS,
    SharedMemory,
)


def test_swarm_memory_filters_own_entries(tmp_path: Path) -> None:
    memory = SharedMemory(tmp_path / "shared_memory.jsonl", max_context_entries=20)
    memory.write("agent_0", ENTRY_RESULT, {"step": 1, "val_bpb": 1.1})
    memory.write("agent_1", ENTRY_RESULT, {"step": 1, "val_bpb": 1.09})
    memory.write("agent_0", ENTRY_STATUS, {"message": "done"})

    other_entries = memory.read_others("agent_0")

    assert len(other_entries) == 1
    assert other_entries[0]["agent_id"] == "agent_1"


def test_swarm_memory_updates_best_sidecar(tmp_path: Path) -> None:
    memory = SharedMemory(tmp_path / "shared_memory.jsonl")

    assert memory.update_best("agent_0", 1.2, "BEST = 1\n")
    assert not memory.update_best("agent_1", 1.3, "WORSE = 1\n")

    best = memory.get_best()
    assert best is not None
    assert best["agent_id"] == "agent_0"
    assert best["val_bpb"] == 1.2
    assert best["train_py_src"] == "BEST = 1\n"


def _write_many(path: str, agent_id: str, n_writes: int) -> None:
    memory = SharedMemory(Path(path), max_context_entries=1000)
    for index in range(n_writes):
        memory.write(agent_id, ENTRY_RESULT, {"step": index, "val_bpb": 1.0})
        time.sleep(0.001)


def test_swarm_memory_concurrent_writes_are_valid_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "shared_memory.jsonl"
    processes = [
        multiprocessing.Process(target=_write_many, args=(str(path), f"agent_{i}", 10))
        for i in range(3)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=30)

    entries = SharedMemory(path).read_all()
    assert len(entries) == 30
    for entry in entries:
        json.dumps(entry)
        assert "agent_id" in entry
        assert "timestamp" in entry
        assert "entry_type" in entry
        assert "content" in entry
