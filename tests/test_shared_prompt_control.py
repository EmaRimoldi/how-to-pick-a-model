from __future__ import annotations

from pathlib import Path

import yaml

from vao.agents.direct_file_edit import _render_direct_edit_prompt
from vao.prompts import render_template, shared_canonical_task


def test_real_backend_prompts_include_shared_canonical_task(tmp_path: Path) -> None:
    marker = "CANONICAL_TASK_BLOCK_V1"
    source = "class CandidateQueryEngine:\n    pass\n"
    common = {
        "profile_summary": "{}",
        "visible_history": "[]",
        "current_solution_source": source,
    }

    rendered_prompts = [
        render_template("mode_distribution.txt", **common),
        render_template("mode_edit_structured.txt", mode="micro", **common),
        render_template("step_batch_structured.txt", **common),
        render_template("mode_edit.txt", mode="micro", **common),
        render_template("mode_edit_replacement.txt", mode="micro", **common),
    ]
    assert all(marker in prompt for prompt in rendered_prompts)

    branch_file = tmp_path / "proposed_solution.py"
    branch_file.write_text(source, encoding="utf-8")
    direct_prompt = _render_direct_edit_prompt(
        {
            "mode": "micro",
            "file_path": str(branch_file),
            "prompt_context": {"profile_summary": {}, "visible_history": []},
            "max_iterations": 1,
            "max_source_chars": 4000,
            "iteration": 0,
            "raw_outputs": [],
            "parsed_outputs": [],
            "tool_events": [],
            "errors": [],
            "usage": {},
            "done": False,
            "final_summary": "",
        }
    )
    assert marker in direct_prompt
    assert shared_canonical_task() in direct_prompt


def test_shared_prompt_keeps_backend_wrappers_separate(tmp_path: Path) -> None:
    source = "class CandidateQueryEngine:\n    pass\n"
    structured_prompt = render_template(
        "step_batch_structured.txt",
        profile_summary="{}",
        visible_history="[]",
        current_solution_source=source,
    )
    branch_file = tmp_path / "proposed_solution.py"
    branch_file.write_text(source, encoding="utf-8")
    direct_prompt = _render_direct_edit_prompt(
        {
            "mode": "micro",
            "file_path": str(branch_file),
            "prompt_context": {"profile_summary": {}, "visible_history": []},
            "max_iterations": 1,
            "max_source_chars": 4000,
            "iteration": 0,
            "raw_outputs": [],
            "parsed_outputs": [],
            "tool_events": [],
            "errors": [],
            "usage": {},
            "done": False,
            "final_summary": "",
        }
    )

    assert "Exactly one compact structured edit candidate for each mode" in structured_prompt
    assert "Allowed tools:" in direct_prompt
    assert "CANONICAL_TASK_BLOCK_V1" in structured_prompt
    assert "CANONICAL_TASK_BLOCK_V1" in direct_prompt


def test_single_prompt_batch_prompt_is_explicit() -> None:
    rendered = render_template(
        "step_batch_structured.txt",
        profile_summary="{}",
        visible_history="[]",
        current_solution_source="class CandidateQueryEngine:\n    pass\n",
    )

    assert "This is the only model-generation prompt for this step" in rendered
    assert "Do not wait for\nseparate per-mode instructions" in rendered
    assert "all six mode-specific branch edits in\nthis single response" in rendered
    assert '"candidates": {' in rendered
    assert "Do not output candidates as a list" in rendered
    assert '\"layout\": {\"primary_mode\": \"layout\"' in rendered
    assert 'do not use "CandidateQueryEngine.put"' in rendered


def test_prompt_controlled_configs_are_single_prompt_batched() -> None:
    haiku_config = yaml.safe_load(Path("configs/hard_haiku_prompt_controlled_10step.yaml").read_text(encoding="utf-8"))
    qwen_config = yaml.safe_load(Path("configs/hard_qwen_prompt_controlled_10step.yaml").read_text(encoding="utf-8"))
    models_config = yaml.safe_load(Path("configs/models.yaml").read_text(encoding="utf-8"))["models"]

    assert haiku_config["experiment"]["candidate_generation"] == "batched"
    assert qwen_config["experiment"]["candidate_generation"] == "batched"
    assert haiku_config["models"]["include"] == ["claude_haiku_batch_strict"]
    assert qwen_config["models"]["include"] == ["weak_qwen_batch_strict"]
    assert models_config["claude_haiku_batch_strict"]["allow_batch_repair"] is False
    assert models_config["weak_qwen_batch_strict"]["batch_fallback_to_per_mode"] is False
    assert models_config["weak_qwen_batch_strict"]["allow_batch_repair"] is False
    assert models_config["weak_qwen_batch_strict"]["allow_response_format_retry"] is False
