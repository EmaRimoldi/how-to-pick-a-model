"""Tests for snapshotting.py — snapshot creation, update, and selection."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent_workflow.instrumentation.snapshotting import (
    SnapshotManager,
    SnapshotMetadata,
    generate_save_snapshot_py,
    generate_update_snapshot_py,
)


@pytest.fixture
def tmp_snap(tmp_path):
    return SnapshotManager(tmp_path / "snapshots")


@pytest.fixture
def sample_train_py(tmp_path):
    f = tmp_path / "train.py"
    f.write_text("EMBEDDING_LR = 1e-3\nWEIGHT_DECAY = 0.1\n")
    return f


def _meta(step: int, agent_id: str = "agent_0", **kwargs) -> SnapshotMetadata:
    return SnapshotMetadata(
        step_index=step,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent_id=agent_id,
        **kwargs,
    )


class TestSnapshotManager:
    def test_next_step_index_empty(self, tmp_snap):
        assert tmp_snap.next_step_index() == 0

    def test_next_step_index_increments(self, tmp_snap, sample_train_py):
        for i in range(3):
            tmp_snap.save(sample_train_py, _meta(i))
        assert tmp_snap.next_step_index() == 3

    def test_save_creates_files(self, tmp_snap, sample_train_py):
        meta = _meta(0, hypothesis="test")
        snap_dir = tmp_snap.save(sample_train_py, meta)
        assert (snap_dir / "train.py").exists()
        assert (snap_dir / "metadata.json").exists()

    def test_save_train_py_content(self, tmp_snap, sample_train_py):
        meta = _meta(0)
        snap_dir = tmp_snap.save(sample_train_py, meta)
        assert "EMBEDDING_LR" in (snap_dir / "train.py").read_text()

    def test_save_metadata_roundtrip(self, tmp_snap, sample_train_py):
        meta = _meta(0, hypothesis="lower lr", expected_effect="reduce overfitting")
        snap_dir = tmp_snap.save(sample_train_py, meta)
        loaded = json.loads((snap_dir / "metadata.json").read_text())
        assert loaded["hypothesis"] == "lower lr"
        assert loaded["expected_effect"] == "reduce overfitting"
        assert loaded["step_index"] == 0

    def test_update_sets_fields(self, tmp_snap, sample_train_py):
        meta = _meta(0)
        tmp_snap.save(sample_train_py, meta)
        tmp_snap.update(0, val_bpb_after=1.23, accepted=True, reason="improved")
        loaded = json.loads(
            (tmp_snap.snapshots_dir / "step_000" / "metadata.json").read_text()
        )
        assert loaded["val_bpb_after"] == 1.23
        assert loaded["accepted"] is True
        assert loaded["reason"] == "improved"

    def test_update_nonexistent_step_is_noop(self, tmp_snap):
        # Should not raise
        tmp_snap.update(99, val_bpb_after=1.0)

    def test_list_snapshots_order(self, tmp_snap, sample_train_py):
        for i in [2, 0, 1]:
            tmp_snap.save(sample_train_py, _meta(i))
        snaps = tmp_snap.list_snapshots()
        assert [s.step_index for s in snaps] == [0, 1, 2]

    def test_best_snapshot_none_when_empty(self, tmp_snap):
        assert tmp_snap.best_snapshot() is None

    def test_best_snapshot_returns_lowest_bpb(self, tmp_snap, sample_train_py):
        for i, bpb in enumerate([1.3, 1.1, 1.2]):
            meta = _meta(i, val_bpb_after=bpb)
            tmp_snap.save(sample_train_py, meta)
        best = tmp_snap.best_snapshot()
        assert best is not None
        assert best.val_bpb_after == pytest.approx(1.1)

    def test_accepted_snapshots_filter(self, tmp_snap, sample_train_py):
        for i, acc in enumerate([True, False, True]):
            meta = _meta(i, accepted=acc)
            tmp_snap.save(sample_train_py, meta)
        acc_snaps = tmp_snap.accepted_snapshots()
        assert len(acc_snaps) == 2
        assert all(s.accepted for s in acc_snaps)

    def test_informative_snapshots_includes_best(self, tmp_snap, sample_train_py):
        for i, bpb in enumerate([1.5, 1.4, 1.1, 1.3]):
            meta = _meta(i, val_bpb_after=bpb, val_bpb_before=(1.5 if i == 0 else None))
            tmp_snap.save(sample_train_py, meta)
        info = tmp_snap.informative_snapshots()
        step_indices = [s.step_index for s in info]
        # Best snapshot (step 2, bpb=1.1) should be included
        assert 2 in step_indices

    def test_snapshot_dir_zero_padded(self, tmp_snap, sample_train_py):
        meta = _meta(5)
        tmp_snap.save(sample_train_py, meta)
        assert (tmp_snap.snapshots_dir / "step_005").exists()

    def test_get_snapshot_dir_returns_none_for_missing(self, tmp_snap):
        assert tmp_snap.get_snapshot_dir(99) is None


class TestSnapshotHelpersGenerated:
    def test_save_snapshot_py_generated(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        results_root = tmp_path / "results"
        results_root.mkdir()
        generate_save_snapshot_py(workspace, "agent_0", results_root)
        assert (workspace / "save_snapshot.py").exists()

    def test_update_snapshot_py_generated(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        results_root = tmp_path / "results"
        results_root.mkdir()
        generate_update_snapshot_py(workspace, results_root)
        assert (workspace / "update_snapshot.py").exists()

    def test_save_snapshot_py_is_executable(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        results_root = tmp_path / "results"
        results_root.mkdir()
        path = generate_save_snapshot_py(workspace, "agent_0", results_root)
        assert path.stat().st_mode & 0o111, "save_snapshot.py should be executable"
