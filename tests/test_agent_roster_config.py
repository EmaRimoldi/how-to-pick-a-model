from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_workflow.config import ExperimentConfig
from agent_workflow.launcher import (
    _apply_agent_selection_args,
    _apply_budget_args,
    _coerce_config_for_mode,
)
from agent_workflow.orchestrator import _render_first_message


def _write_roster_config(path: Path) -> None:
    path.write_text(
        """
experiment:
  id: roster_test
  mode: parallel_shared
agents:
  time_budget_minutes: 30
  train_time_budget_seconds: 300
  model: claude-haiku-4-5-20251001
  cuda_devices: ["0", "1", "2"]
  use_shared_memory: true
  roster:
    - id: explorer
      role: broad search
      model: claude-sonnet-4-6
      temperature: 1.2
      cuda_device: "0"
    - id: optimizer
      role: conservative refinement
      temperature: 0.3
      cuda_device: "1"
    - id: regularizer
      role: regularization search
      cuda_device: "2"
evaluator:
  train_max_steps: 1170
  concurrency: serialized
slurm:
  enabled: false
""".strip()
    )


def test_yaml_roster_defines_named_agents_with_roles(tmp_path: Path):
    config_path = tmp_path / "roster.yaml"
    _write_roster_config(config_path)

    config = ExperimentConfig.from_yaml(config_path, repo_root=str(tmp_path))

    assert config.experiment_id == "roster_test"
    assert config.mode == "parallel_shared"
    assert [agent.agent_id for agent in config.agents] == [
        "explorer",
        "optimizer",
        "regularizer",
    ]
    assert [agent.role for agent in config.agents] == [
        "broad search",
        "conservative refinement",
        "regularization search",
    ]
    assert config.agents[0].model == "claude-sonnet-4-6"
    assert config.agents[0].temperature == 1.2
    assert all(agent.use_shared_memory for agent in config.agents)
    assert all(agent.train_max_steps == 1170 for agent in config.agents)


def test_roster_rejects_invalid_agent_ids(tmp_path: Path):
    config_path = tmp_path / "bad_roster.yaml"
    config_path.write_text(
        """
experiment:
  id: bad
agents:
  roster:
    - id: "bad id"
      role: invalid
""".strip()
    )

    with pytest.raises(ValueError, match="agent ids"):
        ExperimentConfig.from_yaml(config_path, repo_root=str(tmp_path))


def test_empty_roster_falls_back_to_compact_agent_count(tmp_path: Path):
    config_path = tmp_path / "empty_roster.yaml"
    config_path.write_text(
        """
experiment:
  id: compact
agents:
  n: 2
  roster: []
  cuda_devices: ["0", "1"]
""".strip()
    )

    config = ExperimentConfig.from_yaml(config_path, repo_root=str(tmp_path))

    assert [agent.agent_id for agent in config.agents] == ["agent_0", "agent_1"]


def test_launcher_can_truncate_roster_for_requested_parallel_count(tmp_path: Path):
    config_path = tmp_path / "roster.yaml"
    _write_roster_config(config_path)
    config = ExperimentConfig.from_yaml(config_path, repo_root=str(tmp_path))

    coerced = _coerce_config_for_mode(config, "parallel_shared", n_agents=2)

    assert coerced.mode == "parallel_shared"
    assert [agent.agent_id for agent in coerced.agents] == ["explorer", "optimizer"]
    assert all(agent.use_shared_memory for agent in coerced.agents)


def test_cli_overrides_apply_to_loaded_roster_config(tmp_path: Path):
    config_path = tmp_path / "roster.yaml"
    _write_roster_config(config_path)
    config = ExperimentConfig.from_yaml(config_path, repo_root=str(tmp_path))
    config = _coerce_config_for_mode(config, "parallel_shared", n_agents=2)

    _apply_budget_args(config, SimpleNamespace(time_budget=12, train_budget=90))
    _apply_agent_selection_args(
        config,
        SimpleNamespace(model="claude-opus-4-6", cuda_devices="4,5"),
    )

    assert [agent.time_budget_minutes for agent in config.agents] == [12, 12]
    assert [agent.train_time_budget_seconds for agent in config.agents] == [90, 90]
    assert [agent.model for agent in config.agents] == [
        "claude-opus-4-6",
        "claude-opus-4-6",
    ]
    assert [agent.cuda_device for agent in config.agents] == ["4", "5"]


def test_agent_role_is_rendered_into_first_message(tmp_path: Path):
    config_path = tmp_path / "roster.yaml"
    _write_roster_config(config_path)
    config = ExperimentConfig.from_yaml(config_path, repo_root=str(tmp_path))

    rendered = _render_first_message(
        prompt="Agent {{AGENT_ID}} role: {{AGENT_ROLE}} at {{WORKSPACE}}",
        agent_config=config.agents[0],
        run_id="run",
        experiment_id="exp",
        workspace=tmp_path,
    )

    assert "Agent explorer role: broad search" in rendered
