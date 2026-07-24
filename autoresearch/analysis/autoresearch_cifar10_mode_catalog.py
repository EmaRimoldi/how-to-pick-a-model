"""Render the workload/action catalog for the AutoResearch CIFAR-10 benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoresearch.benchmark.cifar10.task_spec import ACTION_MODE_ALIASES, WORKLOAD_REGISTRY


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="autoresearch/artifacts_mode_catalog")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "action_mode_aliases": ACTION_MODE_ALIASES,
        "workloads": WORKLOAD_REGISTRY,
    }
    (out_dir / "mode_catalog.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = ["# AutoResearch CIFAR-10 Workload Catalog", "", "## Action Modes", ""]
    for key, value in ACTION_MODE_ALIASES.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Workloads", ""])
    for mode, spec in WORKLOAD_REGISTRY.items():
        lines.append(f"- `{mode}`: {spec['description']}")
        lines.append(
            f"  train_subset={spec['train_subset_size']}, val_subset={spec['val_subset_size']}, "
            f"label_noise={spec['label_noise_rate']}, imbalance_ratio={spec['imbalance_ratio']}, "
            f"max_train_steps={spec['max_train_steps']}, seed={spec['seed']}"
        )
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
