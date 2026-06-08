"""Execute frozen SWE-bench orchestration specs with open-source workers."""

from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vao.swebench_orchestration.repo_context import (
    RepoContext,
    RepoContextConfig,
    build_repository_context,
    default_work_dir,
    safe_instance_payload,
)
from vao.agents.codex_cli_adapter import CodexCliAdapter
from vao.agents.openai_compatible_adapter import OpenAICompatibleAdapter
from vao.swebench_orchestration.schemas import (
    ComponentSpec,
    OrchestrationDesign,
    OrchestrationSpec,
    SWEInstancePublic,
    TraceStep,
)


ALLOWED_RUNTIME_ADAPTERS = {"openai_compatible", "codex_cli"}
REJECTED_RUNTIME_ADAPTERS = {
    "anthropic",
    "claude",
    "claude_code",
    "claude_haiku",
    "local_stub",
    "openai_responses",
}
PROPRIETARY_MODEL_PATTERNS = (
    "claude",
    "codex",
    "gpt-",
    "gpt_",
    "o1",
    "o3",
    "o4",
    "openai/",
)
PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "model_patch": {"type": "string"},
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["model_patch", "summary", "confidence"],
    "additionalProperties": False,
}
OBSERVATION_SCHEMA = {
    "type": "object",
    "properties": {
        "mode": {"type": "string"},
        "candidate_files": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["notes", "mode", "candidate_files", "confidence"],
    "additionalProperties": False,
}
LIMITATIONS = [
    "Repository checkouts are materialized only when executor.materialize_checkouts is enabled.",
    "This executor does not run target tests or the official SWE-bench verifier inline.",
    "Predictions are patch-generation-only and are emitted as unverified candidates.",
]


@dataclass(frozen=True)
class WorkerConfig:
    alias: str
    adapter: str
    model_id: str
    base_url: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class ExecutorConfig:
    design_path: Path
    instances_path: Path
    workers_config_path: Path
    output_dir: Path
    orchestration_id: str | None
    run_id: str
    split: str
    max_instances: int | None
    parallel_workers: int
    max_calls_per_component: int | None
    dry_run: bool
    materialize_checkouts: bool = False
    checkout_root: Path | None = None
    keep_checkouts: bool = False
    patch_repair_attempts: int = 0
    public_literal_repair_enabled: bool = False
    patch_apply_timeout_seconds: int = 30
    repo_context_enabled: bool = False
    repo_cache_dir: Path | None = None
    repo_work_dir: Path | None = None
    repo_urls: dict[str, str] = field(default_factory=dict)
    repo_context_max_tree_entries: int = 160
    repo_context_max_search_queries: int = 12
    repo_context_max_search_hits: int = 28
    repo_context_max_candidate_files: int = 8
    repo_context_max_snippet_chars: int = 18_000
    repo_context_command_timeout_seconds: int = 120


@dataclass
class InstanceResult:
    instance_id: str
    prediction: dict[str, str]
    traces: list[TraceStep]


@dataclass(frozen=True)
class InstanceWorkspace:
    checkout_dir: Path | None
    error: str | None = None


def read_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_design(path: Path) -> OrchestrationDesign:
    return OrchestrationDesign.model_validate(json.loads(path.read_text(encoding="utf-8")))


def select_orchestration(design: OrchestrationDesign, orchestration_id: str | None) -> OrchestrationSpec:
    if orchestration_id is None:
        return design.orchestration
    if design.orchestration.orchestration_id == orchestration_id:
        return design.orchestration
    raise KeyError(f"Unknown orchestration_id {orchestration_id!r}")


def load_worker_configs(path: Path) -> dict[str, WorkerConfig]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_workers = _normalize_worker_payload(payload)
    workers: dict[str, WorkerConfig] = {}
    for alias, config in raw_workers.items():
        workers[alias] = _validate_worker_config(alias, config)
    return workers


def validate_orchestration_workers(orchestration: OrchestrationSpec, workers: dict[str, WorkerConfig]) -> None:
    missing = sorted({component.model for component in orchestration.components if component.model not in workers})
    if missing:
        raise KeyError(f"Orchestration references unknown worker aliases: {missing}")


def run_executor(config: ExecutorConfig) -> dict[str, Any]:
    design = load_design(config.design_path)
    orchestration = select_orchestration(design, config.orchestration_id)
    workers = load_worker_configs(config.workers_config_path)
    validate_orchestration_workers(orchestration, workers)
    instances = [
        SWEInstancePublic.model_validate(row)
        for row in read_jsonl(config.instances_path, limit=config.max_instances)
    ]

    config.output_dir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(config.parallel_workers, 1)) as pool:
        futures = {
            pool.submit(
                execute_instance,
                instance=instance,
                design=design,
                orchestration=orchestration,
                workers=workers,
                config=config,
            ): instance
            for instance in instances
        }
        results = []
        for future in concurrent.futures.as_completed(futures):
            instance = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover - backend failures vary by environment.
                results.append(
                    _instance_failure_result(
                        instance=instance,
                        design=design,
                        orchestration=orchestration,
                        config=config,
                        error=f"{type(exc).__name__}:{exc}",
                    )
                )
    results.sort(key=lambda item: item.instance_id)

    traces = [trace.model_dump(mode="json") for result in results for trace in result.traces]
    predictions = [result.prediction for result in results]
    traces_path = config.output_dir / "traces.jsonl"
    predictions_path = config.output_dir / "predictions.jsonl"
    manifest_path = config.output_dir / "executor_manifest.json"
    write_jsonl(traces_path, traces)
    write_jsonl(predictions_path, predictions)

    manifest = {
        "run_id": config.run_id,
        "design_path": str(config.design_path),
        "instances_path": str(config.instances_path),
        "workers_config_path": str(config.workers_config_path),
        "orchestration_id": orchestration.orchestration_id,
        "dry_run": config.dry_run,
        "materialize_checkouts": config.materialize_checkouts,
        "checkout_root": str(_checkout_root(config)) if config.materialize_checkouts else None,
        "keep_checkouts": config.keep_checkouts,
        "instances": len(instances),
        "parallel_workers": config.parallel_workers,
        "max_calls_per_component": config.max_calls_per_component,
        "patch_repair_attempts": config.patch_repair_attempts,
        "public_literal_repair_enabled": config.public_literal_repair_enabled,
        "patch_apply_timeout_seconds": config.patch_apply_timeout_seconds,
        "repo_context_enabled": config.repo_context_enabled,
        "repo_cache_dir": str(config.repo_cache_dir or Path("swebench/repos/cache")),
        "repo_work_dir": str(config.repo_work_dir or default_work_dir(config.output_dir, config.run_id)),
        "traces_path": str(traces_path),
        "predictions_path": str(predictions_path),
        "limitations": LIMITATIONS,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def execute_instance(
    *,
    instance: SWEInstancePublic,
    design: OrchestrationDesign,
    orchestration: OrchestrationSpec,
    workers: dict[str, WorkerConfig],
    config: ExecutorConfig,
) -> InstanceResult:
    run_id = f"{config.run_id}_{instance.instance_id}"
    traces: list[TraceStep] = []
    observations: list[dict[str, Any]] = []
    selected_patch = ""
    selected_model = orchestration.orchestration_id
    step = 1
    repo_context = _build_repo_context(instance=instance, config=config, run_id=run_id)
    repo_context_path = _write_repo_context_artifact(
        output_dir=config.output_dir,
        instance_id=instance.instance_id,
        repo_context=repo_context,
    )
    workspace = (
        InstanceWorkspace(checkout_dir=Path(repo_context.checkout_path))
        if repo_context.status == "ready" and repo_context.checkout_path
        else _instance_workspace(instance, config)
    )

    traces.append(
        _trace(
            run_id=run_id,
            design=design,
            orchestration=orchestration,
            instance=instance,
            config=config,
            step=step,
            phase="observe",
            agent_id="executor",
            model_id=None,
            wall_seconds=0.0,
            extra={
                "limitations": LIMITATIONS,
                "repo_context_path": str(repo_context_path) if repo_context_path else None,
                **repo_context.trace_payload(),
            },
        )
    )
    step += 1

    if workspace.error is not None:
        traces.append(
            _trace(
                run_id=run_id,
                design=design,
                orchestration=orchestration,
                instance=instance,
                config=config,
                step=step,
                phase="other",
                agent_id="checkout",
                model_id=None,
                wall_seconds=0.0,
                error=workspace.error,
                extra={
                    "checkout_dir": str(workspace.checkout_dir) if workspace.checkout_dir else None,
                    "repo_context_path": str(repo_context_path) if repo_context_path else None,
                    **repo_context.trace_payload(),
                },
            )
        )
        return InstanceResult(
            instance_id=instance.instance_id,
            prediction={
                "instance_id": instance.instance_id,
                "model_name_or_path": selected_model,
                "model_patch": selected_patch,
            },
            traces=traces,
        )

    try:
        for component in orchestration.components:
            base_calls = _bounded_calls(component.max_calls, config.max_calls_per_component)
            granted_repair_calls = 0
            call_index = 0
            while call_index < base_calls + granted_repair_calls:
                worker = workers[component.model]
                started = time.perf_counter()
                error: str | None = None
                payload: dict[str, Any] = {}
                usage_meta: dict[str, Any] = {}
                phase = _phase_for_component(component)
                patch_apply_check: dict[str, Any] | None = None
                patch_repair_retry_granted = False
                try:
                    if config.dry_run:
                        payload, usage_meta = _dry_run_payload(component, instance)
                    else:
                        payload, usage_meta = _call_worker(
                            worker=worker,
                            component=component,
                            instance=instance,
                            orchestration=orchestration,
                            observations=observations,
                            repo_context=repo_context,
                            call_index=call_index,
                            checkout_dir=workspace.checkout_dir,
                        )
                except Exception as exc:  # pragma: no cover - exact backend errors vary.
                    error = f"{type(exc).__name__}:{exc}"
                wall_seconds = time.perf_counter() - started

                usage = _usage(usage_meta)
                candidate_patch = ""
                if error is None and _is_patch_component(component):
                    candidate_patch = _extract_patch(payload)
                    if not candidate_patch and workspace.checkout_dir is not None:
                        candidate_patch = _git_diff(workspace.checkout_dir)
                    if candidate_patch:
                        patch_apply_check = _check_patch_applicable(
                            patch=candidate_patch,
                            repo_context=repo_context,
                            checkout_dir=workspace.checkout_dir,
                            timeout=config.patch_apply_timeout_seconds,
                        )
                        if patch_apply_check.get("status") in {"passed", "skipped_no_checkout"}:
                            selected_patch = candidate_patch
                            selected_model = worker.model_id
                        elif granted_repair_calls < config.patch_repair_attempts:
                            granted_repair_calls += 1
                            patch_repair_retry_granted = True
                traces.append(
                    _trace(
                        run_id=run_id,
                        design=design,
                        orchestration=orchestration,
                        instance=instance,
                        config=config,
                        step=step,
                        phase=phase,
                        agent_id=component.component_id,
                        model_id=worker.alias,
                        input_tokens=usage["input_tokens"],
                        output_tokens=usage["output_tokens"],
                        api_cost_usd=_api_cost(usage_meta),
                        wall_seconds=wall_seconds,
                        error=error,
                        extra={
                            "component_role": component.role,
                            "model_name_or_path": worker.model_id,
                            "endpoint": worker.base_url,
                            "dry_run": config.dry_run,
                            "call_index": call_index,
                            "checkout_dir": str(workspace.checkout_dir) if workspace.checkout_dir else None,
                            "payload_summary": _payload_summary(payload),
                            "patch_empty_reason": _patch_empty_reason(component=component, payload=payload, error=error),
                            "patch_apply_check": patch_apply_check,
                            "patch_repair_retry_granted": patch_repair_retry_granted,
                        },
                    )
                )
                step += 1

                if error is not None:
                    call_index += 1
                    continue
                observations.append({"component_id": component.component_id, "role": component.role, "payload": payload})
                if selected_patch:
                    break
                call_index += 1
            if selected_patch:
                break

        if (
            not selected_patch
            and config.public_literal_repair_enabled
            and _orchestration_allows_public_literal_repair(orchestration)
        ):
            started = time.perf_counter()
            payload = _public_literal_replacement_patch(instance=instance, repo_context=repo_context)
            candidate_patch = _extract_patch(payload)
            apply_check = (
                _check_patch_applicable(
                    patch=candidate_patch,
                    repo_context=repo_context,
                    checkout_dir=workspace.checkout_dir,
                    timeout=config.patch_apply_timeout_seconds,
                )
                if candidate_patch
                else {"status": "skipped_empty_patch"}
            )
            if candidate_patch and apply_check.get("status") in {"passed", "skipped_no_checkout"}:
                selected_patch = candidate_patch
                selected_model = f"{orchestration.orchestration_id}:public_literal_repair"
            traces.append(
                _trace(
                    run_id=run_id,
                    design=design,
                    orchestration=orchestration,
                    instance=instance,
                    config=config,
                    step=step,
                    phase="fallback",
                    agent_id="public_literal_repair",
                    model_id=None,
                    wall_seconds=time.perf_counter() - started,
                    extra={
                        "component_role": "deterministic_repair",
                        "model_name_or_path": selected_model,
                        "payload_summary": _payload_summary(payload),
                        "patch_empty_reason": _patch_empty_reason(
                            component=ComponentSpec(
                                component_id="public_literal_repair",
                                role="patcher",
                                model=orchestration.components[0].model,
                                prompt_summary="deterministic public literal repair",
                                max_calls=1,
                                output_contract="model_patch unified diff",
                            ),
                            payload=payload,
                            error=None,
                        ),
                        "patch_apply_check": apply_check,
                        "public_literal_repair": True,
                        "public_literal_repair_payload": {
                            key: value for key, value in payload.items() if key != "model_patch"
                        },
                    },
                )
            )
            step += 1
    finally:
        _cleanup_workspace(workspace, config)

    traces.append(
        _trace(
            run_id=run_id,
            design=design,
            orchestration=orchestration,
            instance=instance,
            config=config,
            step=step,
            phase="verify",
            agent_id="executor",
            model_id=None,
            wall_seconds=0.0,
            verified=False,
            error="not_implemented:target_tests_and_swebench_verifier_are_not_run_inline_by_executor",
            extra={
                "limitations": LIMITATIONS,
                "stopping_reason": "local_applyable_patch_selected" if selected_patch else "no_local_applyable_patch",
                "selected_patch_chars": len(selected_patch),
                "selected_patch_modified_files": _modified_files_from_patch(selected_patch),
                "repo_context_path": str(repo_context_path) if repo_context_path else None,
                **repo_context.trace_payload(),
            },
        )
    )

    return InstanceResult(
        instance_id=instance.instance_id,
        prediction={
            "instance_id": instance.instance_id,
            "model_name_or_path": selected_model,
            "model_patch": selected_patch,
        },
        traces=traces,
    )


def _instance_failure_result(
    *,
    instance: SWEInstancePublic,
    design: OrchestrationDesign,
    orchestration: OrchestrationSpec,
    config: ExecutorConfig,
    error: str,
) -> InstanceResult:
    trace = _trace(
        run_id=f"{config.run_id}_{instance.instance_id}",
        design=design,
        orchestration=orchestration,
        instance=instance,
        config=config,
        step=1,
        phase="other",
        agent_id="executor",
        model_id=None,
        error=f"instance_execution_failed:{error}",
        extra={"instance_failure_error": error},
    )
    return InstanceResult(
        instance_id=instance.instance_id,
        prediction={
            "instance_id": instance.instance_id,
            "model_name_or_path": orchestration.orchestration_id,
            "model_patch": "",
        },
        traces=[trace],
    )


def _instance_workspace(instance: SWEInstancePublic, config: ExecutorConfig) -> InstanceWorkspace:
    if config.dry_run or not config.materialize_checkouts:
        return InstanceWorkspace(checkout_dir=None)
    if not instance.repo or not instance.base_commit:
        return InstanceWorkspace(
            checkout_dir=None,
            error="checkout_unavailable:instance_missing_repo_or_base_commit",
        )
    checkout_root = _checkout_root(config)
    checkout_dir = checkout_root / "instances" / _safe_path_name(instance.instance_id)
    try:
        _prepare_checkout(repo=instance.repo, base_commit=instance.base_commit, checkout_root=checkout_root, checkout_dir=checkout_dir)
    except Exception as exc:  # pragma: no cover - network/git failures are environment-specific.
        return InstanceWorkspace(checkout_dir=checkout_dir, error=f"checkout_failed:{type(exc).__name__}:{exc}")
    return InstanceWorkspace(checkout_dir=checkout_dir)


def _checkout_root(config: ExecutorConfig) -> Path:
    return (config.checkout_root or (config.output_dir / "checkouts")).resolve()


def _prepare_checkout(*, repo: str, base_commit: str, checkout_root: Path, checkout_dir: Path) -> None:
    cache_root = checkout_root / "_repo_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    safe_repo = _safe_path_name(repo)
    repo_cache = cache_root / f"{safe_repo}.git"
    clone_url = f"https://github.com/{repo}"
    if not repo_cache.exists():
        _run_git(
            [
                "git",
                "clone",
                "--bare",
                clone_url,
                str(repo_cache),
            ],
            cwd=checkout_root,
            timeout=1800,
        )
    if checkout_dir.exists():
        shutil.rmtree(checkout_dir)
    checkout_dir.parent.mkdir(parents=True, exist_ok=True)
    _run_git(["git", "clone", "--shared", str(repo_cache), str(checkout_dir)], cwd=checkout_root, timeout=900)
    try:
        _run_git(["git", "checkout", "--force", base_commit], cwd=checkout_dir, timeout=900)
    except RuntimeError:
        _run_git(["git", "fetch", "--all", "--tags"], cwd=repo_cache, timeout=1800)
        _run_git(["git", "checkout", "--force", base_commit], cwd=checkout_dir, timeout=900)
    _run_git(["git", "config", "user.email", "swebench-orchestration@local.invalid"], cwd=checkout_dir, timeout=60)
    _run_git(["git", "config", "user.name", "SWE-bench Orchestration"], cwd=checkout_dir, timeout=60)
    _run_git(["git", "config", "--global", "--add", "safe.directory", str(checkout_dir)], cwd=checkout_dir, timeout=60)


def _run_git(command: list[str], *, cwd: Path, timeout: int) -> None:
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if proc.returncode:
        detail = (proc.stderr or proc.stdout)[-1200:]
        raise RuntimeError(f"{' '.join(command)} failed with {proc.returncode}: {detail}")


def _git_diff(checkout_dir: Path) -> str:
    proc = subprocess.run(
        ["git", "diff", "--binary"],
        cwd=checkout_dir,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode:
        return ""
    return proc.stdout.strip()


def _cleanup_workspace(workspace: InstanceWorkspace, config: ExecutorConfig) -> None:
    if config.keep_checkouts or workspace.checkout_dir is None:
        return
    shutil.rmtree(workspace.checkout_dir, ignore_errors=True)


def _safe_path_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "__", value)
    return safe.strip("._-") or "unnamed"


def _build_repo_context(*, instance: SWEInstancePublic, config: ExecutorConfig, run_id: str) -> RepoContext:
    if config.dry_run:
        return RepoContext(repo=instance.repo, base_commit=instance.base_commit, status="disabled")
    return build_repository_context(
        instance=instance,
        config=_repo_context_config(config),
        run_id=run_id,
        output_dir=config.output_dir,
    )


def _repo_context_config(config: ExecutorConfig) -> RepoContextConfig:
    return RepoContextConfig(
        enabled=config.repo_context_enabled,
        cache_dir=config.repo_cache_dir or Path("swebench/repos/cache"),
        work_dir=config.repo_work_dir,
        repo_urls=config.repo_urls,
        max_tree_entries=config.repo_context_max_tree_entries,
        max_search_queries=config.repo_context_max_search_queries,
        max_search_hits=config.repo_context_max_search_hits,
        max_candidate_files=config.repo_context_max_candidate_files,
        max_snippet_chars=config.repo_context_max_snippet_chars,
        command_timeout_seconds=config.repo_context_command_timeout_seconds,
    )


def _write_repo_context_artifact(
    *, output_dir: Path, instance_id: str, repo_context: RepoContext
) -> Path | None:
    if repo_context.status in {"disabled", "skipped_no_base_commit"}:
        return None
    context_dir = output_dir / "repo_context"
    context_dir.mkdir(parents=True, exist_ok=True)
    path = context_dir / f"{_safe_filename(instance_id)}.json"
    path.write_text(json.dumps(repo_context.prompt_payload(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", value).strip("._-") or "instance"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Optional executor experiment YAML.")
    parser.add_argument("--design", default=None, help="Frozen orchestration design JSON.")
    parser.add_argument("--instances", default=None, help="SWE-bench public instances JSONL.")
    parser.add_argument("--workers-config", default=None, help="Open-source worker model YAML.")
    parser.add_argument("--orchestration-id", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--split", default=None)
    parser.add_argument("--max-instances", type=int, default=None)
    parser.add_argument("--parallel-workers", type=int, default=None)
    parser.add_argument(
        "--max-calls-per-component",
        default=None,
        help="Optional executor-level cap. Use a positive integer, 0, null, none, or unbounded.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate flow without calling GPU endpoints.")
    parser.add_argument("--materialize-checkouts", action="store_true", help="Clone SWE-bench repos before worker calls.")
    parser.add_argument("--checkout-root", default=None, help="Directory for per-instance checkouts and repo cache.")
    parser.add_argument("--keep-checkouts", action="store_true", help="Keep cloned SWE-bench worktrees after each instance.")
    parser.add_argument("--repo-cache-dir", default=None, help="Durable bare clone cache for SWE-bench repos.")
    parser.add_argument("--repo-work-dir", default=None, help="Per-run repository working-copy root.")
    parser.add_argument("--no-repo-context", action="store_true", help="Disable repository context extraction.")
    return parser


def config_from_args(args: argparse.Namespace) -> ExecutorConfig:
    file_config = _load_yaml(Path(args.config)) if args.config else {}
    executor = file_config.get("executor", {})
    experiment = file_config.get("experiment", {})
    repo_settings_raw = executor.get("repo_context", {})
    if isinstance(repo_settings_raw, bool):
        repo_settings: dict[str, Any] = {"enabled": repo_settings_raw}
    elif isinstance(repo_settings_raw, dict):
        repo_settings = repo_settings_raw
    else:
        repo_settings = {}
    run_id = args.run_id or executor.get("run_id") or experiment.get("name") or "swebench_orchestration_executor"
    output_dir = Path(args.output_dir or executor.get("output_dir") or "swebench/studies/open_source_orchestration/runs/pilot/executor")
    materialize_checkouts = bool(args.materialize_checkouts or executor.get("materialize_checkouts", False))
    repo_context_enabled = bool(
        repo_settings.get("enabled", executor.get("repo_context_enabled", materialize_checkouts))
    )
    if args.no_repo_context:
        repo_context_enabled = False
    repo_cache_dir = Path(
        args.repo_cache_dir
        or executor.get("repo_cache_dir")
        or repo_settings.get("cache_dir")
        or "swebench/repos/cache"
    )
    repo_work_dir_value = (
        args.repo_work_dir
        or executor.get("repo_work_dir")
        or repo_settings.get("work_dir")
        or args.checkout_root
        or executor.get("checkout_root")
    )
    repo_work_dir = Path(repo_work_dir_value) if repo_work_dir_value else default_work_dir(output_dir, str(run_id))
    return ExecutorConfig(
        design_path=Path(_required(args.design or executor.get("design"), "--design")),
        instances_path=Path(
            _required(args.instances or executor.get("instances") or experiment.get("public_instances"), "--instances")
        ),
        workers_config_path=Path(
            _required(
                args.workers_config
                or executor.get("workers_config")
                or "swebench/studies/open_source_orchestration/configs/swebench_open_source_workers.yaml",
                "--workers-config",
            )
        ),
        output_dir=output_dir,
        orchestration_id=args.orchestration_id or executor.get("orchestration_id"),
        run_id=str(run_id),
        split=str(args.split or executor.get("split") or experiment.get("split") or "test"),
        max_instances=args.max_instances if args.max_instances is not None else executor.get("max_instances"),
        parallel_workers=int(
            args.parallel_workers if args.parallel_workers is not None else executor.get("parallel_workers", 1)
        ),
        max_calls_per_component=_optional_positive_int_from_any(
            args.max_calls_per_component
            if args.max_calls_per_component is not None
            else executor.get("max_calls_per_component", 1),
            default=1,
        ),
        dry_run=bool(args.dry_run or executor.get("dry_run", False)),
        materialize_checkouts=materialize_checkouts,
        checkout_root=Path(args.checkout_root or executor["checkout_root"]) if args.checkout_root or executor.get("checkout_root") else None,
        keep_checkouts=bool(args.keep_checkouts or executor.get("keep_checkouts", False)),
        patch_repair_attempts=max(0, _int_from_any(executor.get("patch_repair_attempts"), 0)),
        public_literal_repair_enabled=bool(executor.get("public_literal_repair_enabled", False)),
        patch_apply_timeout_seconds=max(1, _int_from_any(executor.get("patch_apply_timeout_seconds"), 30)),
        repo_context_enabled=repo_context_enabled,
        repo_cache_dir=repo_cache_dir,
        repo_work_dir=repo_work_dir,
        repo_urls={str(key): str(value) for key, value in (repo_settings.get("repo_urls") or {}).items()},
        repo_context_max_tree_entries=int(repo_settings.get("max_tree_entries", 160)),
        repo_context_max_search_queries=int(repo_settings.get("max_search_queries", 12)),
        repo_context_max_search_hits=int(repo_settings.get("max_search_hits", 28)),
        repo_context_max_candidate_files=int(repo_settings.get("max_candidate_files", 8)),
        repo_context_max_snippet_chars=int(repo_settings.get("max_snippet_chars", 18_000)),
        repo_context_command_timeout_seconds=int(repo_settings.get("command_timeout_seconds", 120)),
    )


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    config = config_from_args(parser.parse_args(argv))
    result = run_executor(config)
    print(json.dumps(result, indent=2, sort_keys=True))


def _normalize_worker_payload(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if isinstance(payload.get("workers"), dict):
        return {str(alias): dict(config or {}) for alias, config in payload["workers"].items()}
    if isinstance(payload.get("models"), dict):
        return {str(alias): dict(config or {}) for alias, config in payload["models"].items()}
    if isinstance(payload.get("worker_models"), list):
        normalized: dict[str, dict[str, Any]] = {}
        for row in payload["worker_models"]:
            if not isinstance(row, dict) or "alias" not in row:
                raise ValueError("worker_models entries must be objects with an alias")
            config = dict(row)
            alias = str(config.pop("alias"))
            config.setdefault("adapter", "openai_compatible")
            if "endpoint" in config and "base_url" not in config:
                config["base_url"] = config.pop("endpoint")
            normalized[alias] = config
        return normalized
    raise ValueError("Worker YAML must contain a workers, models, or worker_models mapping")


def _validate_worker_config(alias: str, config: dict[str, Any]) -> WorkerConfig:
    adapter = str(config.get("adapter", ""))
    adapter_key = adapter.lower()
    if adapter_key in REJECTED_RUNTIME_ADAPTERS or adapter_key not in ALLOWED_RUNTIME_ADAPTERS:
        raise ValueError(f"Runtime worker {alias!r} uses disallowed adapter {adapter!r}")
    if adapter_key == "openai_compatible" and config.get("open_source") is not True:
        raise ValueError(f"Runtime worker {alias!r} must declare open_source: true")
    model_id = str(config.get("model_id") or "")
    if not model_id:
        raise ValueError(f"Runtime worker {alias!r} is missing model_id")
    if adapter_key == "openai_compatible" and (_looks_proprietary(alias) or _looks_proprietary(model_id)):
        raise ValueError(f"Runtime worker {alias!r} has a proprietary-looking model_id {model_id!r}")
    base_url = config.get("base_url") or config.get("endpoint")
    if adapter_key == "openai_compatible" and not base_url:
        raise ValueError(f"Runtime worker {alias!r} is missing base_url")
    return WorkerConfig(alias=alias, adapter=adapter_key, model_id=model_id, base_url=str(base_url) if base_url else None, raw=dict(config))


def _looks_proprietary(value: str) -> bool:
    lowered = value.lower()
    return any(pattern in lowered for pattern in PROPRIETARY_MODEL_PATTERNS)


def _call_worker(
    *,
    worker: WorkerConfig,
    component: ComponentSpec,
    instance: SWEInstancePublic,
    orchestration: OrchestrationSpec,
    observations: list[dict[str, Any]],
    repo_context: RepoContext,
    call_index: int,
    checkout_dir: Path | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    adapter = _build_adapter(worker, working_dir=checkout_dir)
    prompt = _render_component_prompt(
        component=component,
        instance=instance,
        orchestration=orchestration,
        observations=observations,
        repo_context=repo_context,
        call_index=call_index,
        checkout_dir=checkout_dir,
    )
    patch_like = component.role in {"patcher", "fallback"}
    schema = PATCH_SCHEMA if patch_like else OBSERVATION_SCHEMA
    max_tokens = int(worker.raw.get("max_tokens_patch" if patch_like else "max_tokens_observe", 4096))
    raw, usage = adapter._complete(prompt, schema, max_tokens=max_tokens)
    return _parse_json_object(raw), usage


def _build_adapter(worker: WorkerConfig, *, working_dir: Path | None = None) -> OpenAICompatibleAdapter | CodexCliAdapter:
    if worker.adapter == "codex_cli":
        allowed_keys = {
            "model_id",
            "timeout_seconds",
            "max_tokens_distribution",
            "max_tokens_edit",
            "max_tokens_batch",
            "retries",
            "edit_protocol",
            "reasoning_effort",
            "sandbox",
            "use_output_schema",
            "use_json_schema",
            "extra_cli_args",
            "working_dir",
        }
        adapter_config = {key: value for key, value in worker.raw.items() if key in allowed_keys}
        adapter_config["model_id"] = worker.model_id
        if working_dir is not None:
            adapter_config["working_dir"] = working_dir
        return CodexCliAdapter(**adapter_config)

    allowed_keys = {
        "model_id",
        "base_url",
        "api_key",
        "temperature",
        "timeout_seconds",
        "max_tokens_distribution",
        "max_tokens_edit",
        "max_tokens_batch",
        "retries",
        "edit_protocol",
        "use_response_format",
        "allow_response_format_retry",
        "extra_body",
    }
    adapter_config = {key: value for key, value in worker.raw.items() if key in allowed_keys}
    adapter_config["model_id"] = worker.model_id
    adapter_config["base_url"] = worker.base_url
    return OpenAICompatibleAdapter(**adapter_config)


def _render_component_prompt(
    *,
    component: ComponentSpec,
    instance: SWEInstancePublic,
    orchestration: OrchestrationSpec,
    observations: list[dict[str, Any]],
    repo_context: RepoContext,
    call_index: int,
    checkout_dir: Path | None,
) -> str:
    if component.role in {"patcher", "fallback"}:
        output_instruction = (
            "Return JSON with model_patch set to a unified diff that can be placed in SWE-bench predictions.jsonl. "
            "If the public evidence is insufficient, return an empty string and explain why in summary."
        )
    else:
        output_instruction = (
            "Return JSON with notes, optional mode, optional candidate_files, and confidence. "
            "Do not invent private test results or repository contents."
        )
    return "\n\n".join(
        [
            "You are a model worker in a frozen SWE-bench orchestration.",
            f"Component id: {component.component_id}",
            f"Component role: {component.role}",
            f"Component prompt summary: {component.prompt_summary}",
            f"Output contract: {component.output_contract}",
            f"Call index: {call_index}",
            f"Orchestration id: {orchestration.orchestration_id}",
            f"Objective: {orchestration.objective_summary}",
            f"Routing policy: {orchestration.routing_policy}",
            f"Evidence policy: {orchestration.evidence_policy}",
            f"Patch policy: {orchestration.patch_policy}",
            f"Verification policy: {orchestration.verification_policy}",
            _checkout_prompt_line(checkout_dir),
            "Current runtime limitations: target tests and SWE-bench verifier calls are not run inline by this executor.",
            "Public SWE-bench instance:",
            json.dumps(safe_instance_payload(instance), indent=2, sort_keys=True),
            "Leakage-safe repository context:",
            json.dumps(repo_context.prompt_payload(), indent=2, sort_keys=True),
            "Prior component outputs:",
            json.dumps(observations, indent=2, sort_keys=True),
            output_instruction,
        ]
    )


def _dry_run_payload(component: ComponentSpec, instance: SWEInstancePublic) -> tuple[dict[str, Any], dict[str, Any]]:
    if component.role in {"patcher", "fallback"}:
        return (
            {
                "model_patch": "",
                "summary": (
                    "dry_run: no worker endpoint was called, so no SWE-bench patch was generated "
                    f"for {instance.instance_id}."
                ),
                "confidence": 0.0,
            },
            {"usage": {"input_tokens": 0, "output_tokens": 0}, "cost_usd": 0.0},
        )
    return (
        {"notes": "dry_run: no worker endpoint was called.", "mode": instance.declared_mode, "confidence": 0.0},
        {"usage": {"input_tokens": 0, "output_tokens": 0}, "cost_usd": 0.0},
    )


def _checkout_prompt_line(checkout_dir: Path | None) -> str:
    if checkout_dir is None:
        return (
            "Repository checkout: not materialized for this run. Use only the public instance fields "
            "and return an empty patch if the evidence is insufficient."
        )
    return (
        f"Repository checkout: {checkout_dir}. Inspect this checkout before patching. If you edit files, "
        "return JSON whose model_patch is the unified diff from `git diff --binary`; do not leave the "
        "final patch only as prose."
    )


def _trace(
    *,
    run_id: str,
    design: OrchestrationDesign,
    orchestration: OrchestrationSpec,
    instance: SWEInstancePublic,
    config: ExecutorConfig,
    step: int,
    phase: str,
    agent_id: str | None,
    model_id: str | None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    api_cost_usd: float = 0.0,
    wall_seconds: float = 0.0,
    verified: bool = False,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> TraceStep:
    payload = {
        "run_id": run_id,
        "orchestration_id": orchestration.orchestration_id,
        "evidence_level": design.evidence_level,
        "instance_id": instance.instance_id,
        "repo": instance.repo,
        "mode": instance.declared_mode,
        "split": config.split,
        "step": step,
        "phase": phase,
        "agent_id": agent_id,
        "model_id": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "api_cost_usd": api_cost_usd,
        "wall_seconds": wall_seconds,
        "test_seconds": 0.0,
        "verifier_calls": 0,
        "patch_id": None,
        "verified": verified,
        "used_in_verified_path": True,
        "error": error,
    }
    if extra:
        payload.update(extra)
    return TraceStep.model_validate(payload)


def _phase_for_component(component: ComponentSpec) -> str:
    return {
        "router": "localize",
        "localizer": "localize",
        "patcher": "patch",
        "reviewer": "review",
        "tester": "verify",
        "fallback": "fallback",
        "controller": "other",
    }.get(component.role, "other")


def _is_patch_component(component: ComponentSpec) -> bool:
    contract = component.output_contract.lower()
    prompt = component.prompt_summary.lower()
    return component.role == "patcher" or (
        component.role == "fallback" and ("patch" in contract or "diff" in contract or "patch" in prompt)
    )


def _bounded_calls(spec_calls: int, configured_max: int | None) -> int:
    if spec_calls <= 0:
        return 0
    if configured_max is None:
        return spec_calls
    if configured_max <= 0:
        return 0
    return min(spec_calls, configured_max)


def _check_patch_applicable(
    *,
    patch: str,
    repo_context: RepoContext,
    checkout_dir: Path | None,
    timeout: int,
) -> dict[str, Any]:
    if not patch.strip():
        return {"status": "skipped_empty_patch", "patch_chars": 0}
    apply_dir = Path(repo_context.checkout_path) if repo_context.status == "ready" and repo_context.checkout_path else checkout_dir
    if apply_dir is None:
        return {
            "status": "skipped_no_checkout",
            "patch_chars": len(patch),
            "repo_context_status": repo_context.status,
        }
    command = ["git", "-C", str(apply_dir), "apply", "--check", "--whitespace=nowarn", "-"]
    try:
        completed = subprocess.run(
            command,
            input=patch,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "command": " ".join(command),
            "patch_chars": len(patch),
            "timeout_seconds": timeout,
            "stdout_preview": _preview(exc.stdout or "", 500) if isinstance(exc.stdout, str) else "",
            "stderr_preview": _preview(exc.stderr or "", 500) if isinstance(exc.stderr, str) else "",
        }
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": " ".join(command),
        "patch_chars": len(patch),
        "returncode": completed.returncode,
        "stdout_preview": _preview(completed.stdout or "", 500),
        "stderr_preview": _preview(completed.stderr or "", 500),
    }


def _public_literal_replacement_patch(*, instance: SWEInstancePublic, repo_context: RepoContext) -> dict[str, Any]:
    if repo_context.status != "ready" or not repo_context.checkout_path:
        return {
            "model_patch": "",
            "summary": "public_literal_repair skipped: no leakage-safe checkout is available.",
            "confidence": 0.0,
        }
    literals = _issue_backtick_literals(instance.problem_statement)
    if len(literals) < 2:
        return {
            "model_patch": "",
            "summary": "public_literal_repair skipped: fewer than two public backtick literals found.",
            "confidence": 0.0,
        }
    checkout = Path(repo_context.checkout_path)
    candidate_files = _dedupe(
        [
            *[str(path) for path in repo_context.candidate_files],
            *[
                str(snippet.get("path"))
                for snippet in repo_context.snippets
                if isinstance(snippet, dict) and snippet.get("path")
            ],
        ]
    )
    for path in candidate_files:
        if not _is_likely_implementation_file(path):
            continue
        file_path = checkout / path
        if not file_path.exists() or not file_path.is_file():
            continue
        original = file_path.read_text(encoding="utf-8", errors="replace")
        for old_literal, new_literal in _literal_replacement_pairs(literals):
            if old_literal not in original or old_literal == new_literal:
                continue
            updated = original.replace(old_literal, new_literal, 1)
            patch = _unified_file_replacement_patch(path=path, original=original, updated=updated)
            return {
                "model_patch": patch,
                "summary": "public_literal_repair replaced an explicit public old/new literal pair.",
                "confidence": 0.95,
                "modified_file": path,
                "old_literal": old_literal,
                "new_literal": new_literal,
                "repair_policy": "public_literal_repair",
            }
    return {
        "model_patch": "",
        "summary": "public_literal_repair skipped: public old literal was not found in candidate implementation files.",
        "confidence": 0.0,
    }


def _orchestration_allows_public_literal_repair(orchestration: OrchestrationSpec) -> bool:
    haystack = "\n".join(
        [
            orchestration.routing_policy,
            orchestration.evidence_policy,
            orchestration.patch_policy,
            orchestration.verification_policy,
            orchestration.fallback_policy,
            *[
                " ".join([component.prompt_summary, component.output_contract, " ".join(component.tools)])
                for component in orchestration.components
            ],
        ]
    ).lower()
    return "public_literal_repair" in haystack


def _issue_backtick_literals(problem_statement: str) -> list[str]:
    values = [match.strip() for match in re.findall(r"`([^`]+)`", problem_statement or "")]
    return [value for value in values if value]


def _literal_replacement_pairs(literals: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for old_index, old_literal in enumerate(literals):
        for new_literal in literals[old_index + 1 :]:
            if old_literal != new_literal:
                pairs.append((old_literal, new_literal))
    return pairs


def _unified_file_replacement_patch(*, path: str, original: str, updated: str) -> str:
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    return "\n".join([f"diff --git a/{path} b/{path}", *diff_lines]) + "\n"


def _extract_patch(payload: dict[str, Any]) -> str:
    patch = payload.get("model_patch") or payload.get("patch") or payload.get("unified_diff") or ""
    if not isinstance(patch, str):
        return ""
    stripped = _strip_code_fences(patch)
    return stripped if stripped.strip() else ""


def _patch_empty_reason(*, component: ComponentSpec, payload: dict[str, Any], error: str | None) -> str:
    if not _is_patch_component(component):
        return "not_patch_component"
    if error is not None:
        return "worker_error"
    if not payload:
        return "empty_payload"
    if not any(key in payload for key in ("model_patch", "patch", "unified_diff")):
        return "missing_patch_field"
    raw_patch = None
    for key in ("model_patch", "patch", "unified_diff"):
        if key in payload:
            raw_patch = payload.get(key)
            break
    if raw_patch is None:
        return "patch_field_null"
    if not isinstance(raw_patch, str):
        return "patch_field_not_string"
    if not _strip_code_fences(raw_patch).strip():
        summary = str(payload.get("summary") or payload.get("notes") or "").strip()
        if summary:
            return "empty_patch:" + _preview(summary, 160)
        return "empty_patch"
    return "non_empty_patch"


def _payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    patch = _extract_patch(payload)
    return {
        "keys": sorted(payload.keys()),
        "mode": payload.get("mode"),
        "confidence": payload.get("confidence"),
        "candidate_files": _preview_list(payload.get("candidate_files")),
        "summary_preview": _preview(str(payload.get("summary") or ""), 320),
        "notes_preview": _preview(str(payload.get("notes") or ""), 320),
        "model_patch_chars": len(patch),
        "model_patch_nonempty": bool(patch),
        "model_patch_modified_files": _modified_files_from_patch(patch),
    }


def _modified_files_from_patch(patch: str) -> list[str]:
    files: list[str] = []
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.append(parts[3][2:] if parts[3].startswith("b/") else parts[3])
        elif line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            path = line[4:].strip()
            files.append(path[2:] if path.startswith("b/") else path)
    return _dedupe(files)[:20]


def _preview(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _preview_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_preview(str(item), 160) for item in value[:20]]


def _is_likely_implementation_file(path: str) -> bool:
    lowered = path.lower()
    if not lowered:
        return False
    blocked_parts = {".github", "docs", "doc", "examples", "example", "tests", "test", "testing"}
    parts = set(re.split(r"[/\\]+", lowered))
    if parts & blocked_parts:
        return False
    blocked_suffixes = (".md", ".rst", ".txt")
    if lowered.endswith(blocked_suffixes):
        return False
    return Path(lowered).suffix in {
        ".py",
        ".pyi",
        ".pyx",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".js",
        ".ts",
        ".java",
        ".rs",
        ".toml",
        ".cfg",
        ".ini",
        ".yaml",
        ".yml",
        ".json",
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:diff|patch)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1) if match else stripped


def _parse_json_object(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match is None:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("worker response must be a JSON object")
    return payload


def _usage(meta: dict[str, Any]) -> dict[str, int]:
    usage = meta.get("usage") if isinstance(meta, dict) else None
    if not isinstance(usage, dict):
        return {"input_tokens": 0, "output_tokens": 0}
    return {
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
    }


def _api_cost(meta: dict[str, Any]) -> float:
    try:
        return float(meta.get("cost_usd") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _required(value: Any, flag: str) -> Any:
    if value is None or value == "":
        raise ValueError(f"{flag} is required, either as a CLI argument or executor config field")
    return value


def _int_from_any(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_positive_int_from_any(value: Any, *, default: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "none", "null", "unbounded"}:
        return None
    parsed = _int_from_any(value, default if default is not None else 0)
    if parsed <= 0:
        return 0
    return parsed


if __name__ == "__main__":
    main()
