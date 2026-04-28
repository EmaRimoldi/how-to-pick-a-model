from __future__ import annotations

import json

from vao.analysis.task_mode_bootstrap import bootstrap_decomposition


def test_bootstrap_decomposition_produces_key_terms(tmp_path) -> None:
    cells = [
        ("pilot", "range_local_scans", "small", 7301, 1.0, 0.80, 10.0),
        ("pilot", "range_local_scans", "large", 7301, 1.0, 0.70, 15.0),
        ("pilot", "topk_stress", "small", 7301, 1.0, 0.70, 10.0),
        ("pilot", "topk_stress", "large", 7301, 1.0, 0.72, 15.0),
        ("holdout", "range_local_scans", "small", 7401, 1.0, 0.78, 10.0),
        ("holdout", "range_local_scans", "large", 7401, 1.0, 0.68, 15.0),
        ("holdout", "topk_stress", "small", 7401, 1.0, 0.72, 10.0),
        ("holdout", "topk_stress", "large", 7401, 1.0, 0.90, 15.0),
    ]
    root = tmp_path / "runs"
    root.mkdir()
    modes = ["layout", "indexing", "topk", "caching", "summaries", "micro"]
    for split, task_mode, model_id, seed, baseline_loss, best_loss, elapsed in cells:
        run_dir = root / f"demo_{split}_{task_mode}_seed{seed}_{model_id}"
        run_dir.mkdir()
        manifest = {
            "run_id": run_dir.name,
            "profile_id": "hard_optimization",
            "model_id": model_id,
            "model_alias": model_id,
            "task_mode_true": task_mode,
            "task_mode_split": split,
            "instance_seed": seed,
            "visibility_regime": "top1_only",
            "modes": modes,
            "max_steps": 1,
            "config": {"models": {"include": [model_id]}},
        }
        summary = {
            "run_id": run_dir.name,
            "model_id": model_id,
            "baseline_loss": baseline_loss,
            "best_visible_loss": best_loss,
            "best_counterfactual_loss": best_loss,
            "elapsed_wall_seconds": elapsed,
            "steps_completed": 1,
        }
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (run_dir / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    result = bootstrap_decomposition(
        [root],
        out_dir=tmp_path / "out",
        success_threshold=0.95,
        success_mode="relative_improvement",
        improvement_threshold=0.05,
        pilot_split="pilot",
        holdout_split="holdout",
        smaller_model="small",
        larger_model="large",
        cost_metric="wall_seconds",
        bootstrap_samples=20,
        random_seed=0,
        task_prior_mode="uniform",
    )
    numeric = result["bootstrap_summary"]["numeric"]
    assert "pairwise.cost_term" in numeric
    assert "pairwise.competence_term" in numeric
    assert "decomposition.pilot_information_gain_nats" in numeric
    assert "decomposition.pilot_router_mismatch_nats" in numeric
