"""Run candidate-agent-model selection decisions for CIFAR-10 signals."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from autoresearch.benchmark.cifar10.task_spec import ALL_WORKLOADS, WORKLOAD_REGISTRY, workload_template_path
from vao.orchestrator import _build_adapter, _load_model_configs
from vao.prompts import render_template

DEFAULT_WORKER_MENU = ["gpt_5_3_codex", "gpt_5_4", "gpt_5_4_mini"]
SIGNALS = ["Z0", "Z1", "Z2"]
CONTROLS = ["none", "shuffle_probe", "wrong_mode_probe", "synthetic_noise"]
SUCCESS_THRESHOLD_RELATIVE = 0.05
MODE_SCHEMA = {
    "mlp_flat": {
        "short_name": "MLP",
        "description": "flat multilayer perceptron starting architecture",
    },
    "cnn_compact": {
        "short_name": "CNN",
        "description": "compact convolutional starting architecture",
    },
    "resnet_micro": {
        "short_name": "ResNet",
        "description": "small residual-network starting architecture",
    },
}

RunIndex = dict[tuple[str, int | None, str | None], list[Path]]


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


def _model_alias_from_manifest(manifest: dict[str, Any]) -> str | None:
    alias = manifest.get("model_alias")
    if alias:
        return str(alias)
    included = (((manifest.get("config") or {}).get("models") or {}).get("include") or [])
    if len(included) == 1:
        return str(included[0])
    return None


def _run_index(roots: list[Path]) -> RunIndex:
    index: RunIndex = {}
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
            seed_value = int(seed) if seed is not None else None
            model_alias = _model_alias_from_manifest(manifest)
            index.setdefault((str(mode), seed_value, model_alias), []).append(run_dir)
            index.setdefault((str(mode), seed_value, None), []).append(run_dir)
    return index


def _baseline_metrics(index: RunIndex, mode: str, seed: int | None) -> dict[str, Any] | None:
    for key in [(mode, seed, None), (mode, None, None)]:
        for run_dir in index.get(key, []):
            metrics = _metrics_from_run_dir(run_dir)
            if metrics:
                return metrics
    return None


def _sum_number(rows: list[dict[str, Any]], key: str) -> float | int | None:
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    if not values:
        return None
    total = sum(values)
    return int(total) if all(isinstance(value, int) for value in values) else total


def _candidate_scout_result(
    run_dir: Path,
    *,
    max_steps: int,
    success_threshold: float,
    hide_mode_labels: bool = False,
) -> dict[str, Any]:
    manifest_path = run_dir / "run_manifest.json"
    summary_path = run_dir / "run_summary.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    summary = _load_json(summary_path) if summary_path.exists() else {}
    steps: list[dict[str, Any]] = []
    for step_path in sorted(run_dir.glob("steps/step_*/step_record.json"))[:max_steps]:
        record = _load_json(step_path)
        selected = next((branch for branch in record.get("branches", []) if branch.get("promoted_as_parent")), None)
        selected_loss = selected.get("latent_loss") if selected else None
        steps.append(
            {
                "step": record.get("step"),
                "selected_mode": record.get("selected_mode"),
                "successful_step": record.get("successful_step"),
                "relative_improvement_so_far": record.get("relative_improvement_so_far"),
                "best_visible_loss_so_far": record.get("best_visible_so_far"),
                "parent_loss": record.get("parent_latent_loss"),
                "selected_loss": selected_loss,
                "selected_correctness": selected.get("correctness") if selected else None,
                "selected_elapsed_wall_seconds": selected.get("elapsed_wall_seconds") if selected else None,
                "validation_failures": selected.get("validation_failures") if selected else None,
                "step_wall_seconds": record.get("step_wall_seconds"),
                "input_tokens": record.get("input_tokens"),
                "output_tokens": record.get("output_tokens"),
                "total_tokens": record.get("total_tokens"),
                "agent_cost_usd": record.get("agent_cost_usd"),
                "interactive_error_count": len(record.get("errors") or []),
            }
        )
    improvements = [
        step.get("relative_improvement_so_far")
        for step in steps
        if isinstance(step.get("relative_improvement_so_far"), (int, float))
    ]
    best_losses = [
        step.get("best_visible_loss_so_far")
        for step in steps
        if isinstance(step.get("best_visible_loss_so_far"), (int, float))
    ]
    best_improvement = max(improvements) if improvements else None
    return {
        "candidate_agent_model": _model_alias_from_manifest(manifest),
        "model_id": manifest.get("model_id") or summary.get("model_id"),
        "source_run_id": None if hide_mode_labels else (manifest.get("run_id") or summary.get("run_id") or run_dir.name),
        "missing": False,
        "scout_steps_completed": len(steps),
        "scout_budget_steps": max_steps,
        "baseline_loss": summary.get("baseline_loss") or (steps[0].get("parent_loss") if steps else None),
        "best_visible_loss_within_scout": min(best_losses) if best_losses else None,
        "best_relative_improvement_within_scout": best_improvement,
        "success_within_scout": bool(best_improvement is not None and best_improvement >= success_threshold),
        "valid_selected_steps": sum(1 for step in steps if step.get("selected_correctness") is True),
        "interactive_error_count": sum(int(step.get("interactive_error_count") or 0) for step in steps),
        "total_scout_wall_seconds": _sum_number(steps, "step_wall_seconds"),
        "total_input_tokens": _sum_number(steps, "input_tokens"),
        "total_output_tokens": _sum_number(steps, "output_tokens"),
        "total_tokens": _sum_number(steps, "total_tokens"),
        "total_agent_cost_usd": _sum_number(steps, "agent_cost_usd"),
        "step_trace": steps,
    }


def _candidate_agent_scouts(
    index: RunIndex,
    mode: str,
    seed: int | None,
    candidate_agent_models: list[str],
    *,
    max_steps: int = 2,
    success_threshold: float = SUCCESS_THRESHOLD_RELATIVE,
    hide_mode_labels: bool = False,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for candidate in candidate_agent_models:
        run_dirs: list[Path] = []
        for key in [(mode, seed, candidate), (mode, None, candidate)]:
            run_dirs.extend(index.get(key, []))
        if not run_dirs:
            results[candidate] = {
                "candidate_agent_model": candidate,
                "missing": True,
                "scout_steps_completed": 0,
                "scout_budget_steps": max_steps,
                "reason": "no_matching_scout_run",
            }
            continue
        result = _candidate_scout_result(
            run_dirs[0],
            max_steps=max_steps,
            success_threshold=success_threshold,
            hide_mode_labels=hide_mode_labels,
        )
        result["candidate_agent_model"] = candidate
        results[candidate] = result
    return {
        "type": "candidate_agent_model_scout",
        "description": "Each candidate agent model was run for a small fixed prefix of the edit-verify horizon on this task instance; only prefix-scout measurements are visible to the router.",
        "scout_budget_steps": max_steps,
        "horizon_steps": 20,
        "success_threshold_relative": success_threshold,
        "transferable_to_selected_agent_model": False,
        "full_horizon_results_visible": False,
        "results": results,
    }


def _base_signal(
    signal: str,
    mode: str,
    seed: int | None,
    worker_menu: list[str],
    index: RunIndex,
    *,
    scout_steps: int = 2,
    router_contract: str = "direct",
    hide_mode_labels: bool = False,
) -> dict[str, Any]:
    spec = WORKLOAD_REGISTRY[mode]
    instance_id = f"seed_{seed if seed is not None else spec.get('seed')}"
    record: dict[str, Any] = {
        "signal_level": signal,
        "task_name": "cifar10_code_editing_optimization",
        "task_contract": {
            "objective": "minimize CIFAR-10 validation loss",
            "success_rule": f"relative validation-loss improvement >= {SUCCESS_THRESHOLD_RELATIVE}",
            "horizon_steps": 20,
            "checker_budget_train_steps": int(spec["max_train_steps"]),
        },
        "candidate_agent_models": worker_menu,
        "instance": {
            "instance_id": instance_id,
            "seed": seed if seed is not None else spec.get("seed"),
        },
    }
    if not hide_mode_labels:
        record["instance"]["workload_id"] = mode
        record["instance"]["starting_architecture_id"] = mode
    if router_contract == "allocation":
        record["mode_schema"] = MODE_SCHEMA
    # Keep legacy top-level fields for existing analysis utilities.
    record["checker_objective"] = f"minimize CIFAR-10 validation loss; success is relative loss improvement >= {SUCCESS_THRESHOLD_RELATIVE}"
    record["horizon_steps"] = record["task_contract"]["horizon_steps"]
    record["checker_budget_train_steps"] = record["task_contract"]["checker_budget_train_steps"]
    if signal in {"Z1", "Z2", "Z3"}:
        template_path = workload_template_path(mode)
        record["initial_trainable_model"] = {
            "train_subset_size": spec["train_subset_size"],
            "val_subset_size": spec["val_subset_size"],
            "label_noise_rate": spec["label_noise_rate"],
            "imbalance_ratio": spec["imbalance_ratio"],
        }
        if not hide_mode_labels:
            record["initial_trainable_model"].update(
                {
                    "architecture_tag": mode,
                    "description": spec["description"],
                    "architecture_name": spec["architecture_name"],
                    "template_path": str(template_path),
                }
            )
        record["workload_summary"] = record["initial_trainable_model"]
        record["initial_train_py"] = template_path.read_text(encoding="utf-8")
    if signal in {"Z2", "Z3"}:
        record["candidate_agent_scouts"] = _candidate_agent_scouts(
            index,
            mode,
            seed,
            worker_menu,
            max_steps=scout_steps,
            success_threshold=SUCCESS_THRESHOLD_RELATIVE,
            hide_mode_labels=hide_mode_labels,
        )
    return record


def _control_signal(record: dict[str, Any], control: str, pool: list[dict[str, Any]], rng: random.Random) -> dict[str, Any]:
    copied = json.loads(json.dumps(record))
    copied["negative_control"] = control
    if control == "none":
        return copied
    if control in {"shuffle_probe", "wrong_mode_probe"} and pool:
        candidates = pool
        if copied.get("signal_level") in {"Z2", "Z3"}:
            candidates = [item for item in candidates if item.get("candidate_agent_scouts")]
        if control == "wrong_mode_probe":
            mode = copied.get("instance", {}).get("workload_id")
            candidates = [item for item in pool if item.get("instance", {}).get("workload_id") != mode] or pool
            if copied.get("signal_level") in {"Z2", "Z3"}:
                candidates = [item for item in candidates if item.get("candidate_agent_scouts")]
        candidates = candidates or pool
        donor = rng.choice(candidates)
        copied["candidate_agent_scouts"] = donor.get("candidate_agent_scouts")
        copied["control_source_instance"] = donor.get("instance")
        return copied
    if control == "synthetic_noise":
        copied["candidate_agent_scouts"] = {
            "type": "candidate_agent_model_scout",
            "description": "Synthetic control values; not real scout evidence.",
            "scout_budget_steps": 2,
            "horizon_steps": copied.get("horizon_steps"),
            "success_threshold_relative": SUCCESS_THRESHOLD_RELATIVE,
            "transferable_to_selected_agent_model": False,
            "full_horizon_results_visible": False,
            "results": {
                candidate: {
                    "candidate_agent_model": candidate,
                    "missing": False,
                    "scout_steps_completed": 2,
                    "scout_budget_steps": 2,
                    "baseline_loss": round(rng.uniform(1.0, 2.5), 6),
                    "best_visible_loss_within_scout": round(rng.uniform(0.8, 2.4), 6),
                    "best_relative_improvement_within_scout": round(rng.uniform(0.0, 0.2), 6),
                    "success_within_scout": rng.choice([True, False]),
                    "total_scout_wall_seconds": round(rng.uniform(10.0, 120.0), 2),
                    "total_tokens": int(rng.uniform(20_000, 150_000)),
                    "interactive_error_count": int(rng.uniform(0, 3)),
                    "step_trace": [],
                }
                for candidate in copied.get("candidate_agent_models", [])
            },
        }
        return copied
    return copied


def _router_schema(worker_menu: list[str], *, router_contract: str = "direct") -> dict[str, Any]:
    model_number_fields = {worker: {"type": ["number", "null"]} for worker in worker_menu}
    if router_contract == "allocation":
        mode_number_fields = {mode: {"type": "number", "minimum": 0, "maximum": 1} for mode in MODE_SCHEMA}
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "selected_agent_model": {"type": "string", "enum": worker_menu},
                "agent_model_ranking": {
                    "type": "array",
                    "items": {"type": "string", "enum": worker_menu},
                    "minItems": len(worker_menu),
                    "maxItems": len(worker_menu),
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "mode_posterior": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": mode_number_fields,
                    "required": list(MODE_SCHEMA),
                },
                "mode_allocation": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": mode_number_fields,
                    "required": list(MODE_SCHEMA),
                },
                "agent_system_scores": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": model_number_fields,
                    "required": worker_menu,
                },
                "success_probability_estimates": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": model_number_fields,
                    "required": worker_menu,
                },
                "expected_cost_to_success": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": model_number_fields,
                    "required": worker_menu,
                },
                "task_diagnosis": {"type": "string"},
                "mode_evidence": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {mode: {"type": "string"} for mode in MODE_SCHEMA},
                    "required": list(MODE_SCHEMA),
                },
                "evidence_used": {"type": "array", "items": {"type": "string"}},
                "expected_failure_mode": {"type": "string"},
                "expected_cost_risk": {"type": "string"},
                "allocation_rationale": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": [
                "selected_agent_model",
                "agent_model_ranking",
                "confidence",
                "mode_posterior",
                "mode_allocation",
                "agent_system_scores",
                "success_probability_estimates",
                "expected_cost_to_success",
                "task_diagnosis",
                "mode_evidence",
                "evidence_used",
                "expected_failure_mode",
                "expected_cost_risk",
                "allocation_rationale",
                "rationale",
            ],
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "selected_agent_model": {"type": "string", "enum": worker_menu},
            "agent_model_ranking": {"type": "array", "items": {"type": "string", "enum": worker_menu}, "minItems": len(worker_menu), "maxItems": len(worker_menu)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "task_diagnosis": {"type": "string"},
            "evidence_used": {"type": "array", "items": {"type": "string"}},
            "expected_failure_mode": {"type": "string"},
            "expected_cost_risk": {"type": "string"},
            "success_probability_estimates": {
                "type": "object",
                "additionalProperties": False,
                "properties": model_number_fields,
                "required": worker_menu,
            },
            "expected_cost_to_success": {
                "type": "object",
                "additionalProperties": False,
                "properties": model_number_fields,
                "required": worker_menu,
            },
            "rationale": {"type": "string"},
        },
        "required": [
            "selected_agent_model",
            "agent_model_ranking",
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


def _validate_probability_vector(value: Any, keys: list[str], name: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{name}_not_object")
        return
    missing = [key for key in keys if key not in value]
    if missing:
        errors.append(f"{name}_missing_keys:{','.join(missing)}")
        return
    total = 0.0
    for key in keys:
        number = value.get(key)
        if not isinstance(number, (int, float)) or number < 0 or number > 1:
            errors.append(f"{name}_{key}_out_of_range:{number!r}")
            return
        total += float(number)
    if abs(total - 1.0) > 0.02:
        errors.append(f"{name}_sum_not_one:{total:.6f}")


def _validate_router_output(output: dict[str, Any], worker_menu: list[str], *, router_contract: str = "direct") -> list[str]:
    errors: list[str] = []
    selected = output.get("selected_agent_model")
    if selected not in worker_menu:
        errors.append(f"selected_agent_model_not_in_menu:{selected!r}")
    ranking = output.get("agent_model_ranking")
    if not isinstance(ranking, list) or sorted(ranking) != sorted(worker_menu):
        errors.append("agent_model_ranking_not_permutation")
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
    if router_contract == "allocation":
        _validate_probability_vector(output.get("mode_posterior"), list(MODE_SCHEMA), "mode_posterior", errors)
        _validate_probability_vector(output.get("mode_allocation"), list(MODE_SCHEMA), "mode_allocation", errors)
        scores = output.get("agent_system_scores")
        if not isinstance(scores, dict):
            errors.append("agent_system_scores_not_object")
        else:
            missing = [worker for worker in worker_menu if worker not in scores]
            if missing:
                errors.append(f"agent_system_scores_missing_workers:{','.join(missing)}")
    return errors


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--router-model-key", default="gpt_5_4")
    parser.add_argument("--candidate-agent-models", default=None)
    parser.add_argument("--worker-menu", default=None, help="Deprecated alias for --candidate-agent-models.")
    parser.add_argument("--workloads", default=",".join(ALL_WORKLOADS))
    parser.add_argument("--seeds", default=None)
    parser.add_argument("--signals", default=",".join(SIGNALS))
    parser.add_argument("--controls", default="none")
    parser.add_argument("--run-roots", nargs="*", default=[])
    parser.add_argument("--scout-steps", type=int, default=2)
    parser.add_argument("--router-contract", choices=["direct", "allocation"], default="direct")
    parser.add_argument("--prompt-template", default=None)
    parser.add_argument("--hide-mode-labels", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rng-seed", type=int, default=1729)
    args = parser.parse_args(argv)

    worker_menu = _parse_csv(args.candidate_agent_models or args.worker_menu, DEFAULT_WORKER_MENU)
    workloads = _parse_csv(args.workloads, ALL_WORKLOADS)
    signals = _parse_csv(args.signals, SIGNALS)
    controls = _parse_csv(args.controls, ["none"])
    seeds = _parse_seeds(args.seeds)
    run_index = _run_index([Path(root) for root in args.run_roots])
    rng = random.Random(args.rng_seed)

    base_records = [
        {
            "true_mode": mode,
            "record": _base_signal(
                signal,
                mode,
                seed,
                worker_menu,
                run_index,
                scout_steps=args.scout_steps,
                router_contract=args.router_contract,
                hide_mode_labels=args.hide_mode_labels,
            ),
        }
        for mode in workloads
        for seed in seeds
        for signal in signals
    ]
    model_configs = _load_model_configs()
    adapter = None if args.dry_run else _build_adapter(model_configs[args.router_model_key])
    prompt_template = args.prompt_template or (
        "autoresearch_allocation_router.txt" if args.router_contract == "allocation" else "autoresearch_router.txt"
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for base in base_records:
            record = base["record"]
            for control in controls:
                routed_record = _control_signal(record, control, [item["record"] for item in base_records], rng)
                row: dict[str, Any] = {
                    "router_model_key": args.router_model_key,
                    "router_contract": args.router_contract,
                    "candidate_agent_models": worker_menu,
                    "signal_level": routed_record["signal_level"],
                    "negative_control": control,
                    "true_mode": base["true_mode"],
                    "instance": routed_record["instance"],
                    "signal_record": routed_record,
                }
                if not args.dry_run:
                    prompt = render_template(
                        prompt_template,
                        candidate_agent_models=json.dumps(worker_menu, sort_keys=True),
                        mode_schema=json.dumps(MODE_SCHEMA, sort_keys=True),
                        signal_record=json.dumps(routed_record, sort_keys=True),
                    )
                    started = time.perf_counter()
                    raw, meta = adapter._complete(prompt, _router_schema(worker_menu, router_contract=args.router_contract), 4096)  # type: ignore[attr-defined]
                    router_output = json.loads(raw)
                    validation_errors = _validate_router_output(router_output, worker_menu, router_contract=args.router_contract)
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
