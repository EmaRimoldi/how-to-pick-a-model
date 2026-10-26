"""Protect real-source provenance and the development/evaluator boundary offline."""

import json
from pathlib import Path
import shutil

import pytest

from vao.repair.pool import build_pool, read_pool
from vao.repair.environment import RepairTask


POOL = Path(__file__).resolve().parents[2] / "experiments/python-repair/checkpoint-environment/development"


def test_real_pool_rebuild_is_deterministic_and_executable_source_is_only_data(tmp_path):
    first = build_pool(POOL, tmp_path / "first")
    second = build_pool(POOL, tmp_path / "second")
    assert len(first) == len(second) == 12
    for a, b in zip(first, second, strict=True):
        assert {p.name: p.read_bytes() for p in a.iterdir()} == {p.name: p.read_bytes() for p in b.iterdir()}
        task = RepairTask.load(a)
        assert task.public["provenance"]["kind"] == "adapted_real_bug_development"
        assert task.public["task_id"].startswith("development/")
        for files in (task.public["files"], json.loads((a / "reference.json").read_text())):
            for name, source in files.items():
                compile(source, name, "exec")  # Parse only; never execute upstream code in the test host.
    with pytest.raises(FileExistsError):
        build_pool(POOL, tmp_path / "first")


def test_changed_upstream_excerpt_is_rejected(tmp_path):
    root = tmp_path / "pool"
    shutil.copytree(POOL, root)
    path = root / "upstream/youtube-dl-003/buggy.txt"
    path.write_text(path.read_text() + "# altered\n")
    with pytest.raises(ValueError, match="Excerpt hash"):
        read_pool(root)


def test_evaluator_cannot_reuse_public_input_under_a_different_id(tmp_path):
    root = tmp_path / "pool"
    shutil.copytree(POOL, root)
    path = root / "pool.json"
    data = json.loads(path.read_text())
    task = data["tasks"][0]
    duplicate = dict(task["public_cases"][0], id="evaluator-renamed")
    task["evaluator_cases"].append(duplicate)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="inputs overlap"):
        read_pool(root)


def test_inspected_pool_cannot_be_relabelled_as_evaluation(tmp_path):
    root = tmp_path / "pool"
    shutil.copytree(POOL, root)
    path = root / "pool.json"
    data = json.loads(path.read_text())
    data["tasks"][0]["split"] = "evaluation"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="development data"):
        read_pool(root)
