from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vao.prompts import render_template


def test_only_single_program_prompt_file_is_active() -> None:
    prompt_files = {
        path.name
        for path in Path("src/vao/prompts").glob("*.txt")
    }
    assert prompt_files == {"single_step_program.txt"}


def test_single_program_prompt_contains_full_protocol() -> None:
    source = "class CandidateQueryEngine:\n    pass\n"
    common = {
        "profile_summary": "{}",
        "visible_history": "[]",
        "current_solution_source": source,
    }

    rendered = render_template("single_step_program.txt", **common)
    assert "VAO_SINGLE_STEP_PROGRAM_V1" in rendered
    assert "CANONICAL_TASK_BLOCK_V1" in rendered
    assert "exactly one candidate edit for each primary mode" in rendered
    assert "This is the only model-generation prompt for this step" in rendered
    assert "The modes are experimental labels, not edit permissions" in rendered


@pytest.mark.parametrize(
    "legacy_name",
    [
        "mode_distribution.txt",
        "mode_edit.txt",
        "mode_edit_replacement.txt",
        "mode_edit_structured.txt",
        "repair_code.txt",
        "repair_code_replacement.txt",
        "repair_code_structured.txt",
        "repair_json.txt",
        "shared_canonical_task.txt",
        "step_batch_structured.txt",
    ],
)
def test_legacy_prompt_templates_are_not_renderable(legacy_name: str) -> None:
    with pytest.raises(ValueError, match="unsupported prompt template"):
        render_template(
            legacy_name,
            mode="micro",
            profile_summary="{}",
            visible_history="[]",
            current_solution_source="class CandidateQueryEngine:\n    pass\n",
        )


def test_single_prompt_batch_prompt_is_explicit() -> None:
    rendered = render_template(
        "single_step_program.txt",
        profile_summary="{}",
        visible_history="[]",
        current_solution_source="class CandidateQueryEngine:\n    pass\n",
    )

    assert "This is the only model-generation prompt for this step" in rendered
    assert "Do not wait for or\n  expect separate per-mode prompts" in rendered
    assert "exactly one candidate edit for each primary mode in a single\n  JSON response" in rendered
    assert '"candidates": {' in rendered
    assert "Do not output candidates as a list" in rendered
    assert '\"layout\": {\"primary_mode\": \"layout\"' in rendered
    assert 'do not use "CandidateQueryEngine.put"' in rendered
    assert "The modes are experimental labels, not edit permissions" in rendered
    assert "not a whitelist of functions or lines" in rendered


def test_prompt_controlled_configs_are_single_prompt_batched() -> None:
    haiku_config = yaml.safe_load(Path("configs/hard_haiku_prompt_controlled_10step.yaml").read_text(encoding="utf-8"))
    qwen_config = yaml.safe_load(Path("configs/hard_qwen_prompt_controlled_10step.yaml").read_text(encoding="utf-8"))
    models_config = yaml.safe_load(Path("configs/models.yaml").read_text(encoding="utf-8"))["models"]

    assert haiku_config["experiment"]["candidate_generation"] == "batched"
    assert qwen_config["experiment"]["candidate_generation"] == "batched"
    assert haiku_config["models"]["include"] == ["claude_haiku_batch_strict"]
    assert qwen_config["models"]["include"] == ["weak_qwen_batch_strict"]
    assert models_config["claude_haiku_batch_strict"]["allow_batch_repair"] is False
    assert models_config["weak_qwen_batch_strict"]["allow_batch_repair"] is False
    assert models_config["weak_qwen_batch_strict"]["allow_response_format_retry"] is False
    assert "weak_qwen_direct" not in models_config
    assert "weak_qwen" not in models_config
    assert "claude_haiku_diff_legacy" not in models_config
    assert "claude_opus_teacher_replacement_legacy" not in models_config


def test_model_matrix_config_contains_requested_backends() -> None:
    matrix = yaml.safe_load(Path("configs/hard_single_prompt_model_matrix.yaml").read_text(encoding="utf-8"))
    models_config = yaml.safe_load(Path("configs/models.yaml").read_text(encoding="utf-8"))["models"]
    requested = {
        "gpt_5_4_batch_strict",
        "gpt_5_4_mini_batch_strict",
        "gpt_5_3_codex_batch_strict",
        "gpt_5_3_codex_spark_batch_strict",
        "gpt_5_2_codex_batch_strict",
        "qwen_coder_batch_strict",
        "claude_haiku_batch_strict",
        "claude_sonnet_batch_strict",
        "claude_opus_4_6_batch_strict",
    }

    assert matrix["experiment"]["candidate_generation"] == "batched"
    assert set(matrix["models"]["include"]) == requested
    assert all(name in models_config for name in requested)
    for name in requested:
        assert models_config[name]["edit_protocol"] == "structured_edits"
        assert models_config[name]["allow_batch_repair"] is False
    for name in {
        "gpt_5_4_batch_strict",
        "gpt_5_4_mini_batch_strict",
        "gpt_5_3_codex_batch_strict",
        "gpt_5_3_codex_spark_batch_strict",
        "gpt_5_2_codex_batch_strict",
    }:
        assert models_config[name]["adapter"] == "codex_cli"
