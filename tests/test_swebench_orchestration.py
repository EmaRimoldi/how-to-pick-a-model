from __future__ import annotations

import json
from pathlib import Path

import pytest

from vao.swebench_orchestration.analyze import analyze
from vao.swebench_orchestration.evaluate import build_command
from vao.swebench_orchestration.executor import ExecutorConfig, load_worker_configs, main as executor_main, run_executor
from vao.swebench_orchestration.prompt import render_prompt
from vao.swebench_orchestration.schemas import OrchestrationDesign, TraceStep


FIXTURES = Path(__file__).parent / "fixtures"


def test_orchestration_design_schema_fixture() -> None:
    payload = json.loads((FIXTURES / "swebench_orchestration_design.json").read_text(encoding="utf-8"))
    design = OrchestrationDesign.model_validate(payload)
    assert {item.orchestration_type for item in design.orchestrations} == {
        "universal",
        "mode_specialist",
        "hierarchical_routed",
    }
    assert design.orchestrations[0].complexity.score() > 0


def test_swebench_orchestration_analysis(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    report = analyze(
        trace_path=FIXTURES / "swebench_orchestration_traces.jsonl",
        orchestration_design_path=FIXTURES / "swebench_orchestration_design.json",
        output_path=output,
        delta=0.10,
        alpha_fail=100.0,
        weights={
            "token": 1.0 / 100_000.0,
            "wall": 1.0 / 3600.0,
            "test": 1.0 / 3600.0,
            "api": 1.0,
            "verifier_call": 0.05,
        },
    )
    assert output.exists()
    assert "test_localizable" in report["mode_frontier"]
    assert any(row["orchestration_id"] == "O_route" for row in report["imbalance"])
    failed = [row for row in report["run_summaries"] if row["run_id"] == "u_b"][0]
    assert failed["success"] is False
    assert failed["wasted_effort_ratio"] > 0


def test_meta_prompt_rendering(tmp_path: Path) -> None:
    instances = tmp_path / "instances_public.jsonl"
    instances.write_text(
        json.dumps(
            {
                "instance_id": "demo",
                "repo": "demo/repo",
                "problem_statement": "A failing test reports an AttributeError.",
                "declared_mode": "semantic_api",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    prompt = render_prompt(
        config={
            "experiment": {
                "evidence_level": "E1",
                "dataset_name": "princeton-nlp/SWE-Bench_Verified",
                "split": "test",
            },
            "worker_models": [{"alias": "qwen_coder_7b", "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct"}],
            "allowed_tools": ["rg", "pytest"],
        },
        instances_path=instances,
        max_instances=None,
    )
    assert "Required orchestration families" in prompt
    assert "demo/repo" in prompt
    assert "gold patches" in prompt


def test_evaluation_command_builder() -> None:
    cmd = build_command(
        dataset_name="princeton-nlp/SWE-Bench_Verified",
        split="test",
        predictions_path=Path("predictions.jsonl"),
        run_id="run",
        max_workers=2,
        timeout=60,
    )
    assert "swebench.harness.run_evaluation" in cmd
    assert "--predictions_path" in cmd


def test_executor_rejects_codex_runtime_worker(tmp_path: Path) -> None:
    workers = tmp_path / "workers.yaml"
    workers.write_text(
        """
workers:
  bad_codex:
    adapter: codex_cli
    open_source: true
    model_id: gpt-5.5
    base_url: http://localhost:9999/v1
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="disallowed adapter"):
        load_worker_configs(workers)


def test_executor_rejects_unmarked_open_source_worker(tmp_path: Path) -> None:
    workers = tmp_path / "workers.yaml"
    workers.write_text(
        """
workers:
  qwen_coder_7b:
    adapter: openai_compatible
    model_id: Qwen/Qwen2.5-Coder-7B-Instruct
    base_url: http://localhost:8000/v1
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="open_source: true"):
        load_worker_configs(workers)


def test_executor_dry_run_outputs_trace_and_prediction(tmp_path: Path) -> None:
    instances = tmp_path / "instances_public.jsonl"
    instances.write_text(
        json.dumps(
            {
                "instance_id": "demo",
                "repo": "demo/repo",
                "problem_statement": "A failing test reports an AttributeError.",
                "declared_mode": "semantic_api",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    workers = _write_open_source_workers(tmp_path)
    output_dir = tmp_path / "pilot"
    manifest = run_executor(
        ExecutorConfig(
            design_path=FIXTURES / "swebench_orchestration_design.json",
            instances_path=instances,
            workers_config_path=workers,
            output_dir=output_dir,
            orchestration_id="O_route",
            run_id="dry",
            split="test",
            max_instances=1,
            parallel_workers=2,
            max_calls_per_component=1,
            dry_run=True,
        )
    )
    assert manifest["dry_run"] is True
    predictions = [
        json.loads(line)
        for line in (output_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    traces = [
        TraceStep.model_validate(json.loads(line))
        for line in (output_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert predictions == [{"instance_id": "demo", "model_name_or_path": "O_route", "model_patch": ""}]
    assert [trace.phase for trace in traces] == ["observe", "localize", "patch", "verify"]
    assert traces[-1].error and "not_implemented" in traces[-1].error


def test_executor_cli_dry_run_config(tmp_path: Path) -> None:
    instances = tmp_path / "instances_public.jsonl"
    instances.write_text(
        json.dumps(
            {
                "instance_id": "demo",
                "repo": "demo/repo",
                "problem_statement": "A failing test reports an AttributeError.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    workers = _write_open_source_workers(tmp_path)
    output_dir = tmp_path / "cli"
    config = tmp_path / "pilot.yaml"
    config.write_text(
        f"""
experiment:
  name: cli_dry
  split: test
  public_instances: {instances}
executor:
  design: {FIXTURES / "swebench_orchestration_design.json"}
  workers_config: {workers}
  orchestration_id: O_all
  output_dir: {output_dir}
  max_instances: 1
  parallel_workers: 1
  max_calls_per_component: 1
""",
        encoding="utf-8",
    )
    executor_main(["--config", str(config), "--dry-run"])
    assert (output_dir / "traces.jsonl").exists()
    assert (output_dir / "predictions.jsonl").exists()


def _write_open_source_workers(tmp_path: Path) -> Path:
    workers = tmp_path / "workers.yaml"
    workers.write_text(
        """
workers:
  qwen_coder_7b:
    adapter: openai_compatible
    open_source: true
    model_id: Qwen/Qwen2.5-Coder-7B-Instruct
    base_url: http://localhost:8000/v1
  qwen_coder_14b:
    adapter: openai_compatible
    open_source: true
    model_id: Qwen/Qwen2.5-Coder-14B-Instruct
    base_url: http://localhost:8001/v1
""",
        encoding="utf-8",
    )
    return workers
