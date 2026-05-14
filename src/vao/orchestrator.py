"""Canonical six-branch experimental protocol."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import yaml

from vao.agents.base import AgentAdapter, AgentState
from vao.agents.autoresearch_local_stub_adapter import AutoResearchLocalStubAdapter
from vao.agents.anthropic_adapter import ClaudeHaikuAdapter
from vao.agents.claude_code_adapter import ClaudeCodeAdapter
from vao.agents.codex_cli_adapter import CodexCliAdapter
from vao.agents.local_stub_adapter import LeakageProbeAdapter, LocalStubAdapter
from vao.agents.openai_compatible_adapter import OpenAICompatibleAdapter
from vao.agents.openai_responses_adapter import OpenAIResponsesAdapter
from vao.benchmark_registry import get_benchmark_spec, infer_benchmark_id
from vao.estimators import gain, jsd, productive_mode_proxy, routing_regret
from vao.agents.claude_parser import ModelOutputError, parse_structured_edit_payload
from vao.logging_utils import append_jsonl, now_iso, sha256_file, write_json
from vao.prompts import render_template
from vao.schemas import BranchEvaluation, ModeDistribution, RunManifest, StepRecord
from vao.success_metrics import (
    DEFAULT_SUCCESS_THRESHOLD_RELATIVE,
    relative_improvement,
    success_on_relative_threshold,
    validate_relative_threshold,
)
from vao.taxonomy import MODES, normalize_mode_probs, validate_mode
from vao.verifier import evaluate_solution
from vao.visibility import build_visible_history
from vao.workspaces import create_run_dir, create_step_branches, init_workspace, promote_branch_to_parent, write_diff


ADAPTERS = {
    "local_stub": LocalStubAdapter,
    "autoresearch_local_stub": AutoResearchLocalStubAdapter,
    "leakage_probe": LeakageProbeAdapter,
    "claude_haiku": ClaudeHaikuAdapter,
    "claude_code": ClaudeCodeAdapter,
    "codex_cli": CodexCliAdapter,
    "openai_compatible": OpenAICompatibleAdapter,
    "openai_responses": OpenAIResponsesAdapter,
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
    benchmark_id = infer_benchmark_id(config)
    benchmark = get_benchmark_spec(benchmark_id)
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
    success_threshold_relative = validate_relative_threshold(
        experiment.get("success_relative_improvement_threshold", DEFAULT_SUCCESS_THRESHOLD_RELATIVE)
    )
    stop_on_success = bool(experiment.get("stop_on_success", False))
    instance_overrides = dict(config.get("benchmark", {}).get("instance_overrides") or {})
    task_mode_true = benchmark.task_mode_from_instance_overrides(instance_overrides)
    task_mode_source = "task_mode_override" if task_mode_true is not None else None
    task_mode_split = str(experiment.get("task_mode_split")) if experiment.get("task_mode_split") else None
    instance_seed = int(instance_overrides["seed"]) if "seed" in instance_overrides else None

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
        model_alias=model_key,
        task_mode_true=task_mode_true,
        task_mode_source=task_mode_source,
        task_mode_split=task_mode_split,
        instance_seed=instance_seed,
        visibility_regime=visibility_regime,
        modes=MODES,
        max_steps=max_steps,
        selection_policy=selection_policy,
        feedback_condition=feedback_condition,
        wall_budget_seconds=wall_budget_seconds,
        success_threshold_relative=success_threshold_relative,
        stop_on_success=stop_on_success,
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
        benchmark_id=benchmark_id,
    )
    baseline_perf_path = Path(baseline.raw_verifier_path or "") / "artifacts" / "baseline_perf.json"
    parent_loss = baseline.latent_loss
    records: list[StepRecord] = []
    best_visible_so_far = baseline.latent_loss if baseline.correctness and math.isfinite(baseline.latent_loss) else math.inf
    tau_step: int | None = None
    if str(experiment.get("candidate_generation", "batched")) == "single_prompt_trajectory":
        return _run_single_prompt_trajectory(
            adapter=adapter,
            config=config,
            experiment=experiment,
            benchmark=benchmark,
            benchmark_id=benchmark_id,
            run_dir=run_dir,
            run_id_actual=run_id_actual,
            profile_id=profile_id,
            model_id=model_id,
            model_key=model_key,
            workspace_solution=workspace_solution,
            baseline=baseline,
            baseline_perf_path=baseline_perf_path,
            parent_loss=parent_loss,
            run_started=run_started,
            max_steps=max_steps,
            wall_budget_seconds=wall_budget_seconds,
            branch_timeout_seconds=branch_timeout_seconds,
            incorrect_penalty=incorrect_penalty,
            success_threshold_relative=success_threshold_relative,
            stop_on_success=stop_on_success,
            visibility_regime=visibility_regime,
            selection_policy=selection_policy,
            instance_overrides=instance_overrides,
            task_mode_true=task_mode_true,
            task_mode_source=task_mode_source,
            task_mode_split=task_mode_split,
            instance_seed=instance_seed,
        )
    if str(experiment.get("candidate_generation", "batched")) == "interactive_session":
        return _run_interactive_session_trajectory(
            adapter=adapter,
            config=config,
            experiment=experiment,
            benchmark=benchmark,
            benchmark_id=benchmark_id,
            run_dir=run_dir,
            run_id_actual=run_id_actual,
            profile_id=profile_id,
            model_id=model_id,
            model_key=model_key,
            workspace_solution=workspace_solution,
            baseline=baseline,
            baseline_perf_path=baseline_perf_path,
            parent_loss=parent_loss,
            run_started=run_started,
            max_steps=max_steps,
            wall_budget_seconds=wall_budget_seconds,
            branch_timeout_seconds=branch_timeout_seconds,
            incorrect_penalty=incorrect_penalty,
            success_threshold_relative=success_threshold_relative,
            stop_on_success=stop_on_success,
            visibility_regime=visibility_regime,
            selection_policy=selection_policy,
            instance_overrides=instance_overrides,
            task_mode_true=task_mode_true,
            task_mode_source=task_mode_source,
            task_mode_split=task_mode_split,
            instance_seed=instance_seed,
        )

    for step in range(max_steps):
        elapsed = time.time() - run_started
        if wall_budget_seconds is not None and elapsed >= float(wall_budget_seconds):
            break
        step_started = time.time()
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
            profile_summary=benchmark.profile_summary(profile_id, instance_overrides=instance_overrides),
            residual_steps=max_steps - step,
            residual_wall_seconds=residual_wall,
            visibility_regime=visibility_regime,
            metadata={
                "model_key": model_key,
                "benchmark_id": benchmark_id,
                "prompt_template": str(experiment.get("prompt_template", benchmark.prompt_template)),
            },
        )
        step_dir = run_dir / "steps" / f"step_{step:04d}"
        branch_dirs = create_step_branches(run_dir, step, workspace_solution, MODES)
        candidate_batch_id = f"{run_id_actual}:step_{step:04d}:{parent_hash[:12]}"
        candidate_generation = str(experiment.get("candidate_generation", "batched"))
        step_input_tokens = 0
        step_output_tokens = 0
        step_total_tokens = 0
        step_cost_usd = 0.0
        distribution_errors: list[str] = []
        if candidate_generation == "batched":
            batch_fn = getattr(adapter, "propose_step_batch", None)
            if not callable(batch_fn):
                raise ValueError(f"Adapter {type(adapter).__name__} does not support batched candidate_generation")
            distribution, batch_proposals = batch_fn(state, branch_dirs)
            step_input_tokens += _usage_input_tokens(distribution.parsed_json)
            step_output_tokens += _usage_output_tokens(distribution.parsed_json)
            step_total_tokens += _usage_total_tokens(distribution.parsed_json)
            step_cost_usd += _usage_cost(distribution.parsed_json)
            selected_mode_top1 = max(MODES, key=lambda mode: distribution.mode_probs[mode])
            selected_mode, selected_mode_reason = _select_mode(experiment, step, selected_mode_top1)
            branch_evaluations: list[BranchEvaluation] = []

            for mode in MODES:
                branch_dir = branch_dirs[mode]
                proposal = batch_proposals[mode]
                proposal_dump = proposal.model_dump(mode="json")
                step_input_tokens += _usage_input_tokens(proposal_dump)
                step_output_tokens += _usage_output_tokens(proposal_dump)
                step_total_tokens += _usage_total_tokens(proposal_dump)
                step_cost_usd += _usage_cost(proposal_dump)

                parent_source = (branch_dir / "parent_solution.py").read_text(encoding="utf-8")
                proposed_path = branch_dir / "proposed_solution.py"
                post_source = proposed_path.read_text(encoding="utf-8")
                write_diff(parent_source, post_source, branch_dir / "patch.diff")
                source_validation = benchmark.validate_source(post_source)
                inferred_mode, secondary_modes, classifier_details = benchmark.classify_edit_mode(parent_source, post_source)
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
                    benchmark_id=benchmark_id,
                )
                evaluation.validation_failures.extend([] if source_validation.get("passed") else source_validation.get("errors", []))
                evaluation.gain = gain(step_parent_loss, evaluation.latent_loss, evaluation.correctness, incorrect_penalty)
                model_edit_path = _model_edit_artifact_path(branch_dir)
                if model_edit_path is not None:
                    evaluation.model_edit_path = str(model_edit_path)
                branch_evaluations.append(evaluation)

            selected_eval = next(branch for branch in branch_evaluations if branch.declared_mode == selected_mode)
        elif candidate_generation == "single":
            single_fn = getattr(adapter, "propose_step_single", None)
            if not callable(single_fn):
                raise ValueError(f"Adapter {type(adapter).__name__} does not support single candidate_generation")
            distribution, proposal = single_fn(state, branch_dirs)
            step_input_tokens += _usage_input_tokens(distribution.parsed_json)
            step_output_tokens += _usage_output_tokens(distribution.parsed_json)
            step_total_tokens += _usage_total_tokens(distribution.parsed_json)
            step_cost_usd += _usage_cost(distribution.parsed_json)
            proposal_dump = proposal.model_dump(mode="json")
            step_input_tokens += _usage_input_tokens(proposal_dump)
            step_output_tokens += _usage_output_tokens(proposal_dump)
            step_total_tokens += _usage_total_tokens(proposal_dump)
            step_cost_usd += _usage_cost(proposal_dump)
            selected_mode_top1 = proposal.declared_mode
            selected_mode = proposal.declared_mode
            selected_mode_reason = "single_candidate_self_selected"
            branch_dir = branch_dirs[selected_mode]
            parent_source = (branch_dir / "parent_solution.py").read_text(encoding="utf-8")
            proposed_path = branch_dir / "proposed_solution.py"
            post_source = proposed_path.read_text(encoding="utf-8")
            write_diff(parent_source, post_source, branch_dir / "patch.diff")
            source_validation = benchmark.validate_source(post_source)
            inferred_mode, secondary_modes, classifier_details = benchmark.classify_edit_mode(parent_source, post_source)
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
            selected_eval = evaluate_solution(
                proposed_path,
                profile_id,
                branch_timeout_seconds,
                branch_dir / "verification.json",
                branch_index=MODES.index(selected_mode),
                primary_mode=inferred_mode,
                secondary_modes=secondary_modes,
                declared_mode=selected_mode,
                inferred_mode=inferred_mode,
                baseline_perf_path=baseline_perf_path if baseline_perf_path.exists() else None,
                source_parent_hash=parent_hash,
                run_id=f"step_{step:04d}_{selected_mode}",
                instance_overrides=config.get("benchmark", {}).get("instance_overrides"),
                benchmark_id=benchmark_id,
            )
            selected_eval.validation_failures.extend([] if source_validation.get("passed") else source_validation.get("errors", []))
            selected_eval.gain = gain(step_parent_loss, selected_eval.latent_loss, selected_eval.correctness, incorrect_penalty)
            model_edit_path = _model_edit_artifact_path(branch_dir)
            if model_edit_path is not None:
                selected_eval.model_edit_path = str(model_edit_path)
            branch_evaluations = [selected_eval]
        else:
            raise ValueError(f"Unknown candidate_generation {candidate_generation!r}; expected batched or single")
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
            step_total_tokens += _usage_total_tokens(post_dump)
            step_cost_usd += _usage_cost(post_dump)

        promote_branch_to_parent(Path(selected_eval.file_path), workspace_solution)
        parent_loss = selected_eval.latent_loss
        if selected_eval.correctness and math.isfinite(selected_eval.latent_loss):
            best_visible_so_far = min(best_visible_so_far, selected_eval.latent_loss)
        relative_improvement_so_far = relative_improvement(baseline.latent_loss, best_visible_so_far)
        successful_step = success_on_relative_threshold(
            baseline.latent_loss,
            best_visible_so_far,
            threshold=success_threshold_relative,
        )
        if tau_step is None and successful_step:
            tau_step = step + 1
        step_wall_seconds = time.time() - step_started

        step_record = StepRecord(
            run_id=run_id_actual,
            profile_id=profile_id,
            model_id=model_id,
            model_alias=model_key,
            task_mode_true=task_mode_true,
            task_mode_source=task_mode_source,
            task_mode_split=task_mode_split,
            instance_seed=instance_seed,
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
            step_wall_seconds=step_wall_seconds,
            agent_cost_usd=step_cost_usd if step_cost_usd > 0 else None,
            input_tokens=step_input_tokens if step_input_tokens > 0 else None,
            output_tokens=step_output_tokens if step_output_tokens > 0 else None,
            total_tokens=step_total_tokens if step_total_tokens > 0 else None,
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
            best_visible_so_far=best_visible_so_far if math.isfinite(best_visible_so_far) else None,
            relative_improvement_so_far=relative_improvement_so_far,
            success_threshold_relative=success_threshold_relative,
            successful_step=successful_step,
            errors=distribution_errors,
            retries=distribution.retries,
            validation_failures=distribution.validation_failures,
        )
        write_json(step_dir / "step_record.json", step_record)
        append_jsonl(run_dir / "evaluations.jsonl", step_record)
        records.append(step_record)
        if stop_on_success and successful_step:
            break

    summary = _run_summary(
        run_id_actual,
        profile_id,
        model_id,
        visibility_regime,
        records,
        baseline,
        run_started,
        success_threshold_relative=success_threshold_relative,
        stop_on_success=stop_on_success,
    )
    write_json(run_dir / "run_summary.json", summary)
    return run_dir


def _run_single_prompt_trajectory(
    *,
    adapter: AgentAdapter,
    config: dict[str, Any],
    experiment: dict[str, Any],
    benchmark: Any,
    benchmark_id: str,
    run_dir: Path,
    run_id_actual: str,
    profile_id: str,
    model_id: str,
    model_key: str,
    workspace_solution: Path,
    baseline: BranchEvaluation,
    baseline_perf_path: Path,
    parent_loss: float,
    run_started: float,
    max_steps: int,
    wall_budget_seconds: float | None,
    branch_timeout_seconds: int,
    incorrect_penalty: float,
    success_threshold_relative: float,
    stop_on_success: bool,
    visibility_regime: str,
    selection_policy: str,
    instance_overrides: dict[str, Any],
    task_mode_true: str | None,
    task_mode_source: str | None,
    task_mode_split: str | None,
    instance_seed: int | None,
) -> Path:
    trajectory_fn = getattr(adapter, "propose_single_prompt_trajectory", None)
    if not callable(trajectory_fn):
        raise ValueError(f"Adapter {type(adapter).__name__} does not support single_prompt_trajectory")
    state = AgentState(
        run_id=run_id_actual,
        profile_id=profile_id,
        model_id=model_id,
        step=0,
        current_solution_path=workspace_solution,
        current_solution_source=workspace_solution.read_text(encoding="utf-8"),
        visible_history=[],
        profile_summary=benchmark.profile_summary(profile_id, instance_overrides=instance_overrides),
        residual_steps=max_steps,
        residual_wall_seconds=wall_budget_seconds,
        visibility_regime=visibility_regime,
        metadata={
            "model_key": model_key,
            "benchmark_id": benchmark_id,
            "prompt_template": str(experiment.get("prompt_template", benchmark.prompt_template)),
            "candidate_generation": "single_prompt_trajectory",
        },
    )
    model_started = time.time()
    trajectory = trajectory_fn(state, max_steps)
    model_elapsed = time.time() - model_started
    prompt_path = run_dir / "trajectory_prompt.txt"
    prompt_path.write_text(str(trajectory.get("prompt", "")), encoding="utf-8")
    write_json(
        run_dir / "trajectory_prompt.json",
        {
            "prompt_hash": trajectory.get("prompt_hash"),
            "prompt_template": trajectory.get("prompt_template"),
            "prompt_path": str(prompt_path),
            "candidate_generation": "single_prompt_trajectory",
        },
    )
    (run_dir / "trajectory_raw_output.txt").write_text(str(trajectory.get("raw", "")), encoding="utf-8")
    write_json(run_dir / "trajectory_raw_output_meta.json", trajectory.get("meta", {}))
    payload = trajectory.get("payload") if isinstance(trajectory.get("payload"), dict) else {}
    planned_steps = payload.get("trajectory_steps") if isinstance(payload, dict) else []
    if not isinstance(planned_steps, list):
        planned_steps = []

    records: list[StepRecord] = []
    best_visible_so_far = baseline.latent_loss if baseline.correctness and math.isfinite(baseline.latent_loss) else math.inf
    source_validator = get_benchmark_spec(benchmark_id).validate_source
    usage_payload = {
        "usage": (trajectory.get("meta") or {}).get("usage"),
        "cost_usd": (trajectory.get("meta") or {}).get("cost_usd"),
    }
    total_input_tokens = _usage_input_tokens(usage_payload)
    total_output_tokens = _usage_output_tokens(usage_payload)
    total_tokens = _usage_total_tokens(usage_payload)
    total_cost = _usage_cost(usage_payload)

    for step, step_payload in enumerate(planned_steps[:max_steps]):
        if wall_budget_seconds is not None and time.time() - run_started >= float(wall_budget_seconds):
            break
        step_started = time.time()
        parent_hash = sha256_file(workspace_solution)
        step_parent_loss = parent_loss
        branch_dirs = create_step_branches(run_dir, step, workspace_solution, MODES)
        candidate_batch_id = f"{run_id_actual}:single_prompt:step_{step:04d}:{parent_hash[:12]}"
        errors: list[str] = []
        validation_failures: list[str] = []
        selected_mode = MODES[0]
        parsed: dict[str, Any] | None = None
        if isinstance(step_payload, dict):
            try:
                selected_mode = validate_mode(str(step_payload.get("declared_mode") or step_payload.get("primary_mode") or ""))
                if str(step_payload.get("primary_mode") or selected_mode) != selected_mode:
                    raise ModelOutputError("primary_declared_mode_mismatch")
                mode_raw = json.dumps(step_payload, sort_keys=True)
                parsed = parse_structured_edit_payload(
                    mode_raw,
                    selected_mode,
                    parent_source=workspace_solution.read_text(encoding="utf-8"),
                    source_validator=source_validator,
                )
            except (ModelOutputError, ValueError) as exc:
                errors.append(f"trajectory_step_invalid:{type(exc).__name__}:{exc}")
                validation_failures.append("trajectory_step_rejected")
        else:
            errors.append("trajectory_step_not_object")
            validation_failures.append("trajectory_step_rejected")

        branch_dir = branch_dirs[selected_mode]
        parent_path = branch_dir / "parent_solution.py"
        proposed_path = branch_dir / "proposed_solution.py"
        model_edit_path = branch_dir / "model_edit.json"
        parent_source = parent_path.read_text(encoding="utf-8")
        if parsed is None:
            proposed_path.write_text(parent_source, encoding="utf-8")
            model_edit_path.write_text("[]", encoding="utf-8")
            parsed = {
                "primary_mode": selected_mode,
                "declared_mode": selected_mode,
                "secondary_modes": [],
                "rationale": "Rejected malformed single-prompt trajectory step; parent copied unchanged.",
                "edits": [],
                "source_validation": {"passed": True, "errors": []},
            }
        else:
            proposed_path.write_text(str(parsed["solution_py"]), encoding="utf-8")
            model_edit_path.write_text(json.dumps(parsed.get("edits", []), indent=2, sort_keys=True), encoding="utf-8")
        post_source = proposed_path.read_text(encoding="utf-8")
        write_diff(parent_source, post_source, branch_dir / "patch.diff")
        source_validation = benchmark.validate_source(post_source)
        inferred_mode, secondary_modes, classifier_details = benchmark.classify_edit_mode(parent_source, post_source)
        proposal_record = {
            "candidate_batch_id": candidate_batch_id,
            "candidate_generation": "single_prompt_trajectory",
            "trajectory_step_index": step,
            "raw_output_text": json.dumps(step_payload, sort_keys=True) if isinstance(step_payload, dict) else str(step_payload),
            "parsed_output_json": {key: value for key, value in parsed.items() if key != "solution_py"},
            "source_validation": source_validation,
            "classifier": {
                "inferred_mode": inferred_mode,
                "secondary_modes": secondary_modes,
                "details": classifier_details,
            },
            "prompt_hash": trajectory.get("prompt_hash"),
            "prompt_snapshot_path": str(prompt_path),
            "changed": sha256_file(parent_path) != sha256_file(proposed_path),
            "errors": errors,
            "validation_failures": validation_failures,
        }
        write_json(branch_dir / "proposal.json", proposal_record)
        selected_eval = evaluate_solution(
            proposed_path,
            profile_id,
            branch_timeout_seconds,
            branch_dir / "verification.json",
            branch_index=MODES.index(selected_mode),
            primary_mode=inferred_mode,
            secondary_modes=secondary_modes,
            declared_mode=selected_mode,
            inferred_mode=inferred_mode,
            baseline_perf_path=baseline_perf_path if baseline_perf_path.exists() else None,
            source_parent_hash=parent_hash,
            run_id=f"step_{step:04d}_{selected_mode}",
            instance_overrides=config.get("benchmark", {}).get("instance_overrides"),
            benchmark_id=benchmark_id,
        )
        selected_eval.validation_failures.extend([] if source_validation.get("passed") else source_validation.get("errors", []))
        selected_eval.gain = gain(step_parent_loss, selected_eval.latent_loss, selected_eval.correctness, incorrect_penalty)
        selected_eval.model_edit_path = str(model_edit_path)
        selected_eval.selected_as_visible = True
        selected_eval.promoted_as_parent = True
        write_json(branch_dir / "verification.json", selected_eval)
        promote_branch_to_parent(Path(selected_eval.file_path), workspace_solution)
        parent_loss = selected_eval.latent_loss
        if selected_eval.correctness and math.isfinite(selected_eval.latent_loss):
            best_visible_so_far = min(best_visible_so_far, selected_eval.latent_loss)
        relative_improvement_so_far = relative_improvement(baseline.latent_loss, best_visible_so_far)
        successful_step = success_on_relative_threshold(
            baseline.latent_loss,
            best_visible_so_far,
            threshold=success_threshold_relative,
        )
        mode_probs = {mode: (1.0 if mode == selected_mode else 0.0) for mode in MODES}
        step_record = StepRecord(
            run_id=run_id_actual,
            profile_id=profile_id,
            model_id=model_id,
            model_alias=model_key,
            task_mode_true=task_mode_true,
            task_mode_source=task_mode_source,
            task_mode_split=task_mode_split,
            instance_seed=instance_seed,
            step=step,
            timestamp=now_iso(),
            current_solution_hash=parent_hash,
            parent_solution_hash=parent_hash,
            parent_latent_loss=step_parent_loss,
            mode_probs=mode_probs,
            mode_ranking=[selected_mode, *[mode for mode in MODES if mode != selected_mode]],
            selected_mode_top1=selected_mode,
            selected_mode=selected_mode,
            selection_policy=selection_policy,
            selected_mode_reason="single_prompt_trajectory_step",
            selected_branch=str(branch_dir),
            candidate_batch_id=candidate_batch_id,
            visibility_regime=visibility_regime,
            branches=[selected_eval],
            residual_steps=max_steps - step - 1,
            residual_wall_seconds=None if wall_budget_seconds is None else max(float(wall_budget_seconds) - (time.time() - run_started), 0.0),
            step_wall_seconds=time.time() - step_started,
            agent_cost_usd=total_cost if step == 0 and total_cost > 0 else None,
            input_tokens=total_input_tokens if step == 0 and total_input_tokens > 0 else None,
            output_tokens=total_output_tokens if step == 0 and total_output_tokens > 0 else None,
            total_tokens=total_tokens if step == 0 and total_tokens > 0 else None,
            model_output_raw_text=str(trajectory.get("raw", "")) if step == 0 else None,
            parsed_model_output_json={
                "candidate_generation": "single_prompt_trajectory",
                "prompt_hash": trajectory.get("prompt_hash"),
                "prompt_snapshot_path": str(prompt_path),
                "trajectory_step": step_payload,
                "trajectory_call_elapsed_wall_seconds": model_elapsed if step == 0 else None,
                "transport": (trajectory.get("meta") or {}).get("transport"),
                "usage": (trajectory.get("meta") or {}).get("usage"),
                "cost_usd": (trajectory.get("meta") or {}).get("cost_usd"),
            },
            best_visible_so_far=best_visible_so_far if math.isfinite(best_visible_so_far) else None,
            relative_improvement_so_far=relative_improvement_so_far,
            success_threshold_relative=success_threshold_relative,
            successful_step=successful_step,
            errors=errors,
            validation_failures=validation_failures,
        )
        step_dir = run_dir / "steps" / f"step_{step:04d}"
        write_json(step_dir / "step_record.json", step_record)
        append_jsonl(run_dir / "evaluations.jsonl", step_record)
        records.append(step_record)
        if stop_on_success and successful_step:
            break

    summary = _run_summary(
        run_id_actual,
        profile_id,
        model_id,
        visibility_regime,
        records,
        baseline,
        run_started,
        success_threshold_relative=success_threshold_relative,
        stop_on_success=stop_on_success,
    )
    summary["candidate_generation"] = "single_prompt_trajectory"
    summary["planned_steps_returned"] = len(planned_steps)
    write_json(run_dir / "run_summary.json", summary)
    return run_dir


def _run_interactive_session_trajectory(
    *,
    adapter: AgentAdapter,
    config: dict[str, Any],
    experiment: dict[str, Any],
    benchmark: Any,
    benchmark_id: str,
    run_dir: Path,
    run_id_actual: str,
    profile_id: str,
    model_id: str,
    model_key: str,
    workspace_solution: Path,
    baseline: BranchEvaluation,
    baseline_perf_path: Path,
    parent_loss: float,
    run_started: float,
    max_steps: int,
    wall_budget_seconds: float | None,
    branch_timeout_seconds: int,
    incorrect_penalty: float,
    success_threshold_relative: float,
    stop_on_success: bool,
    visibility_regime: str,
    selection_policy: str,
    instance_overrides: dict[str, Any],
    task_mode_true: str | None,
    task_mode_source: str | None,
    task_mode_split: str | None,
    instance_seed: int | None,
) -> Path:
    complete_persistent = getattr(adapter, "_complete_persistent", None)
    resume_persistent = getattr(adapter, "_resume_persistent", None)
    schema_fn = getattr(adapter, "_single_candidate_schema", None)
    if not callable(complete_persistent) or not callable(resume_persistent) or not callable(schema_fn):
        raise ValueError(f"Adapter {type(adapter).__name__} does not support interactive_session")

    prompt_template = str(experiment.get("prompt_template", benchmark.prompt_template))
    initial_prompt = render_template(
        prompt_template,
        profile_summary=json.dumps(benchmark.profile_summary(profile_id, instance_overrides=instance_overrides), sort_keys=True),
        visible_history="[]",
        current_solution_source=workspace_solution.read_text(encoding="utf-8"),
    )
    initial_prompt += (
        "\n\nInteractive trajectory mode:\n"
        "This is the only full task prompt. Return exactly one structured-edit candidate for step 0. "
        "After the verifier runs, you will be resumed in the same session with only verifier feedback "
        "and the current solution.py. Continue one edit at a time until the horizon is exhausted."
    )
    prompt_path = run_dir / "interactive_initial_prompt.txt"
    prompt_path.write_text(initial_prompt, encoding="utf-8")
    schema = schema_fn()
    raw, meta = complete_persistent(initial_prompt, schema, int(getattr(adapter, "max_tokens_edit", 4096)))
    session_id = meta.get("session_id")
    if not session_id:
        raise RuntimeError("interactive_session_missing_codex_session_id")
    write_json(run_dir / "interactive_session.json", {"session_id": session_id, "initial_meta": meta, "prompt_path": str(prompt_path)})

    records: list[StepRecord] = []
    best_visible_so_far = baseline.latent_loss if baseline.correctness and math.isfinite(baseline.latent_loss) else math.inf
    source_validator = get_benchmark_spec(benchmark_id).validate_source
    next_raw = raw
    next_meta = meta

    for step in range(max_steps):
        if wall_budget_seconds is not None and time.time() - run_started >= float(wall_budget_seconds):
            break
        step_started = time.time()
        parent_hash = sha256_file(workspace_solution)
        step_parent_loss = parent_loss
        branch_dirs = create_step_branches(run_dir, step, workspace_solution, MODES)
        candidate_batch_id = f"{run_id_actual}:interactive:step_{step:04d}:{parent_hash[:12]}"
        selected_mode = MODES[0]
        errors: list[str] = []
        validation_failures: list[str] = []
        parsed: dict[str, Any] | None = None
        retries = 0
        max_invalid_retries = int(experiment.get("interactive_invalid_edit_retries", 2))
        parent_source_for_parse = workspace_solution.read_text(encoding="utf-8")
        while True:
            try:
                payload = json.loads(next_raw)
                selected_mode = validate_mode(str(payload.get("declared_mode") or payload.get("primary_mode") or ""))
                if str(payload.get("primary_mode") or selected_mode) != selected_mode:
                    raise ModelOutputError("primary_declared_mode_mismatch")
                parsed = parse_structured_edit_payload(
                    json.dumps(payload, sort_keys=True),
                    selected_mode,
                    parent_source=parent_source_for_parse,
                    source_validator=source_validator,
                )
                break
            except (json.JSONDecodeError, ModelOutputError, ValueError) as exc:
                errors.append(f"interactive_step_invalid:{type(exc).__name__}:{exc}")
                if retries >= max_invalid_retries:
                    validation_failures.append("interactive_step_rejected")
                    break
                retries += 1
                repair_feedback = {
                    "step_to_repair": step,
                    "invalid_candidate_error": f"{type(exc).__name__}:{exc}",
                    "remaining_repair_attempts": max_invalid_retries - retries,
                    "current_solution_source": parent_source_for_parse,
                    "instruction": (
                        "Your previous structured-edit candidate could not be applied. "
                        "Return exactly one corrected candidate for the same step as JSON matching the schema. "
                        "Use empty strings for unused edit fields, never null. For replace_exact, old and new must "
                        "be non-empty strings and old must occur exactly once in current_solution_source."
                    ),
                }
                next_raw, next_meta = resume_persistent(
                    session_id,
                    json.dumps(repair_feedback, sort_keys=True),
                    schema,
                    int(getattr(adapter, "max_tokens_edit", 4096)),
                )

        branch_dir = branch_dirs[selected_mode]
        parent_path = branch_dir / "parent_solution.py"
        proposed_path = branch_dir / "proposed_solution.py"
        model_edit_path = branch_dir / "model_edit.json"
        parent_source = parent_path.read_text(encoding="utf-8")
        if parsed is None:
            proposed_path.write_text(parent_source, encoding="utf-8")
            model_edit_path.write_text("[]", encoding="utf-8")
            parsed = {"primary_mode": selected_mode, "declared_mode": selected_mode, "secondary_modes": [], "rationale": "Rejected malformed interactive step.", "edits": []}
        else:
            proposed_path.write_text(str(parsed["solution_py"]), encoding="utf-8")
            model_edit_path.write_text(json.dumps(parsed.get("edits", []), indent=2, sort_keys=True), encoding="utf-8")

        post_source = proposed_path.read_text(encoding="utf-8")
        write_diff(parent_source, post_source, branch_dir / "patch.diff")
        source_validation = benchmark.validate_source(post_source)
        inferred_mode, secondary_modes, classifier_details = benchmark.classify_edit_mode(parent_source, post_source)
        write_json(
            branch_dir / "proposal.json",
            {
                "candidate_batch_id": candidate_batch_id,
                "candidate_generation": "interactive_session",
                "raw_output_text": next_raw,
                "parsed_output_json": {key: value for key, value in parsed.items() if key != "solution_py"},
                "source_validation": source_validation,
                "classifier": {"inferred_mode": inferred_mode, "secondary_modes": secondary_modes, "details": classifier_details},
                "session_id": session_id,
                "model_edit_path": str(model_edit_path),
                "errors": errors,
                "validation_failures": validation_failures,
            },
        )
        selected_eval = evaluate_solution(
            proposed_path,
            profile_id,
            branch_timeout_seconds,
            branch_dir / "verification.json",
            branch_index=MODES.index(selected_mode),
            primary_mode=inferred_mode,
            secondary_modes=secondary_modes,
            declared_mode=selected_mode,
            inferred_mode=inferred_mode,
            baseline_perf_path=baseline_perf_path if baseline_perf_path.exists() else None,
            source_parent_hash=parent_hash,
            run_id=f"step_{step:04d}_{selected_mode}",
            instance_overrides=config.get("benchmark", {}).get("instance_overrides"),
            benchmark_id=benchmark_id,
        )
        selected_eval.validation_failures.extend([] if source_validation.get("passed") else source_validation.get("errors", []))
        selected_eval.gain = gain(step_parent_loss, selected_eval.latent_loss, selected_eval.correctness, incorrect_penalty)
        selected_eval.model_edit_path = str(model_edit_path)
        selected_eval.selected_as_visible = True
        selected_eval.promoted_as_parent = True
        write_json(branch_dir / "verification.json", selected_eval)
        promote_branch_to_parent(Path(selected_eval.file_path), workspace_solution)
        parent_loss = selected_eval.latent_loss
        if selected_eval.correctness and math.isfinite(selected_eval.latent_loss):
            best_visible_so_far = min(best_visible_so_far, selected_eval.latent_loss)
        relative_improvement_so_far = relative_improvement(baseline.latent_loss, best_visible_so_far)
        successful_step = success_on_relative_threshold(baseline.latent_loss, best_visible_so_far, threshold=success_threshold_relative)
        usage_payload = {"usage": next_meta.get("usage"), "cost_usd": next_meta.get("cost_usd")}
        mode_probs = {mode: (1.0 if mode == selected_mode else 0.0) for mode in MODES}
        step_record = StepRecord(
            run_id=run_id_actual,
            profile_id=profile_id,
            model_id=model_id,
            model_alias=model_key,
            task_mode_true=task_mode_true,
            task_mode_source=task_mode_source,
            task_mode_split=task_mode_split,
            instance_seed=instance_seed,
            step=step,
            timestamp=now_iso(),
            current_solution_hash=parent_hash,
            parent_solution_hash=parent_hash,
            parent_latent_loss=step_parent_loss,
            mode_probs=mode_probs,
            mode_ranking=[selected_mode, *[mode for mode in MODES if mode != selected_mode]],
            selected_mode_top1=selected_mode,
            selected_mode=selected_mode,
            selection_policy=selection_policy,
            selected_mode_reason="interactive_session",
            selected_branch=str(branch_dir),
            candidate_batch_id=candidate_batch_id,
            visibility_regime=visibility_regime,
            branches=[selected_eval],
            residual_steps=max_steps - step - 1,
            residual_wall_seconds=None if wall_budget_seconds is None else max(float(wall_budget_seconds) - (time.time() - run_started), 0.0),
            step_wall_seconds=time.time() - step_started,
            agent_cost_usd=_usage_cost(usage_payload) or None,
            input_tokens=_usage_input_tokens(usage_payload) or None,
            output_tokens=_usage_output_tokens(usage_payload) or None,
            total_tokens=_usage_total_tokens(usage_payload) or None,
            model_output_raw_text=next_raw,
            parsed_model_output_json={
                "candidate_generation": "interactive_session",
                "transport": next_meta.get("transport"),
                "session_id": session_id,
                "usage": next_meta.get("usage"),
                "cost_usd": next_meta.get("cost_usd"),
                "elapsed_wall_seconds": next_meta.get("elapsed_wall_seconds"),
            },
            best_visible_so_far=best_visible_so_far if math.isfinite(best_visible_so_far) else None,
            relative_improvement_so_far=relative_improvement_so_far,
            success_threshold_relative=success_threshold_relative,
            successful_step=successful_step,
            retries=retries,
            errors=errors,
            validation_failures=validation_failures,
        )
        step_dir = run_dir / "steps" / f"step_{step:04d}"
        write_json(step_dir / "step_record.json", step_record)
        append_jsonl(run_dir / "evaluations.jsonl", step_record)
        records.append(step_record)
        if stop_on_success and successful_step:
            break
        if step == max_steps - 1:
            break
        feedback = {
            "step_completed": step,
            "verifier_result": {
                "correctness": selected_eval.correctness,
                "val_loss": selected_eval.latent_loss,
                "gain": selected_eval.gain,
                "elapsed_wall_seconds": selected_eval.elapsed_wall_seconds,
                "raw_verifier_path": selected_eval.raw_verifier_path,
            },
            "best_visible_so_far": best_visible_so_far if math.isfinite(best_visible_so_far) else None,
            "relative_improvement_so_far": relative_improvement_so_far,
            "successful_step": successful_step,
            "remaining_steps": max_steps - step - 1,
            "current_solution_source": workspace_solution.read_text(encoding="utf-8"),
            "instruction": "Continue the same AutoResearch run. Return exactly one next structured-edit candidate as JSON matching the original schema. Do not repeat the initial task prompt.",
        }
        next_raw, next_meta = resume_persistent(session_id, json.dumps(feedback, sort_keys=True), schema, int(getattr(adapter, "max_tokens_edit", 4096)))

    summary = _run_summary(
        run_id_actual,
        profile_id,
        model_id,
        visibility_regime,
        records,
        baseline,
        run_started,
        success_threshold_relative=success_threshold_relative,
        stop_on_success=stop_on_success,
    )
    summary["candidate_generation"] = "interactive_session"
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


def _usage_total_tokens(payload: dict[str, Any] | None) -> int:
    usage = _usage_payload(payload)
    return int(usage.get("total_tokens", 0) or usage.get("total_tokens_reported", 0) or usage.get("tokens", 0))


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


def _profile_summary(profile_id: str, instance_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    benchmark = get_benchmark_spec("autoresearch_cifar10")
    return benchmark.profile_summary(profile_id, instance_overrides=instance_overrides)


def _run_summary(
    run_id: str,
    profile_id: str,
    model_id: str,
    visibility_regime: str,
    records: list[StepRecord],
    baseline: BranchEvaluation,
    run_started: float,
    *,
    success_threshold_relative: float,
    stop_on_success: bool,
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
    selected_accounting = [
        float(branch.accounting_cost or 0.0)
        for record in records
        for branch in record.branches
        if branch.promoted_as_parent
    ]
    all_branch_accounting = [
        float(branch.accounting_cost or 0.0)
        for record in records
        for branch in record.branches
    ]
    best_visible_loss = min(selected_losses) if selected_losses else None
    best_counterfactual_loss = min(all_branch_losses) if all_branch_losses else None
    relative_improvement_visible = relative_improvement(baseline.latent_loss, best_visible_loss)
    relative_improvement_counterfactual = relative_improvement(baseline.latent_loss, best_counterfactual_loss)
    success = success_on_relative_threshold(
        baseline.latent_loss,
        best_visible_loss,
        threshold=success_threshold_relative,
    )
    tau_step = next((record.step + 1 for record in records if record.successful_step), None)
    return {
        "run_id": run_id,
        "profile_id": profile_id,
        "model_id": model_id,
        "visibility_regime": visibility_regime,
        "steps_completed": len(records),
        "branch_evaluations": sum(len(record.branches) for record in records),
        "baseline_correctness": baseline.correctness,
        "baseline_loss": baseline.latent_loss,
        "success_threshold_relative": success_threshold_relative,
        "stop_on_success": stop_on_success,
        "success": success,
        "tau_step": tau_step,
        "best_visible_loss": best_visible_loss,
        "best_visible_relative_improvement": relative_improvement_visible,
        "best_counterfactual_loss": best_counterfactual_loss,
        "best_counterfactual_relative_improvement": relative_improvement_counterfactual,
        "selected_accounting_cost": sum(selected_accounting) if selected_accounting else 0.0,
        "total_branch_accounting_cost": sum(all_branch_accounting) if all_branch_accounting else 0.0,
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
