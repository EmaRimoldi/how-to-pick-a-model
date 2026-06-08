from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from vao.swebench_orchestration.analyze import analyze
from vao.swebench_orchestration.evaluate import (
    _collect_instance_results,
    _local_script_lines,
    _validate_predictions,
    build_command,
    run_evaluation,
)
from vao.swebench_orchestration.executor import ExecutorConfig, load_worker_configs, main as executor_main, run_executor
from vao.swebench_orchestration.prompt import prepare_meta_design_config, render_prompt
from vao.swebench_orchestration.repo_context import safe_instance_payload
from vao.swebench_orchestration.schemas import OrchestrationDesign, SWEInstancePublic, TraceStep


FIXTURES = Path(__file__).parent / "fixtures"


def test_orchestration_design_schema_fixture() -> None:
    payload = json.loads((FIXTURES / "swebench_orchestration_design.json").read_text(encoding="utf-8"))
    design = OrchestrationDesign.model_validate(payload)
    assert design.orchestration.orchestration_type == "hierarchical_routed"
    assert design.orchestration.complexity.score() > 0


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
            "model_suite_policy": {
                "mode": "practitioner_declared",
                "default_workers_config": "workers.yaml",
            },
            "worker_models": [{"alias": "qwen_coder_7b", "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct"}],
            "role_assignment_policy": {"roles_live_in_orchestration_spec": True},
            "allowed_tools": ["rg", "pytest"],
        },
        instances_path=instances,
        max_instances=None,
    )
    assert "Required orchestration output" in prompt
    assert "Return exactly one `orchestration` object" in prompt
    assert "Model suite and worker-menu policy" in prompt
    assert "practitioner_declared" in prompt
    assert "Role assignment policy" in prompt
    assert "roles_live_in_orchestration_spec" in prompt
    assert "Self-debug and self-optimization requirement" in prompt
    assert "--backend local" in prompt
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


def test_evaluation_command_builder_modal_subset() -> None:
    cmd = build_command(
        dataset_name="princeton-nlp/SWE-Bench_Verified",
        split="test",
        predictions_path=Path("/tmp/predictions.jsonl"),
        run_id="run",
        max_workers=1,
        timeout=1800,
        instance_ids=["sympy__sympy-16886"],
        modal=True,
        report_dir=Path("reports"),
    )

    assert cmd[cmd.index("--modal") + 1] == "true"
    assert cmd[cmd.index("--instance_ids") + 1] == "sympy__sympy-16886"
    assert cmd[cmd.index("--report_dir") + 1] == "reports"


def test_evaluation_validates_predictions(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "instance_id": "sympy__sympy-16886",
                        "model_name_or_path": "qwen",
                        "model_patch": "diff --git a/x b/x\n",
                    }
                ),
                json.dumps(
                    {
                        "instance_id": "sympy__sympy-16886",
                        "model_name_or_path": "qwen",
                        "model_patch": "",
                    }
                ),
                json.dumps({"instance_id": "django__django-10097"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    validation = _validate_predictions(predictions)

    assert validation["rows"] == 3
    assert validation["missing_required_fields"] == 1
    assert validation["duplicate_instance_ids"] == ["sympy__sympy-16886"]
    assert validation["empty_patch_ids"] == ["sympy__sympy-16886"]
    assert validation["nonempty_patch_count"] == 1


def test_evaluation_dry_run_writes_manifest(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text(
        json.dumps(
            {
                "instance_id": "sympy__sympy-16886",
                "model_name_or_path": "Qwen/Qwen2.5-Coder-14B-Instruct",
                "model_patch": "diff --git a/sympy/crypto/crypto.py b/sympy/crypto/crypto.py\n",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "eval"

    result = run_evaluation(
        dataset_name="princeton-nlp/SWE-Bench_Verified",
        split="test",
        predictions_path=predictions,
        run_id="unit_eval",
        max_workers=1,
        timeout=60,
        execute=False,
        output_dir=output_dir,
        modal=True,
    )

    manifest = json.loads((output_dir / "evaluation_manifest.json").read_text(encoding="utf-8"))
    assert result.returncode is None
    assert manifest["execute"] is False
    assert manifest["backend"] == "modal"
    assert manifest["modal"] is True
    assert manifest["prediction_validation"]["instance_ids"] == ["sympy__sympy-16886"]
    assert manifest["expected_report_path"].endswith("Qwen__Qwen2.5-Coder-14B-Instruct.unit_eval.json")


def test_evaluation_local_backend_dry_run_is_no_docker_no_modal(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text(
        json.dumps(
            {
                "instance_id": "sympy__sympy-16886",
                "model_name_or_path": "local",
                "model_patch": "diff --git a/sympy/crypto/crypto.py b/sympy/crypto/crypto.py\n",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "eval"

    result = run_evaluation(
        dataset_name="princeton-nlp/SWE-Bench_Verified",
        split="test",
        predictions_path=predictions,
        run_id="unit_eval",
        max_workers=1,
        timeout=60,
        execute=False,
        output_dir=output_dir,
        backend="local",
    )

    manifest = json.loads((output_dir / "evaluation_manifest.json").read_text(encoding="utf-8"))
    assert result.returncode is None
    assert manifest["backend"] == "local"
    assert manifest["docker_required"] is False
    assert manifest["modal_required"] is False
    assert manifest["command"] is None


def test_local_backend_rewrites_conda_testbed_script(tmp_path: Path) -> None:
    repo_dir = tmp_path / "testbed"
    lines = _local_script_lines(
        [
            "source /opt/miniconda3/bin/activate",
            "conda activate testbed",
            "cd /testbed",
            "python -m pip install -e .",
        ],
        repo_dir=repo_dir,
    )

    assert lines == [f"cd {repo_dir}", "python -m pip install -e ."]


def test_evaluation_collects_instance_error_summary(tmp_path: Path) -> None:
    log_dir = (
        tmp_path
        / "logs"
        / "run_evaluation"
        / "unit_eval"
        / "Qwen__Qwen2.5-Coder-14B-Instruct"
        / "sympy__sympy-16886"
    )
    log_dir.mkdir(parents=True)
    (log_dir / "report.json").write_text("", encoding="utf-8")
    (log_dir / "test_output.txt").write_text("", encoding="utf-8")
    (log_dir / "run_instance.log").write_text(
        "prefix\n"
        ">>>>> Patch Apply Failed:\n"
        "Hunk #1 FAILED at 1520.\n",
        encoding="utf-8",
    )

    results = _collect_instance_results(
        output_dir=tmp_path,
        validation={
            "first_model_name": "Qwen/Qwen2.5-Coder-14B-Instruct",
            "model_name_by_instance": {"sympy__sympy-16886": "Qwen/Qwen2.5-Coder-14B-Instruct"},
            "instance_ids": ["sympy__sympy-16886"],
        },
        run_id="unit_eval",
    )

    assert results[0]["patch_apply_failed"] is True
    assert "Hunk #1 FAILED" in results[0]["error_summary"]


def test_executor_accepts_codex_runtime_worker(tmp_path: Path) -> None:
    workers = tmp_path / "workers.yaml"
    workers.write_text(
        """
workers:
  codex_gpt55:
    adapter: codex_cli
    model_id: gpt-5.5
    reasoning_effort: xhigh
    sandbox: workspace-write
""",
        encoding="utf-8",
    )
    loaded = load_worker_configs(workers)
    assert loaded["codex_gpt55"].adapter == "codex_cli"
    assert loaded["codex_gpt55"].base_url is None


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


def test_codex_suite_single_orchestration_design() -> None:
    design_path = Path("swebench/studies/codex_suite_100_vs_gpt55/designs/codex_suite_single/orchestration_design.json")
    workers_path = Path("swebench/studies/codex_suite_100_vs_gpt55/configs/swebench_codex_suite_workers.yaml")
    design = OrchestrationDesign.model_validate(json.loads(design_path.read_text(encoding="utf-8")))
    workers = load_worker_configs(workers_path)

    orchestration = design.orchestration
    assert orchestration.orchestration_id == "codex_suite_single_self_optimizing_v1"
    assert orchestration.orchestration_type == "hierarchical_routed"
    assert {component.model for component in orchestration.components} <= set(workers)
    assert all(workers[component.model].adapter == "codex_cli" for component in orchestration.components)


def test_gpt55_baseline_design() -> None:
    design_path = Path("swebench/studies/codex_suite_100_vs_gpt55/designs/gpt55_baseline/orchestration_design.json")
    workers_path = Path("swebench/studies/codex_suite_100_vs_gpt55/configs/swebench_gpt55_baseline_worker.yaml")
    design = OrchestrationDesign.model_validate(json.loads(design_path.read_text(encoding="utf-8")))
    workers = load_worker_configs(workers_path)

    orchestration = design.orchestration
    assert orchestration.orchestration_id == "gpt55_single_worker_baseline_v1"
    assert {component.model for component in orchestration.components} == {"codex_gpt_5_5_baseline"}
    assert workers["codex_gpt_5_5_baseline"].model_id == "gpt-5.5"


def test_neutral_codex_suite_worker_menu_has_no_role_aliases() -> None:
    config_root = Path("swebench/studies/codex_suite_100_vs_gpt55/configs")
    meta_config = yaml.safe_load(
        (config_root / "swebench_orchestration_codex_suite_meta_design_neutral.yaml").read_text(encoding="utf-8")
    )
    runtime_config = yaml.safe_load((config_root / "swebench_codex_suite_workers_neutral.yaml").read_text(encoding="utf-8"))
    forbidden = {"planner", "reviewer", "router", "patcher", "localizer", "fallback"}

    meta_aliases = {item["alias"] for item in meta_config["worker_models"]}
    runtime_aliases = set(runtime_config["workers"])

    assert meta_aliases == runtime_aliases == {"worker_a", "worker_b", "worker_c", "worker_d", "worker_e", "worker_f"}
    assert not any(term in alias for alias in meta_aliases for term in forbidden)
    assert all("intended_use" not in item for item in meta_config["worker_models"])
    assert all("intended_use" not in item for item in runtime_config["workers"].values())
    assert meta_config["model_suite_policy"]["discovery_allowed"] is True
    assert meta_config["model_suite_policy"]["worker_schema"]["alias_policy"] == "neutral_sequential"
    assert meta_config["role_assignment_policy"]["roles_live_in_orchestration_spec"] is True


def test_meta_design_config_loads_practitioner_worker_menu() -> None:
    config = {
        "model_suite_policy": {
            "default_workers_config": "swebench/studies/codex_suite_100_vs_gpt55/configs/swebench_codex_suite_workers_neutral.yaml",
            "discovery_allowed": True,
        },
        "worker_models": [],
    }

    prepared, artifacts = prepare_meta_design_config(config)

    assert artifacts["worker_menu_source"] == "practitioner_declared_config"
    assert {row["alias"] for row in prepared["worker_models"]} == {
        "worker_a",
        "worker_b",
        "worker_c",
        "worker_d",
        "worker_e",
        "worker_f",
    }


def test_meta_design_config_generates_worker_menu_from_discovery_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "official_models.json"
    generated = tmp_path / "workers.generated.yaml"
    manifest.write_text(
        json.dumps(
            {
                "data": [
                    {"id": "gpt-test-large"},
                    {"id": "gpt-test-mini"},
                    {"id": "image-test"},
                ]
            }
        ),
        encoding="utf-8",
    )
    config = {
        "model_suite_policy": {
            "discovery_allowed": True,
            "generated_workers_config": str(generated),
            "discovery_selection": {
                "include_patterns": ["^gpt-test"],
                "exclude_patterns": ["mini$"],
                "max_workers": 3,
            },
            "worker_schema": {
                "alias_policy": "neutral_sequential",
                "adapter": "codex_cli",
                "reasoning_effort": "high",
                "sandbox": "workspace-write",
                "timeout_seconds": 900,
            },
        },
        "worker_models": [],
    }

    prepared, artifacts = prepare_meta_design_config(
        config,
        output_dir=tmp_path,
        model_discovery_manifest=manifest,
    )

    assert artifacts["worker_menu_source"].startswith("manifest:")
    assert artifacts["model_ids"] == ["gpt-test-large"]
    assert prepared["worker_models"] == [
        {
            "alias": "worker_a",
            "adapter": "codex_cli",
            "model_id": "gpt-test-large",
            "reasoning_effort": "high",
            "sandbox": "workspace-write",
            "timeout_seconds": 900,
            "capability_profile": "officially discovered model; assign roles only inside OrchestrationSpec.components",
        }
    ]
    assert generated.exists()
    assert (tmp_path / "model_discovery_snapshot.json").exists()


def test_codex_suite_dry_run_config_with_checkout_fields(tmp_path: Path) -> None:
    instances = tmp_path / "instances_public.jsonl"
    instances.write_text(
        json.dumps(
            {
                "instance_id": "demo",
                "repo": "demo/repo",
                "base_commit": "abc123",
                "problem_statement": "A failing test reports an AttributeError.",
                "declared_mode": "semantic_api",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "codex"
    manifest = run_executor(
        ExecutorConfig(
            design_path=Path("swebench/studies/codex_suite_100_vs_gpt55/designs/codex_suite_single/orchestration_design.json"),
            instances_path=instances,
            workers_config_path=Path("swebench/studies/codex_suite_100_vs_gpt55/configs/swebench_codex_suite_workers.yaml"),
            output_dir=output_dir,
            orchestration_id="codex_suite_single_self_optimizing_v1",
            run_id="codex_dry",
            split="test",
            max_instances=1,
            parallel_workers=1,
            max_calls_per_component=1,
            dry_run=True,
            materialize_checkouts=True,
            checkout_root=tmp_path / "checkouts",
        )
    )

    assert manifest["dry_run"] is True
    assert manifest["materialize_checkouts"] is True
    assert (output_dir / "traces.jsonl").exists()
    assert (output_dir / "predictions.jsonl").exists()


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
  orchestration_id: O_route
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


def test_executor_cli_accepts_meta_update_fields(tmp_path: Path) -> None:
    instances = tmp_path / "instances_public.jsonl"
    instances.write_text(
        json.dumps(
            {
                "instance_id": "demo",
                "repo": "demo/repo",
                "problem_statement": "A failing test reports `old` should be `new`.",
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
  orchestration_id: O_route
  output_dir: {output_dir}
  max_instances: 1
  parallel_workers: 1
  max_calls_per_component: null
  patch_repair_attempts: 2
  public_literal_repair_enabled: true
  patch_apply_timeout_seconds: 7
  repo_context:
    enabled: false
""",
        encoding="utf-8",
    )
    executor_main(["--config", str(config), "--dry-run"])

    manifest = json.loads((output_dir / "executor_manifest.json").read_text(encoding="utf-8"))
    assert manifest["max_calls_per_component"] is None
    assert manifest["patch_repair_attempts"] == 2
    assert manifest["public_literal_repair_enabled"] is True
    assert manifest["repo_context_enabled"] is False


def test_safe_instance_payload_drops_leaky_fields() -> None:
    payload = safe_instance_payload(
        SWEInstancePublic.model_validate(
            {
                "instance_id": "demo",
                "repo": "demo/repo",
                "problem_statement": "public issue",
                "gold_patch": "secret",
                "nested": {"test_patch": "secret", "keep": "visible"},
            }
        )
    )

    assert payload == {
        "base_commit": None,
        "created_at": None,
        "declared_mode": "unknown",
        "hints_text": None,
        "instance_id": "demo",
        "nested": {"keep": "visible"},
        "problem_statement": "public issue",
        "public_fields": {},
        "repo": "demo/repo",
        "version": None,
    }


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
