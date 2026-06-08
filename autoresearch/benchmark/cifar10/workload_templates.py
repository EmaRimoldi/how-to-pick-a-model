"""Workload template registry for AutoResearch-style CIFAR-10 tasks.

The benchmark now treats AutoResearch as a single meta-task instantiated on a
small family of realistic workloads.  Each workload is a full editable
``train.py`` with the same verifier and metric, but a different target model
architecture.
"""

from __future__ import annotations

from pathlib import Path

WORKLOAD_DIR = Path(__file__).resolve().parent / "workloads"

WORKLOAD_KEYS = {
    "cnn_compact",
    "mlp_flat",
    "resnet_micro",
    "resnet_tiny",
}


def template_path_for_workload(workload_id: str) -> Path:
    if workload_id not in WORKLOAD_KEYS:
        raise ValueError(f"unknown_workload:{workload_id}")
    path = WORKLOAD_DIR / f"{workload_id}.py"
    if not path.exists():
        raise FileNotFoundError(path)
    return path
