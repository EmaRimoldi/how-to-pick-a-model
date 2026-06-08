"""Render or invoke the SWE-bench orchestration meta-designer prompt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from vao.agents.codex_cli_adapter import CodexCliAdapter
from vao.swebench_orchestration.schemas import OrchestrationDesign

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "swebench_orchestration_meta_designer.txt"


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
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(
        evidence_level=experiment.get("evidence_level", "E1"),
        dataset_name=experiment.get("dataset_name", "princeton-nlp/SWE-Bench_Verified"),
        split=experiment.get("split", "test"),
        model_suite_policy=json.dumps(model_suite_policy, indent=2, sort_keys=True),
        allowed_models=json.dumps(workers, indent=2, sort_keys=True),
        role_assignment_policy=json.dumps(role_assignment_policy, indent=2, sort_keys=True),
        allowed_tools=json.dumps(tools, indent=2, sort_keys=True),
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
) -> tuple[dict[str, Any], dict[str, Any]]:
    adapter = CodexCliAdapter(
        model_id=model_id,
        reasoning_effort=reasoning_effort,
        timeout_seconds=timeout_seconds,
        use_output_schema=False,
        sandbox=sandbox,
    )
    raw, usage = adapter._complete(
        prompt,
        OrchestrationDesign.model_json_schema(),
        max_tokens=16000,
    )
    payload = json.loads(raw)
    return payload, usage


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
    args = parser.parse_args(argv)

    config = _load_config(Path(args.config))
    experiment = config.get("experiment", {})
    meta = config.get("meta_designer", {})
    instances_path = Path(args.instances or experiment.get("public_instances", "swebench/studies/open_source_orchestration/data/dev_slice/instances_public.jsonl"))
    output_dir = Path(args.output_dir or Path(experiment.get("output_dir", "swebench/studies/open_source_orchestration/runs/swebench_orchestration_meta_design")) / "meta_design")
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = render_prompt(config=config, instances_path=instances_path, max_instances=args.max_instances)
    prompt_path = output_dir / "meta_designer_prompt.md"
    schema_path = output_dir / "orchestration_design_schema.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path.write_text(
        json.dumps(OrchestrationDesign.model_json_schema(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    result = {
        "prompt_path": str(prompt_path),
        "schema_path": str(schema_path),
        "invoke_codex": args.invoke_codex,
    }
    if args.invoke_codex:
        raw_payload, usage = _invoke_codex(
            prompt,
            model_id=args.model_id or meta.get("model_id", "gpt-5.5"),
            reasoning_effort=args.reasoning_effort or meta.get("reasoning_effort", "xhigh"),
            timeout_seconds=args.timeout_seconds or int(meta.get("timeout_seconds", 1800)),
            sandbox=str(meta.get("sandbox", "read-only")),
        )
        raw_path = output_dir / "orchestration_design_raw.json"
        raw_path.write_text(json.dumps(raw_payload, indent=2, sort_keys=True), encoding="utf-8")
        design = OrchestrationDesign.model_validate(raw_payload).model_dump()
        design_path = output_dir / "orchestration_design.json"
        usage_path = output_dir / "meta_designer_usage.json"
        design_path.write_text(json.dumps(design, indent=2, sort_keys=True), encoding="utf-8")
        usage_path.write_text(json.dumps(usage, indent=2, sort_keys=True), encoding="utf-8")
        result["design_path"] = str(design_path)
        result["usage_path"] = str(usage_path)
        result["raw_path"] = str(raw_path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
