"""Tests for the canonical swarm blackboard integration."""

from pathlib import Path

from agent_workflow.communication.blackboard import SharedMemory, ENTRY_RESULT


def test_blackboard_claim_dedup_and_release(tmp_path: Path):
    sm = SharedMemory(tmp_path / "shared_memory.jsonl")

    ok, claim_id = sm.claim("agent_0", "lower embedding lr", ttl_seconds=60)
    assert ok
    assert claim_id

    duplicate_ok, _ = sm.claim("agent_1", "lower embedding lr", ttl_seconds=60)
    assert not duplicate_ok

    sm.release_claim("agent_0", claim_id)
    retry_ok, retry_claim = sm.claim("agent_1", "lower embedding lr", ttl_seconds=60)
    assert retry_ok
    assert retry_claim


def test_blackboard_best_uses_sidecar(tmp_path: Path):
    sm = SharedMemory(tmp_path / "shared_memory.jsonl")
    assert sm.update_best("agent_0", 1.2, "LR = 1e-3\n")
    assert sm.update_best("agent_1", 1.1, "LR = 5e-4\n")
    assert not sm.update_best("agent_0", 1.3, "LR = 2e-3\n")

    best = sm.get_best()
    assert best is not None
    assert best["agent_id"] == "agent_1"
    assert best["val_bpb"] == 1.1
    assert best["train_py_src"] == "LR = 5e-4\n"


def test_blackboard_read_others_excludes_agent(tmp_path: Path):
    sm = SharedMemory(tmp_path / "shared_memory.jsonl")
    sm.write("agent_0", ENTRY_RESULT, {"val_bpb": 1.2})
    sm.write("agent_1", ENTRY_RESULT, {"val_bpb": 1.1})

    others = sm.read_others("agent_0")
    assert len(others) == 1
    assert others[0]["agent_id"] == "agent_1"
