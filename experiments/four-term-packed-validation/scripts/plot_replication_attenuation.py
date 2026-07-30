#!/usr/bin/env python3
"""Plot the frozen finite-replication attenuation diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-bias", type=Path, required=True)
    parser.add_argument("--replication-bias", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    primary_bias = load_json(args.primary_bias)
    replication_bias = load_json(args.replication_bias)
    decision = load_json(args.decision)

    repetitions = [
        int(decision["primary_repetitions_per_task_cell"]),
        int(decision["replication_repetitions_per_task_cell"]),
    ]
    observed = [
        float(decision["primary_mismatch_slope"]),
        float(decision["replication_mismatch_slope"]),
    ]
    intervals = [
        decision["primary_mismatch_slope_ci_95"],
        decision["replication_mismatch_slope_ci_95"],
    ]
    predicted_bias = [
        float(primary_bias["predicted_finite_replication_mismatch_slope"]),
        float(replication_bias["predicted_finite_replication_mismatch_slope"]),
    ]

    lower_errors = [value - float(interval[0]) for value, interval in zip(observed, intervals)]
    upper_errors = [float(interval[1]) - value for value, interval in zip(observed, intervals)]

    figure, axis = plt.subplots(figsize=(5.4, 4.1), constrained_layout=True)
    axis.errorbar(
        repetitions,
        observed,
        yerr=[lower_errors, upper_errors],
        color="#247BA0",
        marker="o",
        markersize=6,
        linewidth=1.5,
        capsize=3,
        label="observed slope (95% bootstrap CI)",
    )
    axis.plot(
        repetitions,
        predicted_bias,
        color="#D1495B",
        marker="s",
        markersize=5,
        linewidth=1.3,
        linestyle="--",
        label="finite-repetition bias prediction",
    )
    axis.axhline(0.0, color="#202124", linewidth=0.9)
    axis.axhline(
        float(decision["attenuation_threshold_slope"]),
        color="#F3A712",
        linewidth=1.0,
        linestyle=":",
        label="frozen attenuation threshold",
    )
    axis.set_xticks(repetitions)
    axis.set(
        xlabel="trajectories per task cell",
        ylabel="residual slope against mismatch",
    )
    axis.grid(alpha=0.2, linewidth=0.7)
    axis.legend(frameon=False, fontsize=8)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=220)
    plt.close(figure)


if __name__ == "__main__":
    main()
