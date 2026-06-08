from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vao.prompts import render_template


def test_prompt_files_are_in_expected_catalogs() -> None:
    assert {path.name for path in Path("src/vao/prompts").glob("*.txt")} == {
        "single_step_program.txt",
    }
    assert {path.name for path in Path("autoresearch/prompts").glob("*.txt")} == {
        "autoresearch_allocation_router.txt",
        "autoresearch_program.txt",
        "autoresearch_router.txt",
    }


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


def test_autoresearch_prompt_contains_task_specific_contract() -> None:
    source = "def main():\n    pass\n"
    rendered = render_template(
        "autoresearch_program.txt",
        profile_summary="{}",
        visible_history="[]",
        current_solution_source=source,
    )
    assert "VAO_AUTORESEARCH_PROGRAM_V3" in rendered
    assert "This is an experiment to have the LLM do its own research" in rendered
    assert "the framework performs the filesystem" in rendered
    assert "Lower\nvalidation loss is better" in rendered
    assert "layout: architecture and model-capacity changes" in rendered
    assert "`SEED`, `DEPTH`, `BASE_CHANNELS`" in rendered
    assert "If the\nschema asks for one candidate" in rendered
    assert "schema asks for a full\n   trajectory" in rendered


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


def test_active_autoresearch_configs_use_canonical_prompt() -> None:
    config_paths = [
        Path("autoresearch/configs/autoresearch_cifar10_model_routing.yaml"),
        Path("autoresearch/configs/autoresearch_cifar10_pilot.yaml"),
        Path("autoresearch/configs/autoresearch_cifar10_single_trajectory_campaign.yaml"),
        Path("autoresearch/configs/autoresearch_cifar10_workload_pilot.yaml"),
        Path("autoresearch/configs/autoresearch_cifar10_workload_holdout.yaml"),
    ]
    for path in config_paths:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert config["experiment"]["prompt_template"] == "autoresearch_program.txt"
        assert config["experiment"]["candidate_generation"] == "interactive_session"
        assert config["experiment"]["steps"] == 20


def test_model_routing_config_contains_existing_backends() -> None:
    matrix = yaml.safe_load(Path("autoresearch/configs/autoresearch_cifar10_model_routing.yaml").read_text(encoding="utf-8"))
    models_config = yaml.safe_load(Path("configs/models.yaml").read_text(encoding="utf-8"))["models"]
    requested = set(matrix["models"]["include"])

    assert matrix["experiment"]["candidate_generation"] == "interactive_session"
    assert matrix["experiment"]["prompt_template"] == "autoresearch_program.txt"
    assert requested == {"gpt_5_3_codex", "gpt_5_4", "gpt_5_4_mini"}
    assert all(name in models_config for name in requested)
    for name in requested:
        assert models_config[name]["edit_protocol"] == "structured_edits"
    for name in {item for item in requested if item.startswith("gpt_")}:
        assert models_config[name]["adapter"] == "codex_cli"


def test_autoresearch_single_trajectory_campaign_config_is_interactive_h20() -> None:
    config = yaml.safe_load(Path("autoresearch/configs/autoresearch_cifar10_single_trajectory_campaign.yaml").read_text(encoding="utf-8"))

    assert config["experiment"]["candidate_generation"] == "interactive_session"
    assert config["experiment"]["steps"] == 20
    assert config["experiment"]["prompt_template"] == "autoresearch_program.txt"
    assert config["benchmark"]["id"] == "autoresearch_cifar10"
