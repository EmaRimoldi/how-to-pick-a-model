#!/usr/bin/env python3
"""Render paper-facing plots from frozen four-term analysis JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


TERM_SPECS = (
    ("unit_cost_nats", "unit cost", "#247BA0"),
    ("competence_nats", "competence", "#70C1B3"),
    ("information_nats", "information", "#F3A712"),
    ("mismatch_nats", "- mismatch", "#D1495B"),
)


def primary_rows(document: dict) -> list[dict]:
    return [row for row in document["results"] if row["comparison"] == "cross_model_primary"]


def condition_label(row: dict) -> str:
    return f"a={row['alpha']:.1f}\n{row['allocation'].replace('_', ' ')}"


def plot_closure(rows: list[dict], output: Path) -> None:
    figure, axis = plt.subplots(figsize=(4.6, 4.1), constrained_layout=True)
    colors = {0.6: "#247BA0", 0.8: "#D1495B"}
    markers = {"matched": "o", "prior": "s", "half_anti": "^"}
    for row in rows:
        axis.scatter(
            row["predicted_delta_nats"],
            row["observed_delta_nats"],
            color=colors[row["alpha"]],
            marker=markers[row["allocation"]],
            s=58,
            edgecolor="white",
            linewidth=0.7,
            zorder=3,
        )
    values = [
        float(row[key])
        for row in rows
        for key in ("predicted_delta_nats", "observed_delta_nats")
    ]
    margin = max(0.05, 0.08 * (max(values) - min(values)))
    limits = (min(values) - margin, max(values) + margin)
    axis.plot(limits, limits, color="#202124", linewidth=1.1, linestyle="--")
    axis.set(xlim=limits, ylim=limits, xlabel="four-term prediction (nat)", ylabel="held-out observed gain (nat)")
    axis.grid(alpha=0.2, linewidth=0.7)
    for alpha, color in colors.items():
        axis.scatter([], [], color=color, label=f"alpha={alpha:.1f}")
    for name, marker in markers.items():
        axis.scatter([], [], color="#555555", marker=marker, label=name.replace("_", " "))
    axis.legend(frameon=False, fontsize=8, ncol=2)
    figure.savefig(output, dpi=220)
    plt.close(figure)


def plot_decomposition(rows: list[dict], output: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.4, 4.2), constrained_layout=True)
    x = np.arange(len(rows))
    positive = np.zeros(len(rows))
    negative = np.zeros(len(rows))
    for key, label, color in TERM_SPECS:
        values = np.asarray(
            [-float(row[key]) if key == "mismatch_nats" else float(row[key]) for row in rows]
        )
        bottoms = np.where(values >= 0.0, positive, negative)
        axis.bar(x, values, bottom=bottoms, width=0.68, color=color, label=label)
        positive += np.where(values >= 0.0, values, 0.0)
        negative += np.where(values < 0.0, values, 0.0)
    axis.scatter(
        x,
        [row["observed_delta_nats"] for row in rows],
        color="#111111",
        marker="D",
        s=30,
        label="held-out observed",
        zorder=4,
    )
    axis.axhline(0.0, color="#202124", linewidth=0.8)
    axis.set_xticks(x, [condition_label(row) for row in rows])
    axis.set_ylabel("log-resource gain (nat)")
    axis.grid(axis="y", alpha=0.2, linewidth=0.7)
    axis.legend(frameon=False, fontsize=8, ncol=3, loc="upper center")
    figure.savefig(output, dpi=220)
    plt.close(figure)


def plot_inverse_share(document: dict, output: Path) -> None:
    figure, axis = plt.subplots(figsize=(5.2, 4.1), constrained_layout=True)
    colors = {
        "Qwen/Qwen2.5-Coder-7B-Instruct": "#247BA0",
        "Qwen/Qwen2.5-Coder-14B-Instruct": "#D1495B",
    }
    for model in sorted({row["model"] for row in document["cells"]}):
        model_rows = [row for row in document["cells"] if row["model"] == model]
        for mode in range(3):
            cells = sorted(
                (row for row in model_rows if row["mode"] == mode),
                key=lambda row: -np.log(row["q_true"]),
            )
            x = [-np.log(row["q_true"]) for row in cells]
            y = [
                np.log(row["mean_first_passage_slots"] / row["focused_mean_slots"])
                for row in cells
            ]
            axis.plot(x, y, color=colors[model], alpha=0.45, linewidth=1.0)
            axis.scatter(x, y, color=colors[model], s=16, alpha=0.75)
    limits = axis.get_xlim()
    axis.plot(limits, limits, color="#202124", linestyle="--", linewidth=1.0, label="unit slope")
    for model, color in colors.items():
        axis.plot([], [], color=color, label=model.split("/")[-1].replace("-Instruct", ""))
    axis.set(xlabel="-log allocation share", ylabel="log normalized first-passage slots")
    axis.grid(alpha=0.2, linewidth=0.7)
    axis.legend(frameon=False, fontsize=8)
    figure.savefig(output, dpi=220)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--inverse-share", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    document = json.loads(args.analysis.read_text(encoding="utf-8"))
    rows = primary_rows(document)
    if not rows:
        raise SystemExit("analysis has no cross-model primary results")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plot_closure(rows, args.output_dir / "four_term_observed_vs_predicted.png")
    plot_decomposition(rows, args.output_dir / "four_term_decomposition.png")
    if args.inverse_share is not None:
        inverse = json.loads(args.inverse_share.read_text(encoding="utf-8"))
        plot_inverse_share(inverse, args.output_dir / "inverse_share_scaling.png")


if __name__ == "__main__":
    main()
