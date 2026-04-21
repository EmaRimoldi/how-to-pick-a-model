from __future__ import annotations

from pathlib import Path

from benchmarks.stateful_query_engine.harness.run_benchmark import load_instance_config
from vao.verifier import evaluate_solution, validate_source


def test_source_validation_baseline() -> None:
    source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    assert validate_source(source)["passed"] is True


def test_single_hard_optimization_profile_is_configured() -> None:
    config = load_instance_config()
    assert set(config["profiles"]) == {"hard_optimization"}
    profile = config["profiles"]["hard_optimization"]
    assert profile["initial_size"] >= 2500
    assert profile["key_space"] >= 100000
    assert profile["trace_length"] >= 1000
    assert profile["traces_per_family"] >= 1
    assert set(profile["families"]) == {
        "uniform_read_heavy",
        "zipf_hot_key",
        "bursty_mixed",
        "range_local_scans",
        "distribution_shift",
        "wide_range_churn",
        "temporal_repeat_windows",
        "topk_stress",
        "negative_lookup_churn",
    }


def test_verifier_wrapper_tiny_profile(tmp_path: Path) -> None:
    result = evaluate_solution(
        Path("benchmarks/stateful_query_engine/solution_template.py"),
        "hard_optimization",
        120,
        tmp_path / "verification.json",
        instance_overrides={
            "initial_size": 20,
            "key_space": 200,
            "trace_length": 20,
            "traces_per_family": 1,
            "families": ["uniform_read_heavy"],
            "repetitions": 1,
            "warmup_prefix": 0,
        },
    )
    assert result.correctness is True
    assert result.latent_loss > 0
    assert (tmp_path / "verification.json").exists()
