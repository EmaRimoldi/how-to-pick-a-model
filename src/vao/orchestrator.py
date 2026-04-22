"""Canonical six-branch experimental protocol."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import yaml

from benchmarks.stateful_query_engine.harness.run_benchmark import load_instance_config

from vao.agents.base import AgentAdapter, AgentState
from vao.agents.anthropic_adapter import ClaudeHaikuAdapter
from vao.agents.claude_code_adapter import ClaudeCodeAdapter
from vao.agents.local_stub_adapter import LeakageProbeAdapter, LocalStubAdapter
from vao.agents.openai_direct_edit_adapter import OpenAICompatibleDirectEditAdapter
from vao.agents.openai_compatible_adapter import OpenAICompatibleAdapter
from vao.agents.openai_responses_adapter import OpenAIResponsesAdapter
from vao.agents.routing_student_adapter import RoutingStudentAdapter
from vao.estimators import gain, jsd, productive_mode_proxy, routing_regret
from vao.logging_utils import append_jsonl, now_iso, sha256_file, write_json
from vao.schemas import BranchEvaluation, ModeDistribution, RunManifest, StepRecord
from vao.taxonomy import MODES, classify_edit_mode, normalize_mode_probs
from vao.verifier import evaluate_solution, validate_source
from vao.visibility import build_visible_history
from vao.workspaces import create_run_dir, create_step_branches, init_workspace, promote_branch_to_parent, write_diff


ADAPTERS = {
    "local_stub": LocalStubAdapter,
    "leakage_probe": LeakageProbeAdapter,
    "claude_haiku": ClaudeHaikuAdapter,
    "claude_code": ClaudeCodeAdapter,
    "openai_compatible": OpenAICompatibleAdapter,
    "openai_compatible_direct_edit": OpenAICompatibleDirectEditAdapter,
    "openai_responses": OpenAIResponsesAdapter,
    "routing_student": RoutingStudentAdapter,
}


def run_from_config(config: dict[str, Any], *, model_ids: list[str] | None = None, profiles: list[str] | None = None, steps: int | None = None, run_id: str | None = None) -> list[Path]:
    model_configs = _load_model_configs()
    include_models = model_ids or list(config.get("models", {}).get("include", ["local_stub"]))
    include_profiles = profiles or list(config.get("benchmark", {}).get("profiles", ["hard_optimization"]))
    completed: list[Path] = []
    for model_key in include_models:
        if model_key not in model_configs:
            raise KeyError(f"Unknown model key {model_key!r}; expected one of {sorted(model_configs)}")
        for profile_id in include_profiles:
            effective = _with_overrides(config, model_key, profile_id, steps)
            effective_run_id = run_id
            if run_id and (len(include_models) > 1 or len(include_profiles) > 1):
                effective_run_id = f"{run_id}_{model_key}_{profile_id}"
            completed.append(run_single(effective, model_key, model_configs[model_key], profile_id, run_id=effective_run_id))
    return completed


def run_single(config: dict[str, Any], model_key: str, model_config: dict[str, Any], profile_id: str, *, run_id: str | None = None) -> Path:
    experiment = config["experiment"]
    modes = list(experiment.get("modes", MODES))
    if modes != MODES:
        raise ValueError(f"The canonical protocol requires modes {MODES}; got {modes}")
    visibility_regime = str(experiment.get("visibility_regime", "top1_only"))
    feedback_condition = str(experiment.get("feedback_condition", "ca"))
    ask_post_feedback_distribution = bool(experiment.get("ask_post_feedback_distribution", feedback_condition == "cb"))
    selection_policy = str(experiment.get("selection_policy", "top1"))
    if feedback_condition == "cb" and visibility_regime != "all_branches":
        raise ValueError("C(b) feedback-use runs require visibility_regime: all_branches")
    max_steps = int(experiment.get("steps", 2))
    wall_budget_seconds = experiment.get("wall_budget_seconds")
    branch_timeout_seconds = int(experiment.get("branch_timeout_seconds", 240))
    incorrect_penalty = float(experiment.get("incorrect_penalty", -1.0))

    run_dir = create_run_dir(Path(config["output"]["root"]), config, run_id=run_id)
    run_id_actual = run_dir.name
    model_id = str(model_config.get("model_id", model_key))
    adapter = _build_adapter(model_config)
    template_path = Path(config["benchmark"]["template_path"])
    workspace_solution = init_workspace(run_dir, template_path)
    run_started = time.time()

    manifest = RunManifest(
        run_id=run_id_actual,
        profile_id=profile_id,
        model_id=model_id,
        visibility_regime=visibility_regime,
        modes=MODES,
        max_steps=max_steps,
        selection_policy=selection_policy,
        feedback_condition=feedback_condition,
        wall_budget_seconds=wall_budget_seconds,
        config=config,
    )
    write_json(run_dir / "run_manifest.json", manifest)

    baseline = evaluate_solution(
        workspace_solution,
        profile_id,
        branch_timeout_seconds,
        run_dir / "baseline_verification.json",
        primary_mode="micro",
        declared_mode="micro",
        inferred_mode="micro",
        run_id="baseline",
        instance_overrides=config.get("benchmark", {}).get("instance_overrides"),
    )
    baseline_perf_path = Path(baseline.raw_verifier_path or "") / "artifacts" / "baseline_perf.json"
    parent_loss = baseline.latent_loss
    records: list[StepRecord] = []

    for step in range(max_steps):
        elapsed = time.time() - run_started
        if wall_budget_seconds is not None and elapsed >= float(wall_budget_seconds):
            break
        parent_hash = sha256_file(workspace_solution)
        step_parent_loss = parent_loss
        residual_wall = None if wall_budget_seconds is None else max(float(wall_budget_seconds) - elapsed, 0.0)
        state = AgentState(
            run_id=run_id_actual,
            profile_id=profile_id,
            model_id=model_id,
            step=step,
            current_solution_path=workspace_solution,
            current_solution_source=workspace_solution.read_text(encoding="utf-8"),
            visible_history=build_visible_history(records, visibility_regime),
            profile_summary=_profile_summary(profile_id),
            residual_steps=max_steps - step,
            residual_wall_seconds=residual_wall,
            visibility_regime=visibility_regime,
            metadata={"model_key": model_key},
        )
        step_dir = run_dir / "steps" / f"step_{step:04d}"
        branch_dirs = create_step_branches(run_dir, step, workspace_solution, MODES)
        candidate_batch_id = f"{run_id_actual}:step_{step:04d}:{parent_hash[:12]}"
        batch_proposals: dict[str, Any] | None = None
        if str(experiment.get("candidate_generation", "per_mode")) == "batched":
            batch_fn = getattr(adapter, "propose_step_batch", None)
            if not callable(batch_fn):
                raise ValueError(f"Adapter {type(adapter).__name__} does not support batched candidate_generation")
            distribution, batch_proposals = batch_fn(state, branch_dirs)
            distribution_errors: list[str] = []
        else:
            distribution, distribution_errors = _propose_distribution(adapter, state)
        step_input_tokens = _usage_input_tokens(distribution.parsed_json)
        step_output_tokens = _usage_output_tokens(distribution.parsed_json)
        step_cost_usd = _usage_cost(distribution.parsed_json)
        selected_mode_top1 = max(MODES, key=lambda mode: distribution.mode_probs[mode])
        selected_mode, selected_mode_reason = _select_mode(experiment, step, selected_mode_top1)
        branch_evaluations: list[BranchEvaluation] = []

        for mode in MODES:
            branch_dir = branch_dirs[mode]
            proposal_errors: list[str] = []
            if batch_proposals is not None:
                proposal = batch_proposals[mode]
            else:
                try:
                    proposal = adapter.propose_edit_for_mode(state, mode, branch_dir)
                except Exception as exc:  # noqa: BLE001 - keep protocol running and log failed branch.
                    proposal_errors.append(f"{type(exc).__name__}: {exc}")
                    if getattr(adapter, "strict_failures", False):
                        proposal = _rejected_noop_proposal(state, mode, branch_dir, proposal_errors)
                    else:
                        proposed = branch_dir / "proposed_solution.py"
                        proposed.write_text((branch_dir / "parent_solution.py").read_text(encoding="utf-8"), encoding="utf-8")
                        proposal = LocalStubAdapter().propose_edit_for_mode(state, mode, branch_dir)
                        proposal.errors.extend(proposal_errors)
            proposal_dump = proposal.model_dump(mode="json")
            step_input_tokens += _usage_input_tokens(proposal_dump)
            step_output_tokens += _usage_output_tokens(proposal_dump)
            step_cost_usd += _usage_cost(proposal_dump)

            parent_source = (branch_dir / "parent_solution.py").read_text(encoding="utf-8")
            proposed_path = branch_dir / "proposed_solution.py"
            post_source = proposed_path.read_text(encoding="utf-8")
            write_diff(parent_source, post_source, branch_dir / "patch.diff")
            source_validation = validate_source(post_source)
            inferred_mode, secondary_modes, classifier_details = classify_edit_mode(parent_source, post_source)
            proposal_record = {
                **proposal_dump,
                "candidate_batch_id": candidate_batch_id,
                "source_validation": source_validation,
                "classifier": {
                    "inferred_mode": inferred_mode,
                    "secondary_modes": secondary_modes,
                    "details": classifier_details,
                },
            }
            write_json(branch_dir / "proposal.json", proposal_record)

            evaluation = evaluate_solution(
                proposed_path,
                profile_id,
                branch_timeout_seconds,
                branch_dir / "verification.json",
                branch_index=MODES.index(mode),
                primary_mode=inferred_mode,
                secondary_modes=secondary_modes,
                declared_mode=mode,
                inferred_mode=inferred_mode,
                baseline_perf_path=baseline_perf_path if baseline_perf_path.exists() else None,
                source_parent_hash=parent_hash,
                run_id=f"step_{step:04d}_{mode}",
                instance_overrides=config.get("benchmark", {}).get("instance_overrides"),
            )
            evaluation.validation_failures.extend([] if source_validation.get("passed") else source_validation.get("errors", []))
            evaluation.gain = gain(step_parent_loss, evaluation.latent_loss, evaluation.correctness, incorrect_penalty)
            model_edit_path = _model_edit_artifact_path(branch_dir)
            if model_edit_path is not None:
                evaluation.model_edit_path = str(model_edit_path)
            branch_evaluations.append(evaluation)

        selected_eval = next(branch for branch in branch_evaluations if branch.declared_mode == selected_mode)
        for branch in branch_evaluations:
            branch.selected_as_visible = visibility_regime == "all_branches" or branch.declared_mode == selected_mode
            branch.promoted_as_parent = branch.declared_mode == selected_mode
            write_json(Path(branch.file_path).parent / "verification.json", branch)

        post_feedback, post_feedback_errors, feedback_metrics = _maybe_propose_post_feedback_distribution(
            adapter=adapter,
            state=state,
            records=records,
            run_id=run_id_actual,
            profile_id=profile_id,
            model_id=model_id,
            step=step,
            parent_hash=parent_hash,
            step_parent_loss=step_parent_loss,
            distribution=distribution,
            selected_mode_top1=selected_mode_top1,
            selected_mode=selected_mode,
            selected_branch=str(Path(selected_eval.file_path).parent),
            candidate_batch_id=candidate_batch_id,
            visibility_regime=visibility_regime,
            branch_evaluations=branch_evaluations,
            residual_steps=max_steps - step - 1,
            residual_wall_seconds=None if wall_budget_seconds is None else max(float(wall_budget_seconds) - (time.time() - run_started), 0.0),
            selection_policy=selection_policy,
            selected_mode_reason=selected_mode_reason,
            enabled=ask_post_feedback_distribution,
        )
        if post_feedback is not None:
            post_dump = post_feedback.parsed_json or {}
            step_input_tokens += _usage_input_tokens(post_dump)
            step_output_tokens += _usage_output_tokens(post_dump)
            step_cost_usd += _usage_cost(post_dump)

        promote_branch_to_parent(Path(selected_eval.file_path), workspace_solution)
        parent_loss = selected_eval.latent_loss

        step_record = StepRecord(
            run_id=run_id_actual,
            profile_id=profile_id,
            model_id=model_id,
            step=step,
            timestamp=now_iso(),
            current_solution_hash=parent_hash,
            parent_solution_hash=parent_hash,
            parent_latent_loss=step_parent_loss,
            mode_probs=normalize_mode_probs(distribution.mode_probs),
            mode_ranking=distribution.mode_ranking,
            selected_mode_top1=selected_mode_top1,
            selected_mode=selected_mode,
            selection_policy=selection_policy,
            selected_mode_reason=selected_mode_reason,
            selected_branch=str(Path(selected_eval.file_path).parent),
            candidate_batch_id=candidate_batch_id,
            visibility_regime=visibility_regime,
            branches=branch_evaluations,
            residual_steps=max_steps - step - 1,
            residual_wall_seconds=None if wall_budget_seconds is None else max(float(wall_budget_seconds) - (time.time() - run_started), 0.0),
            agent_cost_usd=step_cost_usd if step_cost_usd > 0 else None,
            input_tokens=step_input_tokens if step_input_tokens > 0 else None,
            output_tokens=step_output_tokens if step_output_tokens > 0 else None,
            model_output_raw_text=distribution.raw_text,
            parsed_model_output_json=distribution.parsed_json,
            post_feedback_mode_probs=post_feedback.mode_probs if post_feedback is not None else None,
            post_feedback_mode_ranking=post_feedback.mode_ranking if post_feedback is not None else None,
            post_feedback_model_output_raw_text=post_feedback.raw_text if post_feedback is not None else None,
            post_feedback_parsed_model_output_json=post_feedback.parsed_json if post_feedback is not None else None,
            post_feedback_errors=post_feedback_errors,
            post_feedback_retries=post_feedback.retries if post_feedback is not None else 0,
            post_feedback_validation_failures=post_feedback.validation_failures if post_feedback is not None else [],
            feedback_regret_improvement=feedback_metrics.get("feedback_regret_improvement"),
            feedback_jsd_improvement=feedback_metrics.get("feedback_jsd_improvement"),
            errors=distribution_errors,
            retries=distribution.retries,
            validation_failures=distribution.validation_failures,
        )
        write_json(step_dir / "step_record.json", step_record)
        append_jsonl(run_dir / "evaluations.jsonl", step_record)
        records.append(step_record)

    summary = _run_summary(run_id_actual, profile_id, model_id, visibility_regime, records, baseline, run_started)
    write_json(run_dir / "run_summary.json", summary)
    return run_dir


def _select_mode(experiment: dict[str, Any], step: int, top1_mode: str) -> tuple[str, str]:
    policy = str(experiment.get("selection_policy", "top1"))
    if policy == "top1":
        return top1_mode, "argmax_mode_probs"
    if policy == "fixed_mode":
        mode = str(experiment.get("selected_mode") or experiment.get("forced_mode") or "")
        if mode not in MODES:
            raise ValueError(f"selection_policy=fixed_mode requires selected_mode in {MODES}; got {mode!r}")
        return mode, f"fixed_mode:{mode}"
    if policy == "mode_sequence":
        sequence = list(experiment.get("selected_mode_sequence", []))
        if not sequence:
            raise ValueError("selection_policy=mode_sequence requires selected_mode_sequence")
        mode = str(sequence[step % len(sequence)])
        if mode not in MODES:
            raise ValueError(f"selected_mode_sequence contains invalid mode {mode!r}")
        return mode, f"mode_sequence[{step % len(sequence)}]:{mode}"
    raise ValueError(f"Unknown selection_policy {policy!r}; expected top1, fixed_mode, or mode_sequence")


def _model_edit_artifact_path(branch_dir: Path) -> Path | None:
    for name in ("model_edit.json", "model_edit.diff"):
        path = branch_dir / name
        if path.exists():
            return path
    return None


def _maybe_propose_post_feedback_distribution(
    *,
    adapter: AgentAdapter,
    state: AgentState,
    records: list[StepRecord],
    run_id: str,
    profile_id: str,
    model_id: str,
    step: int,
    parent_hash: str,
    step_parent_loss: float,
    distribution: ModeDistribution,
    selected_mode_top1: str,
    selected_mode: str,
    selected_branch: str,
    candidate_batch_id: str,
    visibility_regime: str,
    branch_evaluations: list[BranchEvaluation],
    residual_steps: int,
    residual_wall_seconds: float | None,
    selection_policy: str,
    selected_mode_reason: str,
    enabled: bool,
) -> tuple[ModeDistribution | None, list[str], dict[str, float | None]]:
    if not enabled:
        return None, [], {}
    provisional = StepRecord(
        run_id=run_id,
        profile_id=profile_id,
        model_id=model_id,
        step=step,
        current_solution_hash=parent_hash,
        parent_solution_hash=parent_hash,
        parent_latent_loss=step_parent_loss,
        mode_probs=distribution.mode_probs,
        mode_ranking=distribution.mode_ranking,
        selected_mode_top1=selected_mode_top1,
        selected_mode=selected_mode,
        selection_policy=selection_policy,
        selected_mode_reason=selected_mode_reason,
        selected_branch=selected_branch,
        candidate_batch_id=candidate_batch_id,
        visibility_regime=visibility_regime,
        branches=branch_evaluations,
        residual_steps=residual_steps,
        residual_wall_seconds=residual_wall_seconds,
        model_output_raw_text=distribution.raw_text,
        parsed_model_output_json=distribution.parsed_json,
    )
    post_state = AgentState(
        run_id=state.run_id,
        profile_id=state.profile_id,
        model_id=state.model_id,
        step=state.step,
        current_solution_path=state.current_solution_path,
        current_solution_source=state.current_solution_source,
        visible_history=build_visible_history(records + [provisional], "all_branches"),
        profile_summary=state.profile_summary,
        residual_steps=state.residual_steps,
        residual_wall_seconds=state.residual_wall_seconds,
        visibility_regime="all_branches",
        metadata={
            **state.metadata,
            "feedback_condition": "cb",
            "post_feedback_distribution": True,
            "feedback_step": step,
        },
    )
    post_distribution, errors = _propose_distribution(adapter, post_state)
    gains = {branch.declared_mode: float(branch.gain) for branch in branch_evaluations}
    pstar = productive_mode_proxy(gains)
    pre_regret = routing_regret(gains, selected_mode_top1)
    post_top1 = max(MODES, key=lambda mode: post_distribution.mode_probs[mode])
    post_regret = routing_regret(gains, post_top1)
    metrics = {
        "feedback_regret_improvement": float(pre_regret - post_regret),
        "feedback_jsd_improvement": float(jsd(distribution.mode_probs, pstar) - jsd(post_distribution.mode_probs, pstar)),
    }
    return post_distribution, errors, metrics


def _propose_distribution(adapter: AgentAdapter, state: AgentState) -> tuple[ModeDistribution, list[str]]:
    errors: list[str] = []
    try:
        return adapter.propose_mode_distribution(state), errors
    except Exception as exc:  # noqa: BLE001 - retry once through deterministic fallback.
        errors.append(f"distribution_error={type(exc).__name__}: {exc}")
        if getattr(adapter, "strict_failures", False):
            raise
    fallback = LocalStubAdapter()
    distribution = fallback.propose_mode_distribution(state)
    distribution.agent_contract_failed = True
    distribution.retries = 1
    distribution.validation_failures.extend(errors)
    return distribution, errors


def _rejected_noop_proposal(state: AgentState, mode: str, branch_dir: Path, errors: list[str]) -> Any:
    from vao.schemas import CandidateProposal

    parent_path = branch_dir / "parent_solution.py"
    proposed_path = branch_dir / "proposed_solution.py"
    model_edit_path = branch_dir / "model_edit.diff"
    parent_source = parent_path.read_text(encoding="utf-8")
    proposed_path.write_text(parent_source, encoding="utf-8")
    model_edit_path.write_text("", encoding="utf-8")
    return CandidateProposal(
        branch_index=MODES.index(mode),
        primary_mode=mode,
        secondary_modes=[],
        declared_mode=mode,
        source_hash=sha256_file(proposed_path),
        source_parent_hash=sha256_file(parent_path),
        file_path=str(proposed_path),
        raw_output_text="",
        parsed_output_json={
            "primary_mode": mode,
            "declared_mode": mode,
            "edit_format": "rejected_noop",
            "unified_diff": "",
            "model_edit_path": str(model_edit_path),
            "patch_parse_status": "failed",
            "patch_apply_status": "not_applied",
            "source_validation_status": "not_applicable_noop",
            "rationale": "Rejected strict-backend candidate; parent copied unchanged.",
            "run_id": state.run_id,
            "step": state.step,
        },
        prompt_hash=None,
        changed=False,
        errors=errors,
        validation_failures=["strict_backend_exception_noop"],
    )


def _usage_input_tokens(payload: dict[str, Any] | None) -> int:
    usage = _usage_payload(payload)
    return int(
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )


def _usage_output_tokens(payload: dict[str, Any] | None) -> int:
    usage = _usage_payload(payload)
    return int(usage.get("output_tokens", 0))


def _usage_cost(payload: dict[str, Any] | None) -> float:
    if not isinstance(payload, dict):
        return 0.0
    value = payload.get("cost_usd")
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _usage_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    usage = payload.get("usage")
    return usage if isinstance(usage, dict) else {}


def _build_adapter(model_config: dict[str, Any]) -> AgentAdapter:
    adapter_name = str(model_config.get("adapter", "local_stub"))
    cls = ADAPTERS.get(adapter_name)
    if cls is None:
        raise ValueError(f"Unknown adapter {adapter_name!r}")
    return cls(**model_config)


def _load_model_configs() -> dict[str, dict[str, Any]]:
    path = Path("configs/models.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return dict(data.get("models", {}))


def _with_overrides(config: dict[str, Any], model_key: str, profile_id: str, steps: int | None) -> dict[str, Any]:
    copied = json.loads(json.dumps(config))
    copied.setdefault("models", {})["include"] = [model_key]
    copied.setdefault("benchmark", {})["profiles"] = [profile_id]
    if steps is not None:
        copied.setdefault("experiment", {})["steps"] = steps
    return copied


def _profile_summary(profile_id: str) -> dict[str, Any]:
    config = load_instance_config()
    profile = config["profiles"][profile_id]
    return {
        "profile_id": profile_id,
        "initial_size": profile.get("initial_size"),
        "key_space": profile.get("key_space"),
        "trace_length": profile.get("trace_length"),
        "traces_per_family": profile.get("traces_per_family"),
        "families": profile.get("families"),
        "repetitions": profile.get("repetitions"),
        "warmup_prefix": profile.get("warmup_prefix"),
    }


def _run_summary(
    run_id: str,
    profile_id: str,
    model_id: str,
    visibility_regime: str,
    records: list[StepRecord],
    baseline: BranchEvaluation,
    run_started: float,
) -> dict[str, Any]:
    selected_losses = [
        branch.latent_loss
        for record in records
        for branch in record.branches
        if branch.promoted_as_parent and branch.correctness and math.isfinite(branch.latent_loss)
    ]
    all_branch_losses = [
        branch.latent_loss
        for record in records
        for branch in record.branches
        if branch.correctness and math.isfinite(branch.latent_loss)
    ]
    return {
        "run_id": run_id,
        "profile_id": profile_id,
        "model_id": model_id,
        "visibility_regime": visibility_regime,
        "steps_completed": len(records),
        "branch_evaluations": sum(len(record.branches) for record in records),
        "baseline_correctness": baseline.correctness,
        "baseline_loss": baseline.latent_loss,
        "best_visible_loss": min(selected_losses) if selected_losses else None,
        "best_counterfactual_loss": min(all_branch_losses) if all_branch_losses else None,
        "elapsed_wall_seconds": time.time() - run_started,
        "completed_at": now_iso(),
    }


def _parse_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--models", default=None, help="Comma-separated model keys from configs/models.yaml.")
    parser.add_argument("--profiles", default=None, help="Comma-separated benchmark profile ids.")
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    run_dirs = run_from_config(
        config,
        model_ids=_parse_list(args.models),
        profiles=_parse_list(args.profiles),
        steps=args.steps,
        run_id=args.run_id,
    )
    print(json.dumps({"run_dirs": [str(path) for path in run_dirs]}, indent=2))


if __name__ == "__main__":
    main()
