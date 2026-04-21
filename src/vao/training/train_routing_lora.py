"""QLoRA training entrypoint placeholder.

The implementation guide asks not to train before clean routing supervision
data exists. This module validates the config and records the intended command
surface for a later training run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    training = config.get("training", {})
    required = ["base_model", "train_records", "eval_records", "output_dir"]
    missing = [key for key in required if key not in training]
    if missing:
        raise SystemExit(f"Missing training config keys: {missing}")
    print(json.dumps({"status": "not_started", "reason": "training intentionally scaffolded", "config": training}, indent=2))


if __name__ == "__main__":
    main()
