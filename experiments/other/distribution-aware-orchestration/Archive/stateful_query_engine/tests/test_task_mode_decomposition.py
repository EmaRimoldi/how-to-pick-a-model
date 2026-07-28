from __future__ import annotations

import math
import json

import pandas as pd

from vao.analysis.task_mode_decomposition import (
    _attempt_success,
    _filter_complete_models,
    _relative_improvement,
    _single_mode_crossover,
    _task_mode_priors,
    choose_router,
    load_attempt_records,
    mutual_information,
    pairwise_model_terms,
    pairwise_crossover,
    routing_triviality,
)


def _summary_frame() -> pd.DataFrame:
    rows = [
        {
            "split": "pilot",
            "task_mode_true": "range_local_scans",
            "model_id": "small",
            "attempt_count": 4,
            "success_prob": 0.30,
            "mean_best_loss": 0.91,
            "median_best_loss": 0.91,
            "median_cost": 1.0,
            "mean_steps_completed": 3.0,
        },
        {
            "split": "pilot",
            "task_mode_true": "range_local_scans",
            "model_id": "large",
            "attempt_count": 4,
            "success_prob": 0.80,
            "mean_best_loss": 0.70,
            "median_best_loss": 0.70,
            "median_cost": 1.5,
            "mean_steps_completed": 3.0,
        },
        {
            "split": "pilot",
            "task_mode_true": "topk_stress",
            "model_id": "small",
            "attempt_count": 4,
            "success_prob": 0.82,
            "mean_best_loss": 0.68,
            "median_best_loss": 0.68,
            "median_cost": 1.0,
            "mean_steps_completed": 3.0,
        },
        {
            "split": "pilot",
            "task_mode_true": "topk_stress",
            "model_id": "large",
            "attempt_count": 4,
            "success_prob": 0.76,
            "mean_best_loss": 0.69,
            "median_best_loss": 0.69,
            "median_cost": 1.5,
            "mean_steps_completed": 3.0,
        },
        {
            "split": "holdout",
            "task_mode_true": "range_local_scans",
            "model_id": "small",
            "attempt_count": 4,
            "success_prob": 0.28,
            "mean_best_loss": 0.93,
            "median_best_loss": 0.93,
            "median_cost": 1.0,
            "mean_steps_completed": 3.0,
        },
        {
            "split": "holdout",
            "task_mode_true": "range_local_scans",
            "model_id": "large",
            "attempt_count": 4,
            "success_prob": 0.78,
            "mean_best_loss": 0.72,
            "median_best_loss": 0.72,
            "median_cost": 1.5,
            "mean_steps_completed": 3.0,
        },
        {
            "split": "holdout",
            "task_mode_true": "topk_stress",
            "model_id": "small",
            "attempt_count": 4,
            "success_prob": 0.84,
            "mean_best_loss": 0.67,
            "median_best_loss": 0.67,
            "median_cost": 1.0,
            "mean_steps_completed": 3.0,
        },
        {
            "split": "holdout",
            "task_mode_true": "topk_stress",
            "model_id": "large",
            "attempt_count": 4,
            "success_prob": 0.74,
            "mean_best_loss": 0.71,
            "median_best_loss": 0.71,
            "median_cost": 1.5,
            "mean_steps_completed": 3.0,
        },
    ]
    return pd.DataFrame(rows)


def test_routing_triviality_detects_comparative_advantage() -> None:
    summary = _summary_frame()
    result = routing_triviality(summary, split="pilot")
    assert result["routing_is_trivial_empirically"] is False
    assert set(result["unique_best_models"]) == {"small", "large"}
    assert result["best_model_by_task_mode"]["range_local_scans"] == "large"
    assert result["best_model_by_task_mode"]["topk_stress"] == "small"
    assert result["sufficient_condition_fires"] is False


def test_router_information_and_crossover_are_finite() -> None:
    summary = _summary_frame()
    priors = {"range_local_scans": 0.5, "topk_stress": 0.5}
    router = choose_router(summary, split="pilot", temperature=0.25)
    info = mutual_information(priors, router)
    assert info > 0.0

    crossover = pairwise_crossover(
        summary,
        split="holdout",
        smaller_model="small",
        larger_model="large",
        task_priors=priors,
    )
    assert crossover["aggregate_d_cross"] >= 1.0
    assert math.isfinite(crossover["aggregate_d_cross"])
    assert len(crossover["family_rows"]) == 2


def test_relative_improvement_success_rule() -> None:
    improvement = _relative_improvement(1.0, 0.8)
    assert math.isclose(improvement, 0.2)
    assert _attempt_success(
        baseline_loss=1.0,
        best_loss=0.8,
        success_mode="relative_improvement",
        success_threshold=0.95,
        improvement_threshold=0.15,
    )
    assert not _attempt_success(
        baseline_loss=1.0,
        best_loss=0.95,
        success_mode="relative_improvement",
        success_threshold=0.95,
        improvement_threshold=0.10,
    )


def test_filter_complete_models_drops_incomplete_entries() -> None:
    summary = _summary_frame()
    extra = pd.DataFrame(
        [
            {
                "split": "pilot",
                "task_mode_true": "range_local_scans",
                "model_id": "incomplete",
                "attempt_count": 1,
                "success_prob": 0.1,
                "mean_best_loss": 1.1,
                "median_best_loss": 1.1,
                "median_cost": 2.0,
                "mean_steps_completed": 1.0,
            }
        ]
    )
    filtered = _filter_complete_models(pd.concat([summary, extra], ignore_index=True), pilot_split="pilot", holdout_split="holdout")
    assert "incomplete" not in set(filtered["model_id"])


def test_single_mode_crossover_handles_certain_large_model() -> None:
    assert math.isinf(_single_mode_crossover(1e-6, 1.0))
    assert _single_mode_crossover(1.0, 1.0) == 1.0


def test_pairwise_model_terms_are_finite() -> None:
    summary = _summary_frame()
    priors = {"range_local_scans": 0.5, "topk_stress": 0.5}
    terms = pairwise_model_terms(
        summary,
        split="holdout",
        baseline_model="small",
        comparison_model="large",
        task_priors=priors,
    )
    assert math.isfinite(terms["cost_term"])
    assert math.isfinite(terms["competence_term"])


def test_uniform_task_mode_priors_ignore_sampling_imbalance() -> None:
    summary = _summary_frame()
    priors = _task_mode_priors(summary, split="holdout", mode="uniform")
    assert priors == {"range_local_scans": 0.5, "topk_stress": 0.5}


def test_load_attempt_records_infers_model_alias_from_config(tmp_path) -> None:
    run_dir = tmp_path / "oracle_family_demo_pilot_range_local_scans_seed7301_gpt_5_3_codex_spark_batch_strict"
    run_dir.mkdir()
    manifest = {
        "run_id": run_dir.name,
        "profile_id": "hard_optimization",
        "model_id": "gpt-5.3-codex-spark",
        "task_mode_true": "range_local_scans",
        "task_mode_split": "pilot",
        "instance_seed": 7301,
        "visibility_regime": "top1_only",
        "modes": ["layout", "indexing", "topk", "caching", "summaries", "micro"],
        "max_steps": 1,
        "config": {"models": {"include": ["gpt_5_3_codex_spark_batch_strict"]}},
    }
    summary = {
        "run_id": run_dir.name,
        "model_id": "gpt-5.3-codex-spark",
        "baseline_loss": 1.0,
        "best_visible_loss": 0.8,
        "best_counterfactual_loss": 0.75,
        "elapsed_wall_seconds": 12.0,
        "steps_completed": 1,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    records = load_attempt_records(
        [tmp_path],
        success_threshold=0.95,
        success_mode="relative_improvement",
        improvement_threshold=0.05,
    )
    assert len(records) == 1
    assert records[0].model_id == "gpt-5.3-codex-spark"
    assert records[0].model_alias == "gpt_5_3_codex_spark_batch_strict"
