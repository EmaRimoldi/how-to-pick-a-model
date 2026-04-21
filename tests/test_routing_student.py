from __future__ import annotations

import json

from vao.taxonomy import MODES
from vao.training.train_routing_lora import run_training


def test_routing_student_training_outputs_metrics(tmp_path):
    records_path = tmp_path / "routing.jsonl"
    rows = []
    for index, mode in enumerate(["layout", "indexing", "layout", "topk", "indexing", "layout"]):
        gains = {item: -0.1 for item in MODES}
        gains[mode] = 1.0
        pstar = {item: 0.0 for item in MODES}
        pstar[mode] = 1.0
        rows.append(
            {
                "run_id": "toy",
                "profile_id": "hard_optimization",
                "model_id": "teacher",
                "step": index,
                "input": {
                    "profile_summary": {"profile_id": "hard_optimization"},
                    "current_solution_hash": f"h{index}",
                    "current_solution_source": f"class CandidateQueryEngine: pass  # {mode}",
                    "visible_history": [],
                    "recent_decision_history": [],
                    "full_history_summary": "",
                },
                "productive_mode_top1": mode,
                "productive_mode_distribution": pstar,
                "verified_gain_per_mode": gains,
                "original_mode_probs": {item: 1 / len(MODES) for item in MODES},
                "original_top1_regret": 1.1,
            }
        )
    records_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    result = run_training(
        {
            "training": {
                "train_records": str(records_path),
                "output_dir": str(tmp_path / "model"),
                "train_summary_out": str(tmp_path / "train.json"),
                "eval_summary_out": str(tmp_path / "eval.json"),
                "seed": 1,
                "dev_fraction": 0.33,
                "max_features": 200,
            }
        }
    )
    assert result["train_summary"]["status"] == "completed"
    assert result["train_summary"]["train_count"] > 0
    assert result["eval_summary"]["record_count"] > 0
    assert (tmp_path / "model" / "model.pkl").exists()
