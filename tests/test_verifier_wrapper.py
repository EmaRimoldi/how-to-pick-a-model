from __future__ import annotations

from pathlib import Path

from vao.verifier import evaluate_solution, validate_source


def test_source_validation_baseline() -> None:
    source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    assert validate_source(source)["passed"] is True


def test_verifier_wrapper_tiny_profile(tmp_path: Path) -> None:
    result = evaluate_solution(
        Path("benchmarks/stateful_query_engine/solution_template.py"),
        "paper_development",
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
