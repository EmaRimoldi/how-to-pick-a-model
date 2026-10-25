"""Launch single-trajectory AutoResearch CIFAR-10 campaigns on realistic workloads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from autoresearch.benchmark.cifar10.task_spec import (
    ALL_WORKLOADS,
    single_workload_instance_overrides,
    validate_workload,
    workload_template_path,
)
from vao.orchestrator import _load_model_configs, run_single


def _parse_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_seeds(value: str) -> list[int]:
    if ":" in value:
        start_text, count_text = value.split(":", 1)
        start = int(start_text)
        count = int(count_text)
        return [start + offset for offset in range(count)]
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="autoresearch/configs/autoresearch_cifar10_single_trajectory_campaign.yaml")
    parser.add_argument("--models", default=None)
    parser.add_argument("--workloads", default=",".join(ALL_WORKLOADS))
    parser.add_argument("--families", default=None, help="Deprecated alias for --workloads")
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--profile", default="autoresearch_cifar10")
    parser.add_argument("--split", choices=["pilot", "holdout"], default="pilot")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--max-train-steps", type=int, default=256)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--run-prefix", default="autoresearch_singletraj")
    args = parser.parse_args(argv)

    config = _load_config(Path(args.config))
    model_configs = _load_model_configs()
    model_keys = _parse_csv(args.models) or list(config.get("models", {}).get("include", []))
    workload_arg = args.families if args.families is not None else args.workloads
    workloads = _parse_csv(workload_arg)
    seeds = _parse_seeds(args.seeds)
    if not model_keys:
        raise ValueError("No models selected for AutoResearch single-trajectory campaign")

    completed: list[str] = []
    for workload_id in workloads:
        validate_workload(workload_id)
        for seed in seeds:
            overrides = single_workload_instance_overrides(workload_id, seed=seed, max_train_steps=args.max_train_steps)
            for model_key in model_keys:
                if model_key not in model_configs:
                    raise KeyError(f"Unknown model key {model_key!r}")
                effective = json.loads(json.dumps(config))
                effective.setdefault("models", {})["include"] = [model_key]
                effective.setdefault("benchmark", {})["profiles"] = [args.profile]
                effective["benchmark"]["instance_overrides"] = overrides
                effective["benchmark"]["template_path"] = str(workload_template_path(workload_id))
                effective.setdefault("experiment", {})["task_mode_split"] = args.split
                effective["experiment"]["workload_split"] = args.split
                effective["experiment"]["steps"] = int(args.steps)
                if args.output_root:
                    effective.setdefault("output", {})["root"] = args.output_root
                run_id = f"{args.run_prefix}_{args.split}_{workload_id}_seed{seed}_{model_key}"
                completed.append(
                    str(
                        run_single(
                            effective,
                            model_key,
                            model_configs[model_key],
                            args.profile,
                            run_id=run_id,
                        )
                    )
                )

    print(json.dumps({"run_count": len(completed), "runs": completed}, indent=2))


if __name__ == "__main__":
    main()
