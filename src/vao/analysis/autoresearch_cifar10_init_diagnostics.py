"""Diagnose mode-specific initializations for AutoResearch task modes.

For each task mode, this script evaluates a small grid of candidate initial
``train.py`` settings together with a targeted repair and several off-target
repairs. The goal is to verify that the chosen initial state makes the intended
bottleneck visible and that the targeted repair yields the strongest gain.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from benchmarks.autoresearch_cifar10.dynamic_benchmark import run_candidate
from benchmarks.autoresearch_cifar10.initial_templates import BASE_TEMPLATE_PATH
from benchmarks.autoresearch_cifar10.task_spec import ALL_FAMILIES, LATENT_MODE_REGISTRY, single_family_instance_overrides


def _apply_replacements(text: str, replacements: dict[str, str]) -> str:
    for old, new in replacements.items():
        if old not in text:
            raise ValueError(f"missing_anchor:{old}")
        text = text.replace(old, new, 1)
    return text


def _write_variant(path: Path, replacements: dict[str, str]) -> Path:
    text = BASE_TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = _apply_replacements(text, replacements)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return path


MODE_PLAN = {
    "lr-sensitive": {
        "candidates": {
            "lr_1e-5": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1e-5"},
            "lr_5e-5": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 5e-5"},
            "lr_1e-4": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1e-4"},
        },
        "target_fix": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1.5e-3"},
        "controls": {
            "schedule_on": {"USE_LR_SCHEDULE = False": "USE_LR_SCHEDULE = True"},
            "capacity_up": {"BASE_CHANNELS = 12": "BASE_CHANNELS = 16", "FC_HIDDEN = 48": "FC_HIDDEN = 64"},
        },
    },
    "regularization-sensitive": {
        "candidates": {
            "wd0_drop0": {"WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 0.0"},
            "wd1e-5_drop0": {"WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 1e-5"},
            "wd0_drop005": {"WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 0.0", "DROPOUT_RATE = 0.0": "DROPOUT_RATE = 0.05"},
        },
        "target_fix": {"WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 5e-4", "DROPOUT_RATE = 0.0": "DROPOUT_RATE = 0.15"},
        "controls": {
            "lr_up": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1.5e-3"},
            "schedule_on": {"USE_LR_SCHEDULE = False": "USE_LR_SCHEDULE = True"},
        },
    },
    "optimizer-sensitive": {
        "candidates": {
            "sgd_lr2e-2_m0": {'OPTIMIZER = "adam"': 'OPTIMIZER = "sgd"', "LEARNING_RATE = 5e-4": "LEARNING_RATE = 2e-2", "MOMENTUM = 0.9": "MOMENTUM = 0.0"},
            "sgd_lr1e-2_m0": {'OPTIMIZER = "adam"': 'OPTIMIZER = "sgd"', "LEARNING_RATE = 5e-4": "LEARNING_RATE = 1e-2", "MOMENTUM = 0.9": "MOMENTUM = 0.0"},
            "adam_lr1e-4": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1e-4"},
        },
        "target_fix": {'OPTIMIZER = "adam"': 'OPTIMIZER = "adamw"', "ADAM_BETAS = (0.9, 0.999)": "ADAM_BETAS = (0.9, 0.99)", "WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 2e-4"},
        "controls": {
            "lr_up": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1.5e-3"},
            "schedule_on": {"USE_LR_SCHEDULE = False": "USE_LR_SCHEDULE = True"},
        },
    },
    "data-skew-sensitive": {
        "candidates": {
            "sgd_lr2e-2_m0": {'OPTIMIZER = "adam"': 'OPTIMIZER = "sgd"', "LEARNING_RATE = 5e-4": "LEARNING_RATE = 2e-2", "MOMENTUM = 0.9": "MOMENTUM = 0.0", "BATCH_SIZE = 64": "BATCH_SIZE = 128"},
            "adam_lr5e-4_b128": {"BATCH_SIZE = 64": "BATCH_SIZE = 128", "WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 0.0"},
            "adam_lr1e-4_b128": {"BATCH_SIZE = 64": "BATCH_SIZE = 128", "LEARNING_RATE = 5e-4": "LEARNING_RATE = 1e-4", "WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 0.0"},
        },
        "target_fix": {'OPTIMIZER = "adam"': 'OPTIMIZER = "sgd"', "MOMENTUM = 0.9": "MOMENTUM = 0.95", "WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 2e-4"},
        "controls": {
            "capacity_up": {"BASE_CHANNELS = 12": "BASE_CHANNELS = 16", "FC_HIDDEN = 48": "FC_HIDDEN = 64"},
            "schedule_on": {"USE_LR_SCHEDULE = False": "USE_LR_SCHEDULE = True"},
        },
    },
    "capacity-sensitive": {
        "candidates": {
            "tiny": {"DEPTH = 2": "DEPTH = 1", "BASE_CHANNELS = 12": "BASE_CHANNELS = 8", "FC_HIDDEN = 48": "FC_HIDDEN = 16"},
            "small": {"DEPTH = 2": "DEPTH = 1", "BASE_CHANNELS = 12": "BASE_CHANNELS = 10", "FC_HIDDEN = 48": "FC_HIDDEN = 24"},
            "narrow": {"BASE_CHANNELS = 12": "BASE_CHANNELS = 8", "FC_HIDDEN = 48": "FC_HIDDEN = 24"},
        },
        "target_fix": {"DEPTH = 2": "DEPTH = 3", "BASE_CHANNELS = 12": "BASE_CHANNELS = 16", "FC_HIDDEN = 48": "FC_HIDDEN = 64"},
        "controls": {
            "lr_up": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1.5e-3"},
            "schedule_on": {"USE_LR_SCHEDULE = False": "USE_LR_SCHEDULE = True"},
        },
    },
    "schedule-sensitive": {
        "candidates": {
            "nosched_lr1e-3": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1e-3", "WARMUP_EPOCHS = 2": "WARMUP_EPOCHS = 0"},
            "nosched_lr2e-3": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 2e-3", "WARMUP_EPOCHS = 2": "WARMUP_EPOCHS = 0"},
            "nosched_lr1e-3_decayhard": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1e-3", "LR_DECAY_FACTOR = 0.1": "LR_DECAY_FACTOR = 0.05"},
        },
        "target_fix": {"USE_LR_SCHEDULE = False": "USE_LR_SCHEDULE = True", "WARMUP_EPOCHS = 2": "WARMUP_EPOCHS = 1", "LR_DECAY_FACTOR = 0.1": "LR_DECAY_FACTOR = 0.2"},
        "controls": {
            "lr_up": {"LEARNING_RATE = 5e-4": "LEARNING_RATE = 1.5e-3"},
            "capacity_up": {"BASE_CHANNELS = 12": "BASE_CHANNELS = 16", "FC_HIDDEN = 48": "FC_HIDDEN = 64"},
        },
    },
}


def evaluate(output_root: Path, *, mode: str, variant_name: str, replacements: dict[str, str], timeout: int, seed: int) -> dict[str, Any]:
    solution = _write_variant(output_root / "generated_templates" / mode / f"{variant_name}.py", replacements)
    steps = int(LATENT_MODE_REGISTRY[mode]["max_train_steps"])
    summary = run_candidate(
        solution,
        "autoresearch_cifar10",
        output_root / "runs" / mode / variant_name,
        run_id=f"{mode}_{variant_name}",
        timeout_seconds=timeout,
        instance_overrides=single_family_instance_overrides(mode, seed=seed, max_train_steps=steps),
    )
    metrics = summary.get("metrics") or {}
    return {
        "variant": variant_name,
        "latent_loss": float(summary.get("score", {}).get("latent_loss") or metrics.get("val_loss") or 0.0),
        "val_accuracy": float(metrics.get("val_accuracy") or 0.0),
        "training_seconds": float(metrics.get("training_seconds") or summary.get("elapsed_wall_seconds") or 0.0),
        "passed": bool(summary.get("correctness", {}).get("passed")),
        "solution_path": str(solution),
    }


def evaluate_bundle(output_root: Path, mode: str, candidate_name: str, candidate_repl: dict[str, str], target_fix: dict[str, str], controls: dict[str, dict[str, str]], timeout: int, seed: int) -> tuple[str, dict[str, Any]]:
    baseline = evaluate(output_root, mode=mode, variant_name=f"baseline_{candidate_name}", replacements=candidate_repl, timeout=timeout, seed=seed)
    target = evaluate(output_root, mode=mode, variant_name=f"targetfix_{candidate_name}", replacements={**candidate_repl, **target_fix}, timeout=timeout, seed=seed)
    control_rows = {}
    for control_name, control_fix in controls.items():
        control_rows[control_name] = evaluate(output_root, mode=mode, variant_name=f"{control_name}_{candidate_name}", replacements={**candidate_repl, **control_fix}, timeout=timeout, seed=seed)
    target_gain = baseline["latent_loss"] - target["latent_loss"]
    control_gains = {name: baseline["latent_loss"] - row["latent_loss"] for name, row in control_rows.items()}
    return candidate_name, {
        "baseline": baseline,
        "target": target,
        "controls": control_rows,
        "target_gain": target_gain,
        "best_control_gain": max(control_gains.values()) if control_gains else 0.0,
        "margin_over_controls": target_gain - (max(control_gains.values()) if control_gains else 0.0),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--modes", default=",".join(ALL_FAMILIES))
    parser.add_argument("--seed", type=int, default=7001)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    results = {}
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        plan = MODE_PLAN[mode]
        mode_rows = {}
        jobs = list(plan["candidates"].items())
        if args.workers <= 1:
            for candidate_name, candidate_repl in jobs:
                name, row = evaluate_bundle(output_root, mode, candidate_name, candidate_repl, plan["target_fix"], plan["controls"], args.timeout, args.seed)
                mode_rows[name] = row
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                futures = [
                    pool.submit(evaluate_bundle, output_root, mode, candidate_name, candidate_repl, plan["target_fix"], plan["controls"], args.timeout, args.seed)
                    for candidate_name, candidate_repl in jobs
                ]
                for future in futures:
                    name, row = future.result()
                    mode_rows[name] = row
        best_candidate = max(mode_rows, key=lambda name: (mode_rows[name]["margin_over_controls"], mode_rows[name]["target_gain"]))
        results[mode] = {
            "candidates": mode_rows,
            "recommended_candidate": best_candidate,
            "recommended_score": mode_rows[best_candidate]["margin_over_controls"],
        }
    output_path = output_root / "init_diagnostics_report.json"
    output_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "modes": {mode: rows['recommended_candidate'] for mode, rows in results.items()}}, indent=2))


if __name__ == "__main__":
    main()
