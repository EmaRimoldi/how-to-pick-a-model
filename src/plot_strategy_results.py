from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from src.dataset import load_config


MODE_LABELS = {"easy": "Mode 1", "medium": "Mode 2", "hard": "Mode 3"}
STRATEGY_LABELS = {
    "mode1_direct": "Direct",
    "mode2_structured": "Structured",
    "mode3_robust": "Robust",
}
MODEL_LABELS = {"1.5b": "Qwen 1.5B", "7b": "Qwen 7B", "32b": "Qwen 32B"}
COLORS = {
    "cost": "#2F6B8A",
    "competence": "#2A9D8F",
    "information": "#E9B949",
    "mismatch": "#D95D39",
    "observed": "#1F2933",
    "predicted": "#7A5195",
    "mode1": "#007C91",
    "mode2": "#E9B949",
    "mode3": "#D95D39",
}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["STIXGeneral", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 160,
            "savefig.dpi": 300,
        }
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def plot_specialization(summary: dict[str, Any], output: Path) -> None:
    models = [model for model in ("1.5b", "7b", "32b") if model in summary["models"]]
    modes = ["easy", "medium", "hard"]
    strategies = list(summary["strategies"])
    fig, axes = plt.subplots(1, len(models), figsize=(7.05, 2.35), constrained_layout=True)
    axes = np.atleast_1d(axes)
    image = None
    for axis, model in zip(axes, models, strict=True):
        matrix = np.asarray(
            [
                [summary["cells"][f"{model}|{mode}|{strategy}"]["success_rate"] for strategy in strategies]
                for mode in modes
            ]
        )
        image = axis.imshow(matrix, vmin=0, vmax=1, cmap="viridis", aspect="equal")
        for row in range(3):
            for column in range(3):
                value = matrix[row, column]
                color = "white" if value < 0.42 or value > 0.82 else "#111827"
                axis.text(column, row, f"{100 * value:.0f}%", ha="center", va="center", color=color, fontweight="bold")
            axis.add_patch(plt.Rectangle((row - 0.5, row - 0.5), 1, 1, fill=False, edgecolor="#F4F1DE", lw=1.8))
        axis.set_title(MODEL_LABELS[model], fontweight="bold")
        axis.set_xticks(range(3), [STRATEGY_LABELS[value] for value in strategies], rotation=25, ha="right")
        axis.set_yticks(range(3), [MODE_LABELS[value] for value in modes])
        axis.set_xlabel("Strategy")
    axes[0].set_ylabel("Task mode")
    if image is not None:
        colorbar = fig.colorbar(image, ax=axes, shrink=0.83, pad=0.02)
        colorbar.set_label("Verified success within 20 retries")
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def plot_accounting(closure: dict[str, Any], output: Path, context: str = "20") -> None:
    models = [model for model in ("1.5b", "7b", "32b") if model in closure["results"]]
    fig, axes = plt.subplots(1, len(models), figsize=(7.05, 2.45), sharey=True, constrained_layout=True)
    axes = np.atleast_1d(axes)
    component_keys = ("per_step_cost", "competence", "information", "routing_mismatch")
    labels = ("Cost", "Competence", "Information", "Mismatch")
    colors = (COLORS["cost"], COLORS["competence"], COLORS["information"], COLORS["mismatch"])
    for axis, model in zip(axes, models, strict=True):
        row = closure["results"][model][context]
        values = [float(row[key]) for key in component_keys]
        values[-1] *= -1
        cumulative = 0.0
        for idx, (value, color) in enumerate(zip(values, colors, strict=True)):
            bottom = min(cumulative, cumulative + value)
            axis.bar(idx, abs(value), bottom=bottom, color=color, width=0.68)
            cumulative += value
            if idx < len(values) - 1:
                axis.plot([idx + 0.34, idx + 0.66], [cumulative, cumulative], color="#82909C", lw=0.7)
        observed = float(row["packed_observed_log_speedup"])
        low, high = row["packed_observed_95ci"]
        axis.errorbar(
            4,
            observed,
            yerr=[[observed - low], [high - observed]],
            fmt="o",
            color=COLORS["observed"],
            capsize=2.5,
            label="Observed",
        )
        axis.scatter([4], [row["predicted_log_speedup"]], marker="D", s=24, color=COLORS["predicted"], label="Predicted")
        axis.axhline(0, color="#52606D", lw=0.7)
        axis.set_xticks(range(5), (*labels, "Total"), rotation=28, ha="right")
        axis.set_title(MODEL_LABELS[model], fontweight="bold")
    axes[0].set_ylabel("Expected log-speedup (nats)")
    axes[-1].legend(frameon=False, loc="best")
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def plot_information_speed(closure: dict[str, Any], output: Path) -> None:
    contexts = [0, 5, 20]
    models = [model for model in ("1.5b", "7b", "32b") if model in closure["results"]]
    fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.45), constrained_layout=True)
    model_colors = {"1.5b": COLORS["mode1"], "7b": COLORS["mode2"], "32b": COLORS["mode3"]}
    for model in models:
        rows = closure["results"][model]
        information = [rows[str(n)]["information"] for n in contexts]
        mismatch = [rows[str(n)]["routing_mismatch"] for n in contexts]
        observed = [rows[str(n)]["packed_observed_log_speedup"] for n in contexts]
        predicted = [rows[str(n)]["predicted_log_speedup"] for n in contexts]
        axes[0].plot(contexts, information, marker="o", color=model_colors[model], label=f"{MODEL_LABELS[model]}: $G$")
        axes[0].plot(contexts, mismatch, marker="s", ls="--", color=model_colors[model], alpha=0.75, label=f"{MODEL_LABELS[model]}: $\\epsilon$")
        axes[1].plot(contexts, observed, marker="o", color=model_colors[model], label=f"{MODEL_LABELS[model]} observed")
        axes[1].plot(contexts, predicted, marker="D", ls="--", color=model_colors[model], alpha=0.75, label=f"{MODEL_LABELS[model]} predicted")
    for axis in axes:
        axis.set_xticks(contexts)
        axis.set_xlabel("In-context routing examples")
        axis.axhline(0, color="#82909C", lw=0.7)
        axis.grid(axis="y", color="#D9E2EC", lw=0.55)
    axes[0].set_ylabel("Information / mismatch (nats)")
    axes[0].set_title("Posterior information and allocation mismatch", fontweight="bold")
    axes[1].set_ylabel("Expected log-speedup (nats)")
    axes[1].set_title("Predicted and observed verified speed", fontweight="bold")
    axes[0].legend(frameon=False, ncol=2, fontsize=6.3)
    axes[1].legend(frameon=False, ncol=2, fontsize=6.3)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def plot_allocations(config: dict[str, Any], router_rows: list[dict[str, Any]], output: Path) -> None:
    strategies = list(config["strategies"])
    models = ["1.5b", "7b", "32b"]
    modes = ["easy", "medium", "hard"]
    colors = [COLORS["mode1"], COLORS["mode2"], COLORS["mode3"]]
    fig, axes = plt.subplots(1, 3, figsize=(7.05, 2.25), sharey=True, constrained_layout=True)
    for axis, model in zip(axes, models, strict=True):
        bottom = np.zeros(3)
        selected = [row for row in router_rows if row["model_key"] == model and row["context_examples"] == 20]
        for strategy, color in zip(strategies, colors, strict=True):
            values = np.asarray(
                [
                    np.mean([row["allocation"][strategy] for row in selected if row["true_mode"] == mode])
                    for mode in modes
                ]
            )
            axis.bar(range(3), values, bottom=bottom, color=color, width=0.72, label=STRATEGY_LABELS[strategy])
            bottom += values
        axis.set_title(MODEL_LABELS[model], fontweight="bold")
        axis.set_xticks(range(3), [MODE_LABELS[value] for value in modes])
        axis.set_xlabel("Held-out task mode")
    axes[0].set_ylabel("Mean allocated retries")
    axes[-1].legend(frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot the strategy-allocation experiment")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    configure_style()
    config = load_config(args.config)
    raw = Path(config["paths"]["raw"])
    derived = Path(config["paths"]["derived"])
    figures = Path(config["paths"]["figures"])
    figures.mkdir(parents=True, exist_ok=True)
    summary = load_json(derived / f"strategy_summary_{args.run_id}.json")
    closure = load_json(derived / f"four_term_closure_{args.run_id}.json")
    router_rows = [
        json.loads(line)
        for path in raw.glob("router_*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("run_id") == args.run_id
    ]
    plot_specialization(summary, figures / "strategy_specialization.pdf")
    plot_accounting(closure, figures / "four_term_accounting.pdf")
    plot_information_speed(closure, figures / "information_speed_curve.pdf")
    plot_allocations(config, router_rows, figures / "router_allocations.pdf")
    print(f"Wrote figures to {figures}")


if __name__ == "__main__":
    main()
