from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize_scalar

from src.dataset import load_config
from src.run_strategy_router import MODE_ORDER


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=-1, keepdims=True)


def temperature_scale(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probabilities, 1.0e-9, 1.0))
    return softmax(logits / temperature)


def fit_temperature(probabilities: np.ndarray, labels: np.ndarray) -> float:
    def objective(log_temperature: float) -> float:
        calibrated = temperature_scale(probabilities, math.exp(log_temperature))
        return float(-np.mean(np.log(np.clip(calibrated[np.arange(len(labels)), labels], 1.0e-12, 1.0))))

    result = minimize_scalar(objective, bounds=(math.log(0.05), math.log(20.0)), method="bounded")
    return float(math.exp(result.x))


def entropy(probabilities: np.ndarray) -> np.ndarray:
    values = np.clip(probabilities, 1.0e-12, 1.0)
    return -np.sum(values * np.log(values), axis=-1)


def load_rows(raw_dir: Path, run_id: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(raw_dir.glob("router_*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if run_id is None or row.get("run_id") == run_id:
                    rows.append(row)
    if not rows:
        raise FileNotFoundError(f"No router logs in {raw_dir}")
    return rows


def summarize(config: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    mode_index = {mode: idx for idx, mode in enumerate(MODE_ORDER)}
    strategies = list(config["strategies"])
    smoothing = float(config["allocation"]["smoothing"])
    by_model_context: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_model_context[(str(row.get("model_key", "shared")), int(row["context_examples"]))].append(row)

    summaries: dict[str, dict[str, Any]] = defaultdict(dict)
    for (model_key, context_size), context_rows in sorted(by_model_context.items()):
        calibrated_rows: list[dict[str, Any]] = []
        folds = sorted({int(row["fold"]) for row in context_rows})
        temperatures: dict[str, float] = {}
        for heldout_fold in folds:
            train = [row for row in context_rows if int(row["fold"]) != heldout_fold]
            test = [row for row in context_rows if int(row["fold"]) == heldout_fold]
            train_p = np.asarray([[row["posterior_raw"][mode] for mode in MODE_ORDER] for row in train])
            train_y = np.asarray([mode_index[row["true_mode"]] for row in train], dtype=int)
            temperature = fit_temperature(train_p, train_y)
            temperatures[str(heldout_fold)] = temperature
            for row in test:
                raw = np.asarray([[row["posterior_raw"][mode] for mode in MODE_ORDER]])
                updated = dict(row)
                updated["posterior_calibrated"] = temperature_scale(raw, temperature)[0]
                calibrated_rows.append(updated)

        probabilities = np.asarray([row["posterior_calibrated"] for row in calibrated_rows])
        labels = np.asarray([mode_index[row["true_mode"]] for row in calibrated_rows], dtype=int)
        counts = np.bincount(labels, minlength=len(MODE_ORDER)).astype(float)
        prior = counts / np.sum(counts)
        allocations = np.asarray(
            [[row["allocation"][strategy] for strategy in strategies] for row in calibrated_rows],
            dtype=float,
        )
        q = (allocations + smoothing) / np.sum(allocations + smoothing, axis=1, keepdims=True)
        h_prior = float(entropy(prior[None, :])[0])
        posterior_entropy = float(np.mean(entropy(probabilities)))
        g_entropy = h_prior - posterior_entropy
        g_logscore = h_prior + float(
            np.mean(np.log(np.clip(probabilities[np.arange(len(labels)), labels], 1.0e-12, 1.0)))
        )
        epsilon = float(
            np.mean(
                np.sum(
                    probabilities
                    * (np.log(np.clip(probabilities, 1.0e-12, 1.0)) - np.log(np.clip(q, 1.0e-12, 1.0))),
                    axis=1,
                )
            )
        )
        summaries[model_key][str(context_size)] = {
            "n": len(calibrated_rows),
            "temperatures_by_heldout_fold": temperatures,
            "prior": {mode: float(prior[idx]) for idx, mode in enumerate(MODE_ORDER)},
            "accuracy": float(np.mean(np.argmax(probabilities, axis=1) == labels)),
            "nll": float(-np.mean(np.log(np.clip(probabilities[np.arange(len(labels)), labels], 1.0e-12, 1.0)))),
            "H_prior": h_prior,
            "H_posterior": posterior_entropy,
            "G_entropy": g_entropy,
            "G_logscore_lower_bound": g_logscore,
            "epsilon_kl": epsilon,
            "M_eff": float(math.exp(posterior_entropy)),
            "parse_failure_rate": float(np.mean([row["parse_failed"] for row in calibrated_rows])),
        }
    return {"schema_version": 2, "by_model_and_context_examples": dict(summaries)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-fit strategy-router calibration and information terms")
    parser.add_argument("--config", default="experiments/humaneval-plus/strategy-by-difficulty-grid/configs/strategy_experiment.yaml")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    output = summarize(config, load_rows(Path(config["paths"]["raw"]), args.run_id))
    suffix = f"_{args.run_id}" if args.run_id else ""
    path = Path(config["paths"]["derived"]) / f"router_information_summary{suffix}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
