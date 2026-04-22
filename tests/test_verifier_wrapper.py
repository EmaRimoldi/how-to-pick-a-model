from __future__ import annotations

from pathlib import Path

from benchmarks.stateful_query_engine.harness.run_benchmark import load_instance_config
from vao.candidate_preflight import run_candidate_preflight
from vao.verifier import evaluate_solution, validate_source


def test_source_validation_baseline() -> None:
    source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    assert validate_source(source)["passed"] is True


def test_paper_hard_profiles_are_configured() -> None:
    config = load_instance_config()
    expected = {
        "hard_balanced_dev",
        "hard_balanced_holdout",
        "hard_range_dev",
        "hard_range_holdout",
        "hard_churn_dev",
        "hard_churn_holdout",
        "hard_optimization",
    }
    assert expected <= set(config["profiles"])
    profile = config["profiles"]["hard_balanced_dev"]
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


def test_candidate_preflight_baseline_passes() -> None:
    result = run_candidate_preflight(Path("benchmarks/stateful_query_engine/solution_template.py"))
    assert result["passed"] is True
    assert result["operation_count"] > 0


def test_candidate_preflight_rejects_wrong_topk_order(tmp_path: Path) -> None:
    source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    source = source.replace(
        "rows.sort(key=lambda item: (-item[1], item[0]))",
        "rows.sort(key=lambda item: (item[1], item[0]))",
    )
    candidate = tmp_path / "bad_topk.py"
    candidate.write_text(source, encoding="utf-8")

    result = run_candidate_preflight(candidate)

    assert result["passed"] is False
    assert result["reason"] == "operation_divergence"
    assert result["operation"]["op"] == "top_k"


def test_evaluate_solution_skips_full_benchmark_on_preflight_failure(tmp_path: Path) -> None:
    source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    source = source.replace(
        "rows.sort(key=lambda item: (-item[1], item[0]))",
        "rows.sort(key=lambda item: (item[1], item[0]))",
    )
    candidate = tmp_path / "bad_topk.py"
    candidate.write_text(source, encoding="utf-8")

    result = evaluate_solution(
        candidate,
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

    assert result.correctness is False
    assert result.errors == ["preflight_failed:operation_divergence"]
    assert result.first_divergence["reason"] == "preflight_failed"
    assert not (tmp_path / "verifier_raw").exists()
