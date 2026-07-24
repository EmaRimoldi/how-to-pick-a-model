"""Meta-orchestrator update pass for SWE-bench hierarchical experiments."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from vao.agents.codex_cli_adapter import CodexCliAdapter
from vao.swebench_orchestration.schemas import OrchestrationDesign, OrchestrationSpec


class ExecutorConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_literal_repair_enabled: bool | None = None
    patch_repair_attempts: int | None = Field(default=None, ge=0, le=5)
    max_calls_per_component: int | None = Field(default=None, ge=1, le=5)


class MetaUpdateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_update_id: str
    source_run_id: str
    target_orchestration_id: str
    failure_diagnosis: list[str]
    proposed_changes: list[str]
    executor_config_patch: ExecutorConfigPatch = Field(default_factory=ExecutorConfigPatch)
    updated_hierarchical_orchestration: OrchestrationSpec
    expected_effect: str
    leakage_safety_notes: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_failure_bundle(
    *,
    executor_dir: Path,
    evaluation_manifest_path: Path | None,
) -> dict[str, Any]:
    traces = read_jsonl(executor_dir / "traces.jsonl")
    predictions = read_jsonl(executor_dir / "predictions.jsonl")
    manifest = read_json(executor_dir / "executor_manifest.json")
    evaluation_manifest = read_json(evaluation_manifest_path)
    return {
        "executor_manifest": _compact_executor_manifest(manifest),
        "public_instances": _public_instances_from_manifest(manifest, predictions),
        "prediction_summary": _summarize_predictions(predictions),
        "trace_summary": _summarize_traces(traces),
        "four_term_diagnostics": _four_term_diagnostics(traces, predictions, evaluation_manifest),
        "evaluation_summary": _summarize_evaluation(evaluation_manifest),
        "selected_trace_events": _selected_trace_events(traces),
        "repo_context_artifacts": _repo_context_artifacts(traces),
    }


def render_update_prompt(
    *,
    design: OrchestrationDesign,
    orchestration_id: str,
    failure_bundle: dict[str, Any],
    config: dict[str, Any],
) -> str:
    orchestration = _select_hierarchical(design, orchestration_id)
    experiment = config.get("experiment", {})
    meta = config.get("meta_designer", {})
    worker_models = config.get("worker_models", [])
    allowed_tools = list(config.get("allowed_tools", []))
    executor_capabilities = {
        "patch_apply_check": "Local git apply --check gate before any official verifier call.",
        "patch_repair_attempts": "Small retry budget after apply-check failure.",
        "public_literal_repair": (
            "Optional deterministic tool policy. It may synthesize a unified diff only from "
            "public issue backtick literals plus leakage-safe repository context. It is used "
            "only if the updated hierarchical design explicitly names the policy."
        ),
        "official_modal_verifier": "Official SWE-bench harness through Modal, outside the executor.",
    }
    return "\n\n".join(
        [
            "You are the Meta-Orchestrator update pass for a SWE-bench orchestration experiment.",
            "Your job is not to solve the SWE-bench instance directly. Your job is to update the active hierarchical orchestration policy based on observed failures, trace logs, and verifier output.",
            f"Meta model configured for this pass: {meta.get('model_id', 'unspecified')}",
            f"Benchmark: {experiment.get('dataset_name', 'princeton-nlp/SWE-Bench_Verified')}",
            f"Split: {experiment.get('split', 'test')}",
            "Only one orchestration may be active in the next executor run: the hierarchical routed orchestration named below. Keep universal and specialist families out of execution.",
            f"Target hierarchical orchestration id: {orchestration_id}",
            "Allowed worker models:",
            json.dumps(worker_models, indent=2, sort_keys=True),
            "Allowed tools from the initial experiment config:",
            json.dumps(allowed_tools, indent=2, sort_keys=True),
            "Executor capabilities available for the updated design:",
            json.dumps(executor_capabilities, indent=2, sort_keys=True),
            "Current hierarchical orchestration JSON:",
            json.dumps(orchestration.model_dump(mode='json'), indent=2, sort_keys=True),
            "Observed failure bundle:",
            json.dumps(failure_bundle, indent=2, sort_keys=True),
            "Update constraints:",
            "- Use only public issue text, leakage-safe repo context, executor traces, local apply-check output, and official verifier feedback.",
            "- Do not use gold patches, hidden tests, or post-hoc private solution fields.",
            "- The next pass should optimize local candidate quality first: increase non-empty and local apply-check-passed patches, reduce invalid diffs and empty patcher outputs, and avoid spending additional official Modal verifier calls until local metrics improve.",
            "- Use the four_term_diagnostics block mechanistically: map solution cost, retries/stopping, information loss, and mode/allocation mismatch to concrete changes in routing, context handoff, patch contracts, fallback triggers, and deterministic-tool gating.",
            "- If failures show that a deterministic public-literal tool is warranted, explicitly name `public_literal_repair` in the updated patch/fallback policy or component tools.",
            "- If failures instead point to model prompting, context, retry, or routing, update those policies without enabling unrelated tools.",
            "- Preserve the same target orchestration id unless there is a strong reason to version it in the name.",
            "- Return one updated hierarchical OrchestrationSpec plus a small executor_config_patch.",
            "Return only JSON matching the provided schema.",
        ]
    )


def invoke_meta_update(
    *,
    prompt: str,
    model_id: str,
    reasoning_effort: str,
    timeout_seconds: int,
) -> tuple[MetaUpdateProposal, dict[str, Any], dict[str, Any]]:
    adapter = CodexCliAdapter(
        model_id=model_id,
        reasoning_effort=reasoning_effort,
        timeout_seconds=timeout_seconds,
        use_output_schema=False,
        sandbox="read-only",
    )
    raw, usage = adapter._complete(prompt, MetaUpdateProposal.model_json_schema(), max_tokens=12000)
    payload = _parse_json_object(raw)
    proposal = MetaUpdateProposal.model_validate(payload)
    return proposal, payload, usage


def materialize_updated_design(
    *,
    design: OrchestrationDesign,
    proposal: MetaUpdateProposal,
    orchestration_id: str,
) -> OrchestrationDesign:
    updated_orchestration = proposal.updated_hierarchical_orchestration
    if updated_orchestration.orchestration_type != "hierarchical_routed":
        raise ValueError("Meta update must return a hierarchical_routed orchestration.")
    if updated_orchestration.orchestration_id != orchestration_id:
        raise ValueError(
            "Updated orchestration id does not match target: "
            f"{updated_orchestration.orchestration_id!r} != {orchestration_id!r}"
        )

    payload = design.model_dump(mode="json")
    replaced = False
    if payload["orchestration"]["orchestration_id"] == orchestration_id:
        payload["orchestration"] = updated_orchestration.model_dump(mode="json")
        replaced = True
    if not replaced:
        raise KeyError(f"Unknown orchestration_id {orchestration_id!r}")
    payload["design_id"] = f"{payload['design_id']}__{_safe_id(proposal.design_update_id)}"
    payload["assumptions"] = [
        *payload.get("assumptions", []),
        "Hierarchical policy was updated by a meta-orchestrator pass using executor traces and verifier feedback.",
    ]
    payload["logging_plan"] = [
        *payload.get("logging_plan", []),
        "Record meta_update.json, executor_config_patch.json, and updated hierarchical design for each update cycle.",
    ]
    return OrchestrationDesign.model_validate(payload)


def apply_executor_config_patch(config: dict[str, Any], proposal: MetaUpdateProposal, *, design_path: Path) -> dict[str, Any]:
    updated = json.loads(json.dumps(config))
    executor = dict(updated.get("executor") or {})
    patch = proposal.executor_config_patch.model_dump(exclude_none=True)
    for key, value in patch.items():
        executor[key] = value
    executor["design"] = str(design_path)
    executor["orchestration_id"] = proposal.target_orchestration_id
    updated["executor"] = executor
    return updated


def _compact_executor_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "run_id",
        "orchestration_id",
        "instances",
        "max_calls_per_component",
        "patch_repair_attempts",
        "public_literal_repair_enabled",
        "repo_context_enabled",
        "instances_path",
        "predictions_path",
        "traces_path",
    ]
    return {key: manifest.get(key) for key in keys if key in manifest}


def _public_instances_from_manifest(
    manifest: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    path_value = manifest.get("instances_path")
    if not path_value:
        return []
    path = Path(str(path_value))
    if not path.exists():
        return []
    wanted = {str(row.get("instance_id")) for row in predictions if row.get("instance_id")}
    rows = []
    for row in read_jsonl(path):
        instance_id = str(row.get("instance_id") or "")
        if wanted and instance_id not in wanted:
            continue
        rows.append(_safe_public_instance(row))
    return rows[:8]


def _summarize_predictions(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for row in predictions:
        patch = str(row.get("model_patch") or "")
        rows.append(
            {
                "instance_id": row.get("instance_id"),
                "model_name_or_path": row.get("model_name_or_path"),
                "patch_chars": len(patch),
                "patch_nonempty": bool(patch.strip()),
                "modified_files": _modified_files_from_patch(patch),
            }
        )
    return {
        "rows": len(predictions),
        "nonempty_patch_count": sum(1 for row in rows if row["patch_nonempty"]),
        "predictions": rows,
    }


def _summarize_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    phases = Counter(str(row.get("phase") or "unknown") for row in traces)
    errors = [str(row.get("error")) for row in traces if row.get("error")]
    patch_empty = Counter(
        str(row.get("patch_empty_reason") or "missing")
        for row in traces
        if row.get("phase") in {"patch", "fallback"}
    )
    apply_checks = [
        {
            "step": row.get("step"),
            "agent_id": row.get("agent_id"),
            "status": (row.get("patch_apply_check") or {}).get("status"),
            "reason": (row.get("patch_apply_check") or {}).get("reason"),
        }
        for row in traces
        if isinstance(row.get("patch_apply_check"), dict)
    ]
    verify_steps = [row for row in traces if row.get("phase") == "verify"]
    return {
        "trace_steps": len(traces),
        "phase_counts": dict(phases),
        "error_count": len(errors),
        "error_previews": errors[:8],
        "patch_empty_reason_counts": dict(patch_empty),
        "patch_apply_checks": apply_checks[-8:],
        "verify_steps": [
            {
                "step": row.get("step"),
                "error": row.get("error"),
                "stopping_reason": row.get("stopping_reason"),
                "selected_patch_chars": row.get("selected_patch_chars"),
                "invalid_patch_count": row.get("invalid_patch_count"),
                "selected_patch_modified_files": row.get("selected_patch_modified_files"),
            }
            for row in verify_steps[-4:]
        ],
    }


def _four_term_diagnostics(
    traces: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    evaluation_manifest: dict[str, Any],
) -> dict[str, Any]:
    trace_by_instance: dict[str, list[dict[str, Any]]] = {}
    for row in traces:
        instance_id = str(row.get("instance_id") or "")
        if instance_id:
            trace_by_instance.setdefault(instance_id, []).append(row)

    prediction_by_instance = {
        str(row.get("instance_id")): row
        for row in predictions
        if row.get("instance_id")
    }
    report = evaluation_manifest.get("report") if isinstance(evaluation_manifest.get("report"), dict) else {}
    resolved_ids = set(str(item) for item in report.get("resolved_ids", []) or [])
    unresolved_ids = set(str(item) for item in report.get("unresolved_ids", []) or [])
    error_ids = set(str(item) for item in report.get("error_ids", []) or [])

    instance_rows: list[dict[str, Any]] = []
    for instance_id, rows in sorted(trace_by_instance.items()):
        prediction = prediction_by_instance.get(instance_id, {})
        patch = str(prediction.get("model_patch") or "")
        apply_statuses = [
            str((row.get("patch_apply_check") or {}).get("status"))
            for row in rows
            if isinstance(row.get("patch_apply_check"), dict)
        ]
        nonempty_attempts = [
            row
            for row in rows
            if (row.get("payload_summary") or {}).get("model_patch_nonempty") is True
        ]
        passed_apply_steps = [
            int(row.get("step") or 0)
            for row in rows
            if isinstance(row.get("patch_apply_check"), dict)
            and (row.get("patch_apply_check") or {}).get("status") == "passed"
        ]
        mode = _most_common([str(row.get("mode") or "unknown") for row in rows])
        input_tokens = sum(int(row.get("input_tokens") or 0) for row in rows)
        output_tokens = sum(int(row.get("output_tokens") or 0) for row in rows)
        wall_seconds = sum(float(row.get("wall_seconds") or 0.0) for row in rows)
        patch_empty_reasons = [
            str(row.get("patch_empty_reason"))
            for row in rows
            if row.get("phase") in {"patch", "fallback"} and row.get("patch_empty_reason")
        ]
        repo_ready = any(row.get("repo_context_status") == "ready" for row in rows)
        candidate_files = sorted(
            {
                str(item)
                for row in rows
                for item in (row.get("repo_context_candidate_files") or [])
            }
        )[:12]
        selected_files = _modified_files_from_patch(patch)
        information_loss_flags = []
        if repo_ready and not patch.strip():
            information_loss_flags.append("repo_context_ready_but_final_patch_empty")
        if candidate_files and selected_files and not set(candidate_files).intersection(selected_files):
            information_loss_flags.append("patch_touches_no_repo_context_candidate_file")
        if "failed" in apply_statuses:
            information_loss_flags.append("nonempty_candidate_lost_to_apply_failure")

        instance_rows.append(
            {
                "instance_id": instance_id,
                "mode": mode,
                "final_patch_nonempty": bool(patch.strip()),
                "final_patch_chars": len(patch),
                "final_patch_modified_files": selected_files,
                "nonempty_attempt_count": len(nonempty_attempts),
                "apply_check_statuses": apply_statuses,
                "apply_check_passed": "passed" in apply_statuses,
                "first_apply_pass_step": min(passed_apply_steps) if passed_apply_steps else None,
                "resolved": instance_id in resolved_ids,
                "unresolved": instance_id in unresolved_ids,
                "evaluation_error": instance_id in error_ids,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "wall_seconds": wall_seconds,
                "patch_empty_reasons": patch_empty_reasons[:6],
                "information_loss_flags": information_loss_flags,
            }
        )

    total = max(len(predictions), 1)
    final_nonempty = [row for row in instance_rows if row["final_patch_nonempty"]]
    apply_passed = [row for row in instance_rows if row["apply_check_passed"]]
    by_mode: dict[str, dict[str, Any]] = {}
    for mode in sorted({str(row["mode"]) for row in instance_rows}):
        rows = [row for row in instance_rows if row["mode"] == mode]
        by_mode[mode] = {
            "instances": len(rows),
            "final_nonempty": sum(1 for row in rows if row["final_patch_nonempty"]),
            "apply_check_passed": sum(1 for row in rows if row["apply_check_passed"]),
            "resolved": sum(1 for row in rows if row["resolved"]),
            "mean_total_tokens": _mean([float(row["total_tokens"]) for row in rows]),
            "mean_wall_seconds": _mean([float(row["wall_seconds"]) for row in rows]),
        }

    return {
        "solution_generation_cost": {
            "instances": len(predictions),
            "input_tokens": sum(int(row.get("input_tokens") or 0) for row in traces),
            "output_tokens": sum(int(row.get("output_tokens") or 0) for row in traces),
            "wall_seconds": sum(float(row.get("wall_seconds") or 0.0) for row in traces),
            "final_nonempty_patch_count": len(final_nonempty),
            "apply_check_passed_count": len(apply_passed),
            "tokens_per_final_nonempty_patch": (
                sum(row["total_tokens"] for row in instance_rows) / len(final_nonempty)
                if final_nonempty
                else None
            ),
            "tokens_per_apply_check_passed_patch": (
                sum(row["total_tokens"] for row in instance_rows) / len(apply_passed)
                if apply_passed
                else None
            ),
        },
        "retries_to_verified_success": {
            "resolved_count": len(resolved_ids),
            "resolved_ids": sorted(resolved_ids),
            "official_stopping_time_observed": bool(resolved_ids),
            "local_apply_stopping_time_proxy": {
                row["instance_id"]: row["first_apply_pass_step"]
                for row in instance_rows
                if row["first_apply_pass_step"] is not None
            },
        },
        "information_loss": {
            "repo_ready_but_final_patch_empty": [
                row["instance_id"]
                for row in instance_rows
                if "repo_context_ready_but_final_patch_empty" in row["information_loss_flags"]
            ][:20],
            "patch_touches_no_repo_context_candidate_file": [
                row["instance_id"]
                for row in instance_rows
                if "patch_touches_no_repo_context_candidate_file" in row["information_loss_flags"]
            ][:20],
            "nonempty_candidate_lost_to_apply_failure": [
                row["instance_id"]
                for row in instance_rows
                if "nonempty_candidate_lost_to_apply_failure" in row["information_loss_flags"]
            ][:20],
        },
        "mode_allocation_mismatch": {
            "by_mode": by_mode,
            "high_cost_empty_instances": sorted(
                [
                    {
                        "instance_id": row["instance_id"],
                        "mode": row["mode"],
                        "total_tokens": row["total_tokens"],
                        "wall_seconds": row["wall_seconds"],
                    }
                    for row in instance_rows
                    if not row["final_patch_nonempty"]
                ],
                key=lambda item: float(item["total_tokens"]),
                reverse=True,
            )[:12],
        },
        "local_apply_optimization_target": {
            "final_nonempty_patch_rate": len(final_nonempty) / total,
            "apply_check_passed_rate": len(apply_passed) / total,
            "empty_patch_rate": 1.0 - (len(final_nonempty) / total),
        },
        "representative_instances": instance_rows[:12],
    }


def _summarize_evaluation(manifest: dict[str, Any]) -> dict[str, Any]:
    report = manifest.get("report") if isinstance(manifest.get("report"), dict) else {}
    instance_results = manifest.get("instance_results") if isinstance(manifest.get("instance_results"), list) else []
    return {
        "returncode": manifest.get("returncode"),
        "modal": manifest.get("modal"),
        "expected_report_exists": manifest.get("expected_report_exists"),
        "prediction_validation": manifest.get("prediction_validation"),
        "resolved_instances": report.get("resolved_instances"),
        "unresolved_instances": report.get("unresolved_instances"),
        "error_instances": report.get("error_instances"),
        "empty_patch_instances": report.get("empty_patch_instances"),
        "instance_results": [
            {
                "instance_id": row.get("instance_id"),
                "resolved": row.get("resolved"),
                "patch_apply_failed": row.get("patch_apply_failed"),
                "error_summary": row.get("error_summary"),
            }
            for row in instance_results
        ],
    }


def _selected_trace_events(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for row in traces:
        if row.get("phase") not in {"observe", "localize", "other", "patch", "review", "fallback", "verify"}:
            continue
        event = {
            "step": row.get("step"),
            "phase": row.get("phase"),
            "agent_id": row.get("agent_id"),
            "model_id": row.get("model_id"),
            "error": row.get("error"),
            "payload_summary": row.get("payload_summary"),
            "patch_empty_reason": row.get("patch_empty_reason"),
            "patch_apply_check": row.get("patch_apply_check"),
            "repo_context_status": row.get("repo_context_status"),
            "repo_context_candidate_files": row.get("repo_context_candidate_files"),
            "stopping_reason": row.get("stopping_reason"),
            "selected_patch_chars": row.get("selected_patch_chars"),
        }
        selected.append({key: value for key, value in event.items() if value is not None})
    return selected[-20:]


def _repo_context_artifacts(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in traces:
        path_value = row.get("repo_context_path")
        if not path_value:
            continue
        path = Path(str(path_value))
        if str(path) in seen or not path.exists():
            continue
        seen.add(str(path))
        payload = read_json(path)
        artifacts.append(
            {
                "path": str(path),
                "repo": payload.get("repo"),
                "base_commit": payload.get("base_commit"),
                "status": payload.get("status"),
                "candidate_files": payload.get("candidate_files", [])[:12],
                "search_queries": payload.get("search_queries", [])[:12],
                "search_hits": payload.get("search_hits", [])[:12],
                "snippets": [
                    {
                        "path": snippet.get("path"),
                        "start_line": snippet.get("start_line"),
                        "end_line": snippet.get("end_line"),
                        "text": _truncate(str(snippet.get("text") or ""), 3500),
                    }
                    for snippet in payload.get("snippets", [])[:4]
                    if isinstance(snippet, dict)
                ],
            }
        )
    return artifacts[:8]


def _safe_public_instance(row: dict[str, Any]) -> dict[str, Any]:
    blocked = {
        "patch",
        "test_patch",
        "solution",
        "gold_patch",
        "FAIL_TO_PASS",
        "PASS_TO_PASS",
        "fail_to_pass",
        "pass_to_pass",
    }
    safe = {key: value for key, value in row.items() if key not in blocked}
    if "problem_statement" in safe:
        safe["problem_statement"] = _truncate(str(safe["problem_statement"]), 5000)
    if "hints_text" in safe and safe["hints_text"] is not None:
        safe["hints_text"] = _truncate(str(safe["hints_text"]), 2000)
    return safe


def _select_hierarchical(design: OrchestrationDesign, orchestration_id: str) -> OrchestrationSpec:
    orchestration = design.orchestration
    if orchestration.orchestration_id == orchestration_id:
        if orchestration.orchestration_type != "hierarchical_routed":
            raise ValueError(f"{orchestration_id!r} is not hierarchical_routed.")
        return orchestration
    raise KeyError(f"Unknown orchestration_id {orchestration_id!r}")


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        start = text.find("{")
        if start < 0:
            raise
        payload, _end = decoder.raw_decode(text[start:])
    if not isinstance(payload, dict):
        raise ValueError("Meta update output must be a JSON object.")
    return payload


def _modified_files_from_patch(patch: str) -> list[str]:
    files: list[str] = []
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.append(parts[3].removeprefix("b/"))
    return sorted(set(files))


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-") or "meta_update"


def _most_common(values: list[str]) -> str:
    if not values:
        return "unknown"
    return Counter(values).most_common(1)[0][0]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _load_yaml(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/swebench_orchestration_slurm_pilot.yaml")
    parser.add_argument("--design", required=True)
    parser.add_argument("--orchestration-id", default="swev_e250_routed_onepass_escalator_20260607_b4c1")
    parser.add_argument("--executor-dir", required=True)
    parser.add_argument("--evaluation-manifest", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--invoke-codex", action="store_true")
    parser.add_argument("--proposal", default=None, help="Existing proposal JSON to materialize without Codex.")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=None)
    parser.add_argument("--updated-design-out", default=None)
    parser.add_argument("--updated-config-out", default=None)
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = _load_yaml(Path(args.config) if args.config else None)
    design = OrchestrationDesign.model_validate(read_json(Path(args.design)))
    failure_bundle = build_failure_bundle(
        executor_dir=Path(args.executor_dir),
        evaluation_manifest_path=Path(args.evaluation_manifest) if args.evaluation_manifest else None,
    )
    prompt = render_update_prompt(
        design=design,
        orchestration_id=args.orchestration_id,
        failure_bundle=failure_bundle,
        config=config,
    )
    prompt_path = output_dir / "meta_update_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path = output_dir / "meta_update_schema.json"
    schema_path.write_text(
        json.dumps(MetaUpdateProposal.model_json_schema(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    failure_bundle_path = output_dir / "failure_bundle.json"
    failure_bundle_path.write_text(json.dumps(failure_bundle, indent=2, sort_keys=True), encoding="utf-8")

    result: dict[str, Any] = {
        "prompt_path": str(prompt_path),
        "schema_path": str(schema_path),
        "failure_bundle_path": str(failure_bundle_path),
        "invoke_codex": args.invoke_codex,
    }
    proposal: MetaUpdateProposal | None = None
    raw_payload: dict[str, Any] | None = None
    if args.proposal:
        raw_payload = read_json(Path(args.proposal))
        proposal = MetaUpdateProposal.model_validate(raw_payload)
    elif args.invoke_codex:
        meta = config.get("meta_designer", {})
        proposal, raw_payload, usage = invoke_meta_update(
            prompt=prompt,
            model_id=args.model_id or str(meta.get("model_id", "gpt-5.5")),
            reasoning_effort=args.reasoning_effort or str(meta.get("reasoning_effort", "xhigh")),
            timeout_seconds=args.timeout_seconds or int(meta.get("timeout_seconds", 1800)),
        )
        usage_path = output_dir / "meta_update_usage.json"
        usage_path.write_text(json.dumps(usage, indent=2, sort_keys=True), encoding="utf-8")
        result["usage_path"] = str(usage_path)

    if proposal is not None and raw_payload is not None:
        raw_path = output_dir / "meta_update_raw.json"
        raw_path.write_text(json.dumps(raw_payload, indent=2, sort_keys=True), encoding="utf-8")
        proposal_path = output_dir / "meta_update.json"
        proposal_path.write_text(
            json.dumps(proposal.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        updated_design = materialize_updated_design(
            design=design,
            proposal=proposal,
            orchestration_id=args.orchestration_id,
        )
        updated_design_path = Path(args.updated_design_out) if args.updated_design_out else output_dir / "orchestration_design_updated.json"
        updated_design_path.parent.mkdir(parents=True, exist_ok=True)
        updated_design_path.write_text(
            json.dumps(updated_design.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        config_patch_path = output_dir / "executor_config_patch.json"
        config_patch_path.write_text(
            json.dumps(proposal.executor_config_patch.model_dump(exclude_none=True), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        if args.updated_config_out:
            updated_config = apply_executor_config_patch(config, proposal, design_path=updated_design_path)
            updated_config_path = Path(args.updated_config_out)
            updated_config_path.parent.mkdir(parents=True, exist_ok=True)
            updated_config_path.write_text(yaml.safe_dump(updated_config, sort_keys=False), encoding="utf-8")
            result["updated_config_path"] = str(updated_config_path)
        result.update(
            {
                "proposal_path": str(proposal_path),
                "raw_path": str(raw_path),
                "updated_design_path": str(updated_design_path),
                "executor_config_patch_path": str(config_patch_path),
                "design_update_id": proposal.design_update_id,
                "target_orchestration_id": proposal.target_orchestration_id,
            }
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
