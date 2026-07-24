"""Smoke tests for the consolidated canonical package surface."""

from agent_workflow import AgentConfig, ExperimentConfig
from agent_workflow.modes.swarm import SwarmModeConfig, create_swarm_blackboard, run_swarm


def test_canonical_config_reexports_base_schema():
    cfg = ExperimentConfig.make_n_parallel(
        experiment_id="unit",
        n_agents=2,
        time_budget_minutes=1,
        train_time_budget_seconds=10,
        repo_root=".",
    )
    assert cfg.agents[0].agent_id == "agent_0"
    assert AgentConfig(agent_id="x").agent_id == "x"


def test_swarm_mode_creates_blackboard(tmp_path):
    sm = create_swarm_blackboard(tmp_path, SwarmModeConfig(max_context_entries=3))
    assert sm.path.exists()


def test_swarm_run_delegates_to_runtime(monkeypatch):
    calls = {}

    def fake_main(argv=None):
        calls["argv"] = argv

    monkeypatch.setattr(
        "agent_workflow.swarm.launcher.main_swarm",
        fake_main,
    )

    run_swarm(["--n-agents", "3"])

    assert calls["argv"] == ["--n-agents", "3"]
