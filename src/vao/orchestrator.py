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
from vao.agents.claude_code_adapter import ClaudeCodeAdapter
from vao.agents.local_stub_adapter import LocalStubAdapter
from vao.agents.openai_compatible_adapter import OpenAICompatibleAdapter
from vao.estimators import gain
from vao.logging_utils import append_jsonl, now_iso, sha256_file, write_json
from vao.schemas import BranchEvaluation, ModeDistribution, RunManifest, StepRecord
from vao.taxonomy import MODES, classify_edit_mode, normalize_mode_probs
from vao.verifier import evaluate_solution, validate_source
from vao.visibility import build_visible_history
from vao.workspaces import create_run_dir, create_step_branches, init_workspace, promote_branch_to_parent, write_diff


ADAPTERS = {
    "local_stub": LocalStubAdapter,
    "claude_code": ClaudeCodeAdapter,
    "openai_compatible": OpenAICompatibleAdapter,
}


def run_from_config(config: dict[str, Any], *, model_ids: list[str] | None = None, profiles: list[str] | None = None, steps: int | None = None, run_id: str | None = None) -> list[Path]:
    model_configs = _load_model_configs()
    include_models = model_ids or list(config.get("models", {}).get("include", ["local_stub"]))
    include_profiles = profiles or list(config.get("benchmark", {}).get("profiles", ["paper_development"]))
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
        distribution, distribution_errors = _propose_distribution(adapter, state)
        selected_mode = max(MODES, key=lambda mode: distribution.mode_probs[mode])
        step_dir = run_dir / "steps" / f"step_{step:04d}"
        branch_dirs = create_step_branches(run_dir, step, workspace_solution, MODES)
        branch_evaluations: list[BranchEvaluation] = []
        candidate_batch_id = f"{run_id_actual}:step_{step:04d}:{parent_hash[:12]}"

        for mode in MODES:
            branch_dir = branch_dirs[mode]
            proposal_errors: list[str] = []
            try:
                proposal = adapter.propose_edit_for_mode(state, mode, branch_dir)
            except Exception as exc:  # noqa: BLE001 - keep protocol running and log failed branch.
                proposal_errors.append(f"{type(exc).__name__}: {exc}")
                proposed = branch_dir / "proposed_solution.py"
                proposed.write_text((branch_dir / "parent_solution.py").read_text(encoding="utf-8"), encoding="utf-8")
                proposal = LocalStubAdapter().propose_edit_for_mode(state, mode, branch_dir)
                proposal.errors.extend(proposal_errors)

            parent_source = (branch_dir / "parent_solution.py").read_text(encoding="utf-8")
            proposed_path = branch_dir / "proposed_solution.py"
            post_source = proposed_path.read_text(encoding="utf-8")
            write_diff(parent_source, post_source, branch_dir / "patch.diff")
            source_validation = validate_source(post_source)
            inferred_mode, secondary_modes, classifier_details = classify_edit_mode(parent_source, post_source)
            proposal_record = {
                **proposal.model_dump(mode="json"),
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
            evaluation.gain = gain(parent_loss, evaluation.latent_loss, evaluation.correctness, incorrect_penalty)
            branch_evaluations.append(evaluation)

        selected_eval = next(branch for branch in branch_evaluations if branch.declared_mode == selected_mode)
        for branch in branch_evaluations:
            branch.selected_as_visible = visibility_regime == "all_branches" or branch.declared_mode == selected_mode
            branch.promoted_as_parent = branch.declared_mode == selected_mode
            write_json(Path(branch.file_path).parent / "verification.json", branch)

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
            mode_probs=normalize_mode_probs(distribution.mode_probs),
            mode_ranking=distribution.mode_ranking,
            selected_mode_top1=selected_mode,
            selected_mode=selected_mode,
            selected_branch=str(Path(selected_eval.file_path).parent),
            candidate_batch_id=candidate_batch_id,
            visibility_regime=visibility_regime,
            branches=branch_evaluations,
            residual_steps=max_steps - step - 1,
            residual_wall_seconds=None if wall_budget_seconds is None else max(float(wall_budget_seconds) - (time.time() - run_started), 0.0),
            agent_cost_usd=None,
            input_tokens=None,
            output_tokens=None,
            model_output_raw_text=distribution.raw_text,
            parsed_model_output_json=distribution.parsed_json,
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


def _propose_distribution(adapter: AgentAdapter, state: AgentState) -> tuple[ModeDistribution, list[str]]:
    errors: list[str] = []
    try:
        return adapter.propose_mode_distribution(state), errors
    except Exception as exc:  # noqa: BLE001 - retry once through deterministic fallback.
        errors.append(f"distribution_error={type(exc).__name__}: {exc}")
    fallback = LocalStubAdapter()
    distribution = fallback.propose_mode_distribution(state)
    distribution.agent_contract_failed = True
    distribution.retries = 1
    distribution.validation_failures.extend(errors)
    return distribution, errors


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
