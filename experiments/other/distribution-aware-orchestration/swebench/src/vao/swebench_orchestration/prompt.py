"""Render or invoke the SWE-bench orchestration meta-designer prompt."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from vao.agents.codex_cli_adapter import CodexCliAdapter
from vao.swebench_orchestration.schemas import MetaDesignPackage, OrchestrationDesign

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "swebench_orchestration_meta_designer.txt"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"


def _read_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def prepare_meta_design_config(
    config: dict[str, Any],
    *,
    output_dir: Path | None = None,
    allow_web_model_discovery: bool = False,
    model_discovery_manifest: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve the worker menu before rendering the meta-orchestrator prompt."""

    prepared = json.loads(json.dumps(config))
    artifacts: dict[str, Any] = {"worker_menu_source": "inline_worker_models"}
    if prepared.get("worker_models"):
        return prepared, artifacts

    policy = prepared.get("model_suite_policy") or {}
    default_config = policy.get("default_workers_config")
    if default_config:
        workers_path = Path(str(default_config))
        prepared["worker_models"] = _worker_models_from_worker_yaml(workers_path)
        artifacts.update(
            {
                "worker_menu_source": "practitioner_declared_config",
                "workers_config_path": str(workers_path),
            }
        )
        return prepared, artifacts

    if not policy.get("discovery_allowed"):
        raise ValueError("worker_models is empty and model_suite_policy.discovery_allowed is false")

    discovered = _discover_worker_models(
        policy=policy,
        allow_web_model_discovery=allow_web_model_discovery,
        model_discovery_manifest=model_discovery_manifest,
    )
    prepared["worker_models"] = discovered["worker_models"]
    artifacts.update(
        {
            "worker_menu_source": discovered["source"],
            "model_ids": discovered["model_ids"],
        }
    )
    generated_workers_config = policy.get("generated_workers_config")
    if generated_workers_config:
        generated_path = Path(str(generated_workers_config))
        _write_workers_config(generated_path, discovered["worker_models"])
        artifacts["generated_workers_config"] = str(generated_path)
    if output_dir is not None:
        snapshot_path = output_dir / "model_discovery_snapshot.json"
        snapshot_path.write_text(json.dumps(discovered, indent=2, sort_keys=True), encoding="utf-8")
        artifacts["model_discovery_snapshot"] = str(snapshot_path)
    return prepared, artifacts


def _worker_models_from_worker_yaml(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_workers = payload.get("workers") or payload.get("models")
    if not isinstance(raw_workers, dict):
        raise ValueError(f"{path} must contain a workers or models mapping")
    rows = []
    for alias, config in raw_workers.items():
        if not isinstance(config, dict):
            raise ValueError(f"Worker {alias!r} in {path} must be a mapping")
        row = {"alias": str(alias), **config}
        rows.append(row)
    return rows


def _discover_worker_models(
    *,
    policy: dict[str, Any],
    allow_web_model_discovery: bool,
    model_discovery_manifest: Path | None,
) -> dict[str, Any]:
    model_ids = _load_model_ids_from_manifest(model_discovery_manifest) if model_discovery_manifest else None
    source = f"manifest:{model_discovery_manifest}" if model_discovery_manifest else None
    if model_ids is None:
        if not allow_web_model_discovery:
            raise ValueError("model discovery requires --allow-web-model-discovery or --model-discovery-manifest")
        model_ids = _fetch_official_model_ids(policy)
        source = str(policy.get("official_model_endpoint") or OPENAI_MODELS_URL)
    selected = _select_model_ids(model_ids, policy)
    worker_models = _worker_models_from_model_ids(selected, policy)
    return {
        "source": source,
        "provider_family": policy.get("provider_family"),
        "model_ids": selected,
        "worker_models": worker_models,
    }


def _load_model_ids_from_manifest(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(item) for item in payload]
    if isinstance(payload.get("model_ids"), list):
        return [str(item) for item in payload["model_ids"]]
    if isinstance(payload.get("data"), list):
        return [str(item["id"]) for item in payload["data"] if isinstance(item, dict) and item.get("id")]
    raise ValueError(f"{path} must contain model_ids or OpenAI-style data[].id")


def _fetch_official_model_ids(policy: dict[str, Any]) -> list[str]:
    endpoint = str(policy.get("official_model_endpoint") or OPENAI_MODELS_URL)
    if endpoint != OPENAI_MODELS_URL:
        raise ValueError("Only the official OpenAI model-listing endpoint is supported for live discovery")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for live official model discovery")
    request = urllib.request.Request(endpoint, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [str(item["id"]) for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")]


def _select_model_ids(model_ids: list[str], policy: dict[str, Any]) -> list[str]:
    selection = policy.get("discovery_selection") or {}
    include_patterns = [re.compile(str(item)) for item in selection.get("include_patterns", [".*"])]
    exclude_patterns = [re.compile(str(item)) for item in selection.get("exclude_patterns", [])]
    max_workers = int(selection.get("max_workers", policy.get("max_workers", 8)))
    selected = []
    for model_id in sorted(set(model_ids)):
        if not any(pattern.search(model_id) for pattern in include_patterns):
            continue
        if any(pattern.search(model_id) for pattern in exclude_patterns):
            continue
        selected.append(model_id)
    if not selected:
        raise ValueError("model discovery did not select any models")
    return selected[:max_workers]


def _worker_models_from_model_ids(model_ids: list[str], policy: dict[str, Any]) -> list[dict[str, Any]]:
    worker_schema = policy.get("worker_schema") or {}
    adapter = str(worker_schema.get("adapter") or policy.get("adapter") or "codex_cli")
    sandbox = str(worker_schema.get("sandbox") or policy.get("sandbox") or "workspace-write")
    timeout_seconds = int(worker_schema.get("timeout_seconds") or policy.get("timeout_seconds") or 1200)
    reasoning_effort = str(worker_schema.get("reasoning_effort") or policy.get("reasoning_effort") or "high")
    rows = []
    for index, model_id in enumerate(model_ids):
        rows.append(
            {
                "alias": _neutral_alias(index),
                "adapter": adapter,
                "model_id": model_id,
                "reasoning_effort": reasoning_effort,
                "sandbox": sandbox,
                "timeout_seconds": timeout_seconds,
                "capability_profile": "officially discovered model; assign roles only inside OrchestrationSpec.components",
            }
        )
    return rows


def _neutral_alias(index: int) -> str:
    letters = "abcdefghijklmnopqrstuvwxyz"
    if index < len(letters):
        return f"worker_{letters[index]}"
    return f"worker_{index + 1}"


def _write_workers_config(path: Path, worker_models: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workers = {}
    for row in worker_models:
        config = dict(row)
        alias = str(config.pop("alias"))
        workers[alias] = config
    path.write_text(yaml.safe_dump({"workers": workers}, sort_keys=False), encoding="utf-8")


def render_prompt(
    *,
    config: dict[str, Any],
    instances_path: Path,
    max_instances: int | None,
) -> str:
    instances = _read_jsonl(instances_path, limit=max_instances)
    experiment = config.get("experiment", {})
    meta = config.get("meta_designer", {})
    model_suite_policy = config.get("model_suite_policy", {})
    workers = config.get("worker_models", [])
    role_assignment_policy = config.get("role_assignment_policy", {})
    tools = config.get("allowed_tools", [])
    loss_weights = config.get("loss_weights", {})
    complexity_weights = config.get("complexity_weights", {})
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(
        evidence_level=experiment.get("evidence_level", "E1"),
        dataset_name=experiment.get("dataset_name", "princeton-nlp/SWE-Bench_Verified"),
        split=experiment.get("split", "test"),
        model_suite_policy=json.dumps(model_suite_policy, indent=2, sort_keys=True),
        allowed_models=json.dumps(workers, indent=2, sort_keys=True),
        role_assignment_policy=json.dumps(role_assignment_policy, indent=2, sort_keys=True),
        allowed_tools=json.dumps(tools, indent=2, sort_keys=True),
        loss_weights=json.dumps(loss_weights, indent=2, sort_keys=True),
        complexity_weights=json.dumps(complexity_weights, indent=2, sort_keys=True),
        instances_json=json.dumps(instances, indent=2, sort_keys=True),
        meta_model=meta.get("model_id", "gpt-5.5"),
    )


def _invoke_codex(
    prompt: str,
    *,
    model_id: str,
    reasoning_effort: str,
    timeout_seconds: int,
    sandbox: str,
) -> tuple[MetaDesignPackage, dict[str, Any], dict[str, Any]]:
    adapter = CodexCliAdapter(
        model_id=model_id,
        reasoning_effort=reasoning_effort,
        timeout_seconds=timeout_seconds,
        use_output_schema=False,
        sandbox=sandbox,
    )
    raw, usage = adapter._complete(
        prompt,
        MetaDesignPackage.model_json_schema(),
        max_tokens=24000,
    )
    payload = json.loads(raw)
    package = MetaDesignPackage.model_validate(payload)
    return package, payload, usage


def materialize_meta_design_package(
    *,
    package: MetaDesignPackage,
    raw_payload: dict[str, Any],
    usage: dict[str, Any],
    output_dir: Path,
) -> dict[str, str]:
    """Write provenance artifacts and the clean executor-facing design JSON."""

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "meta_design_package_raw.json"
    package_path = output_dir / "meta_design_package.json"
    distribution_path = output_dir / "distribution_analysis.json"
    candidates_path = output_dir / "candidate_orchestrations.jsonl"
    loss_estimates_path = output_dir / "candidate_loss_estimates.json"
    rationale_path = output_dir / "selected_orchestration_rationale.md"
    design_path = output_dir / "orchestration_design.json"
    usage_path = output_dir / "meta_designer_usage.json"

    raw_path.write_text(json.dumps(raw_payload, indent=2, sort_keys=True), encoding="utf-8")
    package_path.write_text(json.dumps(package.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    distribution_path.write_text(
        json.dumps(package.distribution_analysis.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    with candidates_path.open("w", encoding="utf-8") as handle:
        for candidate in package.candidate_orchestrations:
            handle.write(json.dumps(candidate.model_dump(mode="json"), sort_keys=True) + "\n")
    loss_estimates_path.write_text(
        json.dumps([item.model_dump(mode="json") for item in package.candidate_loss_estimates], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    rationale_path.write_text(package.selected_orchestration_rationale.strip() + "\n", encoding="utf-8")
    design_path.write_text(
        json.dumps(package.orchestration_design.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    usage_path.write_text(json.dumps(usage, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "raw_path": str(raw_path),
        "package_path": str(package_path),
        "distribution_analysis_path": str(distribution_path),
        "candidate_orchestrations_path": str(candidates_path),
        "candidate_loss_estimates_path": str(loss_estimates_path),
        "selected_orchestration_rationale_path": str(rationale_path),
        "design_path": str(design_path),
        "usage_path": str(usage_path),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="swebench/studies/open_source_orchestration/configs/swebench_orchestration_meta_design.yaml")
    parser.add_argument("--instances", default=None, help="Defaults to experiment.public_instances from config")
    parser.add_argument("--output-dir", default=None, help="Defaults to experiment.output_dir/meta_design")
    parser.add_argument("--max-instances", type=int, default=None)
    parser.add_argument("--invoke-codex", action="store_true")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=None)
    parser.add_argument("--allow-web-model-discovery", action="store_true")
    parser.add_argument("--model-discovery-manifest", default=None)
    args = parser.parse_args(argv)

    config = _load_config(Path(args.config))
    experiment = config.get("experiment", {})
    meta = config.get("meta_designer", {})
    instances_path = Path(args.instances or experiment.get("public_instances", "swebench/studies/open_source_orchestration/data/dev_slice/instances_public.jsonl"))
    output_dir = Path(args.output_dir or Path(experiment.get("output_dir", "swebench/studies/open_source_orchestration/runs/swebench_orchestration_meta_design")) / "meta_design")
    output_dir.mkdir(parents=True, exist_ok=True)

    config, worker_menu_artifacts = prepare_meta_design_config(
        config,
        output_dir=output_dir,
        allow_web_model_discovery=args.allow_web_model_discovery,
        model_discovery_manifest=Path(args.model_discovery_manifest) if args.model_discovery_manifest else None,
    )
    prompt = render_prompt(config=config, instances_path=instances_path, max_instances=args.max_instances)
    prompt_path = output_dir / "meta_designer_prompt.md"
    package_schema_path = output_dir / "meta_design_package_schema.json"
    design_schema_path = output_dir / "orchestration_design_schema.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    package_schema_path.write_text(
        json.dumps(MetaDesignPackage.model_json_schema(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    design_schema_path.write_text(
        json.dumps(OrchestrationDesign.model_json_schema(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    result = {
        "prompt_path": str(prompt_path),
        "schema_path": str(package_schema_path),
        "package_schema_path": str(package_schema_path),
        "orchestration_design_schema_path": str(design_schema_path),
        "invoke_codex": args.invoke_codex,
        "worker_menu": worker_menu_artifacts,
    }
    if args.invoke_codex:
        package, raw_payload, usage = _invoke_codex(
            prompt,
            model_id=args.model_id or meta.get("model_id", "gpt-5.5"),
            reasoning_effort=args.reasoning_effort or meta.get("reasoning_effort", "xhigh"),
            timeout_seconds=args.timeout_seconds or int(meta.get("timeout_seconds", 1800)),
            sandbox=str(meta.get("sandbox", "read-only")),
        )
        result.update(
            materialize_meta_design_package(
                package=package,
                raw_payload=raw_payload,
                usage=usage,
                output_dir=output_dir,
            )
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
