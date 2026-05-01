"""Run oracle-family task-mode pilot studies on top of the benchmark solver."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from vao.orchestrator import _load_model_configs, run_single
from vao.task_modes import TASK_MODES, single_family_instance_overrides, validate_task_mode


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
    parser.add_argument("--config", default="configs/oracle_family_pilot.yaml")
    parser.add_argument("--models", default=None, help="Comma-separated model keys. Defaults to config include list.")
    parser.add_argument("--families", default=",".join(TASK_MODES))
    parser.add_argument("--seeds", required=True, help="Either comma-separated seeds or start:count.")
    parser.add_argument("--profile", default="hard_optimization")
    parser.add_argument("--split", choices=["pilot", "holdout"], default="pilot")
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--run-prefix", default="oracle_family")
    parser.add_argument("--selection-policy", choices=["top1", "fixed_mode", "mode_sequence"], default=None)
    parser.add_argument("--selected-mode", default=None)
    parser.add_argument("--selected-mode-sequence", default=None, help="Comma-separated sequence used when selection-policy=mode_sequence.")
    parser.add_argument("--traces-per-family", type=int, default=1)
    parser.add_argument("--trace-length", type=int, default=None)
    parser.add_argument("--repetitions", type=int, default=None)
    parser.add_argument("--warmup-prefix", type=int, default=None)
    parser.add_argument("--initial-size", type=int, default=None)
    parser.add_argument("--key-space", type=int, default=None)
    parser.add_argument("--value-max", type=int, default=None)
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    config = _load_config(config_path)
    model_configs = _load_model_configs()
    model_keys = _parse_csv(args.models) or list(config.get("models", {}).get("include", []))
    families = _parse_csv(args.families)
    seeds = _parse_seeds(args.seeds)
    if not model_keys:
        raise ValueError("No models selected for oracle-family pilot")

    completed: list[str] = []
    for family in families:
        validate_task_mode(family)
        for seed in seeds:
            overrides = single_family_instance_overrides(
                family,
                seed=seed,
                traces_per_family=args.traces_per_family,
                initial_size=args.initial_size,
                key_space=args.key_space,
                trace_length=args.trace_length,
                repetitions=args.repetitions,
                warmup_prefix=args.warmup_prefix,
                value_max=args.value_max,
            )
            for model_key in model_keys:
                if model_key not in model_configs:
                    raise KeyError(f"Unknown model key {model_key!r}")
                effective = json.loads(json.dumps(config))
                effective.setdefault("models", {})["include"] = [model_key]
                effective.setdefault("benchmark", {})["profiles"] = [args.profile]
                effective["benchmark"]["instance_overrides"] = overrides
                effective.setdefault("experiment", {})["task_mode_split"] = args.split
                if args.steps is not None:
                    effective["experiment"]["steps"] = int(args.steps)
                if args.selection_policy is not None:
                    effective["experiment"]["selection_policy"] = str(args.selection_policy)
                if args.selected_mode is not None:
                    effective["experiment"]["selected_mode"] = str(args.selected_mode)
                if args.selected_mode_sequence is not None:
                    effective["experiment"]["selected_mode_sequence"] = _parse_csv(args.selected_mode_sequence)
                if args.output_root:
                    effective.setdefault("output", {})["root"] = args.output_root
                run_id = f"{args.run_prefix}_{args.split}_{family}_seed{seed}_{model_key}"
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
