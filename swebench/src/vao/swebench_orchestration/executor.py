"""Execute frozen SWE-bench orchestration specs with open-source workers."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

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
    max_calls_per_component: int
    dry_run: bool
    materialize_checkouts: bool = False
    checkout_root: Path | None = None
    keep_checkouts: bool = False


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
        return design.orchestrations[0]
    for orchestration in design.orchestrations:
        if orchestration.orchestration_id == orchestration_id:
            return orchestration
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
        futures = [
            pool.submit(
                execute_instance,
                instance=instance,
                design=design,
                orchestration=orchestration,
                workers=workers,
                config=config,
            )
            for instance in instances
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
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
    workspace = _instance_workspace(instance, config)

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
            extra={"limitations": LIMITATIONS},
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
                extra={"checkout_dir": str(workspace.checkout_dir) if workspace.checkout_dir else None},
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
            calls = _bounded_calls(component.max_calls, config.max_calls_per_component)
            for call_index in range(calls):
                worker = workers[component.model]
                started = time.perf_counter()
                error: str | None = None
                payload: dict[str, Any] = {}
                usage_meta: dict[str, Any] = {}
                phase = _phase_for_component(component)
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
                            call_index=call_index,
                            checkout_dir=workspace.checkout_dir,
                        )
                except Exception as exc:  # pragma: no cover - exact backend errors vary.
                    error = f"{type(exc).__name__}:{exc}"
                wall_seconds = time.perf_counter() - started

                usage = _usage(usage_meta)
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
                        },
                    )
                )
                step += 1

                if error is not None:
                    continue
                observations.append({"component_id": component.component_id, "role": component.role, "payload": payload})
                if component.role in {"patcher", "fallback"} and not selected_patch:
                    selected_patch = _extract_patch(payload)
                    if not selected_patch and workspace.checkout_dir is not None:
                        selected_patch = _git_diff(workspace.checkout_dir)
                    if selected_patch:
                        selected_model = worker.model_id
                        break
            if selected_patch:
                break
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
            extra={"limitations": LIMITATIONS},
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
    parser.add_argument("--max-calls-per-component", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Validate flow without calling GPU endpoints.")
    parser.add_argument("--materialize-checkouts", action="store_true", help="Clone SWE-bench repos before worker calls.")
    parser.add_argument("--checkout-root", default=None, help="Directory for per-instance checkouts and repo cache.")
    parser.add_argument("--keep-checkouts", action="store_true", help="Keep cloned SWE-bench worktrees after each instance.")
    return parser


def config_from_args(args: argparse.Namespace) -> ExecutorConfig:
    file_config = _load_yaml(Path(args.config)) if args.config else {}
    executor = file_config.get("executor", {})
    experiment = file_config.get("experiment", {})
    run_id = args.run_id or executor.get("run_id") or experiment.get("name") or "swebench_orchestration_executor"
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
        output_dir=Path(args.output_dir or executor.get("output_dir") or "swebench/studies/open_source_orchestration/runs/pilot/executor"),
        orchestration_id=args.orchestration_id or executor.get("orchestration_id"),
        run_id=str(run_id),
        split=str(args.split or executor.get("split") or experiment.get("split") or "test"),
        max_instances=args.max_instances if args.max_instances is not None else executor.get("max_instances"),
        parallel_workers=int(
            args.parallel_workers if args.parallel_workers is not None else executor.get("parallel_workers", 1)
        ),
        max_calls_per_component=int(
            args.max_calls_per_component
            if args.max_calls_per_component is not None
            else executor.get("max_calls_per_component", 1)
        ),
        dry_run=bool(args.dry_run or executor.get("dry_run", False)),
        materialize_checkouts=bool(args.materialize_checkouts or executor.get("materialize_checkouts", False)),
        checkout_root=Path(args.checkout_root or executor["checkout_root"]) if args.checkout_root or executor.get("checkout_root") else None,
        keep_checkouts=bool(args.keep_checkouts or executor.get("keep_checkouts", False)),
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
    call_index: int,
    checkout_dir: Path | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    adapter = _build_adapter(worker, working_dir=checkout_dir)
    prompt = _render_component_prompt(
        component=component,
        instance=instance,
        orchestration=orchestration,
        observations=observations,
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
            json.dumps(instance.model_dump(mode="json"), indent=2, sort_keys=True),
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


def _bounded_calls(spec_calls: int, configured_max: int) -> int:
    if spec_calls <= 0 or configured_max <= 0:
        return 0
    return min(spec_calls, configured_max)


def _extract_patch(payload: dict[str, Any]) -> str:
    patch = payload.get("model_patch") or payload.get("patch") or payload.get("unified_diff") or ""
    if not isinstance(patch, str):
        return ""
    return _strip_code_fences(patch).strip()


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


if __name__ == "__main__":
    main()
