"""Tests for budgeting.py."""

import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agent_workflow.budgeting import BudgetTracker
from agent_workflow.config import ExperimentConfig


def test_budget_not_expired_before_start():
    tracker = BudgetTracker(wall_clock_budget_seconds=60)
    assert not tracker.is_expired()
    assert not tracker.should_stop()


def test_budget_expires_after_clock_starts():
    tracker = BudgetTracker(wall_clock_budget_seconds=1)
    tracker.start_budget_clock()
    time.sleep(1.1)
    assert tracker.is_expired()
    assert tracker.should_stop()


def test_startup_expires_before_first_turn():
    tracker = BudgetTracker(wall_clock_budget_seconds=3600, startup_deadline_seconds=1)
    time.sleep(1.1)
    assert tracker.startup_expired()


def test_budget_not_started_initially():
    tracker = BudgetTracker(wall_clock_budget_seconds=60)
    assert not tracker.budget_started()
    assert tracker.remaining_seconds() == 60.0


def test_remaining_minutes():
    tracker = BudgetTracker(wall_clock_budget_seconds=120)
    tracker.start_budget_clock()
    remaining = tracker.remaining_minutes()
    assert remaining in (1, 2)  # 2 minutes initially


def test_refund_extends_budget():
    tracker = BudgetTracker(wall_clock_budget_seconds=10)
    tracker.start_budget_clock()
    time.sleep(0.1)
    before = tracker.remaining_seconds()
    tracker.refund_seconds(5.0)
    after = tracker.remaining_seconds()
    assert after > before


def test_parallel_budget_matches_single_budget():
    """Both modes should use the same total compute budget."""
    T = 30  # base budget in minutes

    parallel_config = ExperimentConfig.make_parallel(
        experiment_id="test_parallel",
        time_budget_minutes=T,
        train_time_budget_seconds=300,
        repo_root="/tmp",
    )

    single_config = ExperimentConfig.make_single_long(
        experiment_id="test_single",
        time_budget_minutes=T,
        train_time_budget_seconds=300,
        repo_root="/tmp",
    )

    # Parallel: 2 agents × T minutes each = 2T total compute
    parallel_total = sum(a.time_budget_minutes for a in parallel_config.agents)
    # Single: 1 agent × 2T = 2T total compute
    single_total = sum(a.time_budget_minutes for a in single_config.agents)

    assert parallel_total == single_total == 2 * T


def test_fixed_step_config_propagates_to_agents():
    config = ExperimentConfig.make_parallel(
        experiment_id="test_parallel",
        time_budget_minutes=30,
        train_time_budget_seconds=300,
        train_max_steps=1170,
        repo_root="/tmp",
    )

    assert config.train_max_steps == 1170
    assert all(agent.train_max_steps == 1170 for agent in config.agents)


def test_agent_stops_after_budget():
    """BudgetTracker.should_stop() returns True when remaining <= 30s."""
    tracker = BudgetTracker(wall_clock_budget_seconds=31)
    tracker.start_budget_clock()
    time.sleep(1.1)
    assert tracker.remaining_seconds() < 30.0
    assert tracker.should_stop()
