"""Execute frozen SWE-bench orchestration specs with open-source workers."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from vao.agents.openai_compatible_adapter import OpenAICompatibleAdapter
from vao.swebench_orchestration.schemas import (
    ComponentSpec,
    OrchestrationDesign,
    OrchestrationSpec,
    SWEInstancePublic,
    TraceStep,
)


ALLOWED_RUNTIME_ADAPTERS = {"openai_compatible"}
REJECTED_RUNTIME_ADAPTERS = {
    "anthropic",
    "claude",
    "claude_code",
    "claude_haiku",
    "codex_cli",
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
    "required": ["model_patch"],
    "additionalProperties": True,
}
OBSERVATION_SCHEMA = {
    "type": "object",
    "properties": {
        "mode": {"type": "string"},
        "candidate_files": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["notes"],
    "additionalProperties": True,
}
LIMITATIONS = [
    "This MVP does not materialize repository checkouts.",
    "This MVP does not run target tests or the official SWE-bench verifier.",
    "Predictions are patch-generation-only and are emitted as unverified candidates.",
]


@dataclass(frozen=True)
class WorkerConfig:
    alias: str
    adapter: str
    model_id: str
    base_url: str
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


@dataclass
class InstanceResult:
    instance_id: str
    prediction: dict[str, str]
    traces: list[TraceStep]


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
                    },
                )
            )
            step += 1

            if error is not None:
                continue
            observations.append({"component_id": component.component_id, "role": component.role, "payload": payload})
            if component.role == "patcher" and not selected_patch:
                selected_patch = _extract_patch(payload)
                if selected_patch:
                    selected_model = worker.model_id
                    break
        if selected_patch:
            break

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
            error="not_implemented:repo_checkout_tests_and_swebench_verifier_are_not_run_by_this_mvp",
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
                args.workers_config or executor.get("workers_config") or "configs/swebench_open_source_workers.yaml",
                "--workers-config",
            )
        ),
        output_dir=Path(args.output_dir or executor.get("output_dir") or "experiments/swebench_orchestration/pilot"),
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
        raise ValueError(
            f"Runtime worker {alias!r} uses disallowed adapter {adapter!r}; "
            "SWE-bench orchestration execution only permits openai_compatible open-source workers."
        )
    if config.get("open_source") is not True:
        raise ValueError(f"Runtime worker {alias!r} must declare open_source: true")
    model_id = str(config.get("model_id") or "")
    if not model_id:
        raise ValueError(f"Runtime worker {alias!r} is missing model_id")
    if _looks_proprietary(alias) or _looks_proprietary(model_id):
        raise ValueError(f"Runtime worker {alias!r} has a proprietary-looking model_id {model_id!r}")
    base_url = str(config.get("base_url") or config.get("endpoint") or "")
    if not base_url:
        raise ValueError(f"Runtime worker {alias!r} is missing base_url")
    return WorkerConfig(alias=alias, adapter=adapter_key, model_id=model_id, base_url=base_url, raw=dict(config))


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
) -> tuple[dict[str, Any], dict[str, Any]]:
    adapter = _build_adapter(worker)
    prompt = _render_component_prompt(
        component=component,
        instance=instance,
        orchestration=orchestration,
        observations=observations,
        call_index=call_index,
    )
    schema = PATCH_SCHEMA if component.role == "patcher" else OBSERVATION_SCHEMA
    max_tokens = int(worker.raw.get("max_tokens_patch" if component.role == "patcher" else "max_tokens_observe", 4096))
    raw, usage = adapter._complete(prompt, schema, max_tokens=max_tokens)
    return _parse_json_object(raw), usage


def _build_adapter(worker: WorkerConfig) -> OpenAICompatibleAdapter:
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
) -> str:
    if component.role == "patcher":
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
            "You are an open-source model worker in a frozen SWE-bench orchestration.",
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
            "Current runtime limitations: repository checkout, test execution, and verifier calls are not implemented in this MVP.",
            "Public SWE-bench instance:",
            json.dumps(instance.model_dump(mode="json"), indent=2, sort_keys=True),
            "Prior component outputs:",
            json.dumps(observations, indent=2, sort_keys=True),
            output_instruction,
        ]
    )


def _dry_run_payload(component: ComponentSpec, instance: SWEInstancePublic) -> tuple[dict[str, Any], dict[str, Any]]:
    if component.role == "patcher":
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
