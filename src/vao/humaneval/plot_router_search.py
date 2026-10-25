from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


LABELS = {"1.5b": "Qwen 1.5B", "7b": "Qwen 7B", "32b": "Qwen 32B"}
COLORS = {"1.5b": "#2F6B8A", "7b": "#2A9D8F", "32b": "#D95D39"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot confirmatory router-search results")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))["results"]
    models = ["1.5b", "7b", "32b"]
    values = []
    intervals = []
    annotations = []
    for model in models:
        config = next(iter(data[model].values()))
        result = next(iter(config.values()))
        values.append(result["multiplicative_speedup"])
        intervals.append(result["speedup_95ci"])
        annotations.append(
            f"{result['routed_successes']}/{result['n_tasks']} solved"
        )
    values_array = np.asarray(values)
    interval_array = np.asarray(intervals)
    errors = np.vstack((values_array - interval_array[:, 0], interval_array[:, 1] - values_array))
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["STIXGeneral", "DejaVu Serif"],
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axis = plt.subplots(figsize=(3.35, 2.55), constrained_layout=True)
    x = np.arange(len(models))
    axis.bar(x, values_array, color=[COLORS[m] for m in models], width=0.62, alpha=0.9)
    axis.errorbar(x, values_array, yerr=errors, fmt="none", color="#1F2933", capsize=3, lw=1)
    axis.axhline(1, color="#52606D", lw=0.8, ls="--")
    for idx, (value, label) in enumerate(zip(values_array, annotations, strict=True)):
        axis.text(idx, max(interval_array[idx, 1], value) + 0.025, label, ha="center", va="bottom", fontsize=7.5)
    axis.set_xticks(x, [LABELS[m] for m in models])
    axis.set_ylabel("Paired certified-time speedup")
    axis.set_ylim(0.68, max(interval_array[:, 1]) + 0.16)
    axis.grid(axis="y", color="#D9E2EC", lw=0.55)
    fig.savefig(args.output, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
