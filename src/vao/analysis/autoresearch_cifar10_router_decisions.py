"""Run prompt-only worker-routing decisions for AutoResearch CIFAR-10 signals."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from benchmarks.autoresearch_cifar10.task_spec import ALL_WORKLOADS, WORKLOAD_REGISTRY, workload_template_path
from vao.orchestrator import _build_adapter, _load_model_configs
from vao.prompts import render_template

DEFAULT_WORKER_MENU = ["gpt_5_3_codex_spark", "gpt_5_3_codex", "gpt_5_4"]
SIGNALS = ["Z0", "Z1", "Z2", "Z3"]
CONTROLS = ["none", "shuffle_probe", "wrong_mode_probe", "synthetic_noise"]


def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_seeds(value: str | None) -> list[int | None]:
    if not value:
        return [None]
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metrics_from_run_dir(run_dir: Path) -> dict[str, Any] | None:
    metrics_path = run_dir / "verifier_raw" / "baseline" / "artifacts" / "candidate_metrics.json"
    if metrics_path.exists():
        return _load_json(metrics_path)
    summary_path = run_dir / "run_summary.json"
    if summary_path.exists():
        summary = _load_json(summary_path)
        return {
            "baseline_loss": summary.get("baseline_loss"),
            "best_visible_loss": summary.get("best_visible_loss"),
            "best_visible_relative_improvement": summary.get("best_visible_relative_improvement"),
            "success": summary.get("success"),
            "tau_step": summary.get("tau_step"),
            "elapsed_wall_seconds": summary.get("elapsed_wall_seconds"),
            "steps_completed": summary.get("steps_completed"),
        }
    return None


def _run_index(roots: list[Path]) -> dict[tuple[str, int | None], list[Path]]:
    index: dict[tuple[str, int | None], list[Path]] = {}
    for root in roots:
        for manifest_path in sorted(root.glob("**/run_manifest.json")):
            run_dir = manifest_path.parent
            manifest = _load_json(manifest_path)
            mode = manifest.get("task_mode_true")
            if not mode:
                overrides = (((manifest.get("config") or {}).get("benchmark") or {}).get("instance_overrides") or {})
                workloads = overrides.get("workloads") or overrides.get("families") or []
                mode = workloads[0] if len(workloads) == 1 else None
            if not mode:
                continue
            seed = manifest.get("instance_seed")
            index.setdefault((str(mode), int(seed) if seed is not None else None), []).append(run_dir)
    return index


def _baseline_metrics(index: dict[tuple[str, int | None], list[Path]], mode: str, seed: int | None) -> dict[str, Any] | None:
    for key in [(mode, seed), (mode, None)]:
        for run_dir in index.get(key, []):
            metrics = _metrics_from_run_dir(run_dir)
            if metrics:
                return metrics
    return None


def _scout_trace(index: dict[tuple[str, int | None], list[Path]], mode: str, seed: int | None, *, max_steps: int = 2) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in [(mode, seed), (mode, None)]:
        for run_dir in index.get(key, []):
            for step_path in sorted(run_dir.glob("steps/step_*/step_record.json"))[:max_steps]:
                record = _load_json(step_path)
                selected = next((branch for branch in record.get("branches", []) if branch.get("promoted_as_parent")), None)
                rows.append(
                    {
                        "step": record.get("step"),
                        "selected_mode": record.get("selected_mode"),
                        "successful_step": record.get("successful_step"),
                        "relative_improvement_so_far": record.get("relative_improvement_so_far"),
                        "step_wall_seconds": record.get("step_wall_seconds"),
                        "input_tokens": record.get("input_tokens"),
                        "output_tokens": record.get("output_tokens"),
                        "total_tokens": record.get("total_tokens"),
                        "selected_loss": selected.get("latent_loss") if selected else None,
                        "selected_elapsed_wall_seconds": selected.get("elapsed_wall_seconds") if selected else None,
                    }
                )
                if len(rows) >= max_steps:
                    return rows
    return rows


def _base_signal(signal: str, mode: str, seed: int | None, worker_menu: list[str], index: dict[tuple[str, int | None], list[Path]]) -> dict[str, Any]:
    spec = WORKLOAD_REGISTRY[mode]
    record: dict[str, Any] = {
        "signal_level": signal,
        "task_name": "autoresearch_cifar10",
        "checker_objective": "minimize CIFAR-10 validation loss; success is relative loss improvement >= 0.05",
        "horizon_steps": 20,
        "checker_budget_train_steps": int(spec["max_train_steps"]),
        "worker_menu": worker_menu,
        "instance": {
            "workload_id": mode,
            "seed": seed if seed is not None else spec.get("seed"),
        },
    }
    if signal in {"Z1", "Z2", "Z3"}:
        template_path = workload_template_path(mode)
        record["workload_summary"] = {
            "description": spec["description"],
            "architecture_name": spec["architecture_name"],
            "train_subset_size": spec["train_subset_size"],
            "val_subset_size": spec["val_subset_size"],
            "label_noise_rate": spec["label_noise_rate"],
            "imbalance_ratio": spec["imbalance_ratio"],
            "template_path": str(template_path),
        }
        record["initial_train_py"] = template_path.read_text(encoding="utf-8")
    if signal in {"Z2", "Z3"}:
        record["unmodified_baseline_probe"] = _baseline_metrics(index, mode, seed)
    if signal == "Z3":
        record["two_step_scout_trace"] = _scout_trace(index, mode, seed, max_steps=2)
    return record


def _control_signal(record: dict[str, Any], control: str, pool: list[dict[str, Any]], rng: random.Random) -> dict[str, Any]:
    copied = json.loads(json.dumps(record))
    copied["negative_control"] = control
    if control == "none":
        return copied
    if control in {"shuffle_probe", "wrong_mode_probe"} and pool:
        candidates = pool
        if copied.get("signal_level") in {"Z2", "Z3"}:
            candidates = [item for item in candidates if item.get("unmodified_baseline_probe") is not None]
        if copied.get("signal_level") == "Z3":
            candidates = [item for item in candidates if "two_step_scout_trace" in item]
        if control == "wrong_mode_probe":
            mode = copied.get("instance", {}).get("workload_id")
            candidates = [item for item in pool if item.get("instance", {}).get("workload_id") != mode] or pool
            if copied.get("signal_level") in {"Z2", "Z3"}:
                candidates = [item for item in candidates if item.get("unmodified_baseline_probe") is not None]
            if copied.get("signal_level") == "Z3":
                candidates = [item for item in candidates if "two_step_scout_trace" in item]
        candidates = candidates or pool
        donor = rng.choice(candidates)
        copied["unmodified_baseline_probe"] = donor.get("unmodified_baseline_probe")
        copied["two_step_scout_trace"] = donor.get("two_step_scout_trace", [])
        copied["control_source_instance"] = donor.get("instance")
        return copied
    if control == "synthetic_noise":
        copied["unmodified_baseline_probe"] = {
            "val_loss": round(rng.uniform(1.0, 2.5), 6),
            "val_accuracy": round(rng.uniform(0.1, 0.6), 4),
            "training_seconds": round(rng.uniform(1.0, 30.0), 2),
            "total_seconds": round(rng.uniform(5.0, 60.0), 2),
            "total_steps": copied.get("checker_budget_train_steps"),
            "param_count": int(rng.uniform(5_000, 200_000)),
            "success": rng.choice([True, False]),
        }
        copied["two_step_scout_trace"] = []
        return copied
    return copied


def _router_schema(worker_menu: list[str]) -> dict[str, Any]:
    worker_number_fields = {worker: {"type": ["number", "null"]} for worker in worker_menu}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "selected_worker": {"type": "string", "enum": worker_menu},
            "worker_ranking": {"type": "array", "items": {"type": "string", "enum": worker_menu}, "minItems": len(worker_menu), "maxItems": len(worker_menu)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "task_diagnosis": {"type": "string"},
            "evidence_used": {"type": "array", "items": {"type": "string"}},
            "expected_failure_mode": {"type": "string"},
            "expected_cost_risk": {"type": "string"},
            "success_probability_estimates": {
                "type": "object",
                "additionalProperties": False,
                "properties": worker_number_fields,
                "required": worker_menu,
            },
            "expected_cost_to_success": {
                "type": "object",
                "additionalProperties": False,
                "properties": worker_number_fields,
                "required": worker_menu,
            },
            "rationale": {"type": "string"},
        },
        "required": [
            "selected_worker",
            "worker_ranking",
            "confidence",
            "task_diagnosis",
            "evidence_used",
            "expected_failure_mode",
            "expected_cost_risk",
            "success_probability_estimates",
            "expected_cost_to_success",
            "rationale",
        ],
    }


def _validate_router_output(output: dict[str, Any], worker_menu: list[str]) -> list[str]:
    errors: list[str] = []
    selected = output.get("selected_worker")
    if selected not in worker_menu:
        errors.append(f"selected_worker_not_in_menu:{selected!r}")
    ranking = output.get("worker_ranking")
    if not isinstance(ranking, list) or sorted(ranking) != sorted(worker_menu):
        errors.append("worker_ranking_not_permutation")
    for key in ("success_probability_estimates", "expected_cost_to_success"):
        value = output.get(key)
        if not isinstance(value, dict):
            errors.append(f"{key}_not_object")
            continue
        missing = [worker for worker in worker_menu if worker not in value]
        if missing:
            errors.append(f"{key}_missing_workers:{','.join(missing)}")
    confidence = output.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0 <= float(confidence) <= 1):
        errors.append(f"confidence_out_of_range:{confidence!r}")
    return errors


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--router-model-key", default="gpt_5_4")
    parser.add_argument("--worker-menu", default=",".join(DEFAULT_WORKER_MENU))
    parser.add_argument("--workloads", default=",".join(ALL_WORKLOADS))
    parser.add_argument("--seeds", default=None)
    parser.add_argument("--signals", default=",".join(SIGNALS))
    parser.add_argument("--controls", default="none")
    parser.add_argument("--run-roots", nargs="*", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rng-seed", type=int, default=1729)
    args = parser.parse_args(argv)

    worker_menu = _parse_csv(args.worker_menu, DEFAULT_WORKER_MENU)
    workloads = _parse_csv(args.workloads, ALL_WORKLOADS)
    signals = _parse_csv(args.signals, SIGNALS)
    controls = _parse_csv(args.controls, ["none"])
    seeds = _parse_seeds(args.seeds)
    run_index = _run_index([Path(root) for root in args.run_roots])
    rng = random.Random(args.rng_seed)

    base_records = [_base_signal(signal, mode, seed, worker_menu, run_index) for mode in workloads for seed in seeds for signal in signals]
    model_configs = _load_model_configs()
    adapter = None if args.dry_run else _build_adapter(model_configs[args.router_model_key])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in base_records:
            for control in controls:
                routed_record = _control_signal(record, control, base_records, rng)
                row: dict[str, Any] = {
                    "router_model_key": args.router_model_key,
                    "worker_menu": worker_menu,
                    "signal_level": routed_record["signal_level"],
                    "negative_control": control,
                    "instance": routed_record["instance"],
                    "signal_record": routed_record,
                }
                if not args.dry_run:
                    prompt = render_template(
                        "autoresearch_router.txt",
                        worker_menu=json.dumps(worker_menu, sort_keys=True),
                        signal_record=json.dumps(routed_record, sort_keys=True),
                    )
                    started = time.perf_counter()
                    raw, meta = adapter._complete(prompt, _router_schema(worker_menu), 4096)  # type: ignore[attr-defined]
                    router_output = json.loads(raw)
                    validation_errors = _validate_router_output(router_output, worker_menu)
                    if validation_errors:
                        raise RuntimeError("router_output_validation_failed:" + ";".join(validation_errors))
                    row.update(
                        {
                            "router_prompt": prompt,
                            "router_raw_output": raw,
                            "router_output": router_output,
                            "router_output_validation_errors": validation_errors,
                            "router_meta": meta,
                            "router_wall_seconds": time.perf_counter() - started,
                        }
                    )
                handle.write(json.dumps(row, sort_keys=True, allow_nan=True) + "\n")
    print(json.dumps({"output": str(output), "records": len(base_records) * len(controls), "dry_run": args.dry_run}, indent=2))


if __name__ == "__main__":
    main()
