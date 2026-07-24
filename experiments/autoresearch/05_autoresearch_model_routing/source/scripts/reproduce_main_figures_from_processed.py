"""Reproduce main paper figures from processed three-worker analysis JSON.

This script is designed for the anonymous review artifact: it does not require
raw trajectory logs, provider-auth material, execution-environment paths, or the
development repository history.  It consumes ``results/threeworker_final_analysis.json`` and regenerates
compact figures used by the paper-facing analysis.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MODES = ["cnn_compact", "mlp_flat", "resnet_micro"]
MODE_LABELS = {"cnn_compact": "CNN", "mlp_flat": "MLP", "resnet_micro": "ResNet"}
WORKERS = ["gpt_5_3_codex", "gpt_5_4", "gpt_5_4_mini"]
WORKER_LABELS = {
    "gpt_5_3_codex": "Codex",
    "gpt_5_4": "GPT-5.4",
    "gpt_5_4_mini": "GPT-5.4 Mini",
}
WORKER_COLORS = {
    "gpt_5_3_codex": "#1f4e79",
    "gpt_5_4": "#d95f02",
    "gpt_5_4_mini": "#54A24B",
}
REAL_CONTROL = {"real", "none", None, ""}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(fig: plt.Figure, out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_dir / f"{name}.png", dpi=220, bbox_inches="tight")
    fig.savefig(out_dir / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def frontier_by_cell(frontier: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["mode"], row["worker"]): row for row in frontier}


def ci_error(ci: dict[str, float | None]) -> tuple[float, float]:
    mean = float(ci["mean"])
    lo = mean - float(ci["lo"])
    hi = float(ci["hi"]) - mean
    return max(lo, 0.0), max(hi, 0.0)


def plot_worker_frontier(report: dict[str, Any], out_dir: Path) -> None:
    frontier = frontier_by_cell(report["frontier"])
    x = np.arange(len(MODES))
    width = 0.24
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.3))

    for idx, worker in enumerate(WORKERS):
        offset = (idx - (len(WORKERS) - 1) / 2.0) * width
        rows = [frontier[(mode, worker)] for mode in MODES]

        losses = [float(row["deployment_loss_ci"]["mean"]) for row in rows]
        yerr = np.array([ci_error(row["deployment_loss_ci"]) for row in rows]).T
        axes[0].bar(
            x + offset,
            losses,
            width,
            yerr=yerr,
            capsize=2,
            label=WORKER_LABELS[worker],
            color=WORKER_COLORS[worker],
            alpha=0.86,
        )

        axes[1].bar(
            x + offset,
            [float(row["log_effort_objective"]) for row in rows],
            width,
            color=WORKER_COLORS[worker],
            alpha=0.86,
        )

        axes[2].bar(
            x + offset,
            [float(row["mean_final_relative_improvement"]) for row in rows],
            width,
            color=WORKER_COLORS[worker],
            alpha=0.86,
        )

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
        ax.grid(axis="x", visible=False)
    axes[0].set_title("Deployment loss")
    axes[0].set_ylabel("lower is better")
    axes[1].set_title("Log-effort")
    axes[1].set_ylabel("lower is better")
    axes[2].set_title("Final improvement")
    axes[2].set_ylabel("relative improvement")
    axes[0].legend(frameon=False, loc="upper left")
    save(fig, out_dir, "fig_worker_frontier_compact")


def plot_router_validation(report: dict[str, Any], out_dir: Path) -> None:
    router = report["router"]
    rows = router["rows"]
    selection_summary = router["selection_summary"]
    gain_summary = router["gain_summary"]
    frontier = frontier_by_cell(report["frontier"])

    fig, axes = plt.subplots(1, 4, figsize=(14.0, 3.2))

    # Panel A: mode diagnosis availability, reported from frozen signal audit.
    signal_names = ["Budget", "Probe", "Probe+budget", "Full"]
    signal_acc = [0.349, 1.0, 1.0, 1.0]
    axes[0].bar(signal_names, signal_acc, color=["#bdbdbd", "#2a6fdb", "#2a6fdb", "#2a6fdb"])
    axes[0].set_ylim(0.0, 1.05)
    axes[0].set_title("Signal mode audit")
    axes[0].set_ylabel("accuracy")
    axes[0].tick_params(axis="x", rotation=25)

    # Panel B: selected-worker share on real records.
    real_rows = [row for row in rows if row.get("control") in REAL_CONTROL]
    signals = ["Z0", "Z1", "Z2", "Z3"]
    bottom = np.zeros(len(signals))
    for worker in WORKERS:
        shares = []
        for signal in signals:
            cell = [row for row in real_rows if row["signal"] == signal]
            count = sum(1 for row in cell if row["worker"] == worker)
            shares.append(count / len(cell) if cell else 0.0)
        axes[1].bar(signals, shares, bottom=bottom, color=WORKER_COLORS[worker], label=WORKER_LABELS[worker])
        bottom += np.array(shares)
    axes[1].set_ylim(0.0, 1.05)
    axes[1].set_title("Router allocation")
    axes[1].set_ylabel("selected-worker share")
    axes[1].legend(frameon=False, fontsize=7)

    # Panel C: paired net deployment gain for real signals.
    real_gains = [row for row in gain_summary if row.get("control") in REAL_CONTROL and row["signal"] != "Z0"]
    real_gains.sort(key=lambda row: row["signal"])
    labels = [row["signal"] for row in real_gains]
    means = [float(row["net_gain_ci"]["mean"]) for row in real_gains]
    yerr = np.array([ci_error(row["net_gain_ci"]) for row in real_gains]).T
    axes[2].axhline(0.0, color="#222222", linewidth=0.9)
    axes[2].bar(labels, means, yerr=yerr, capsize=2, color="#2a6fdb", alpha=0.88)
    axes[2].set_title("Paired gain")
    axes[2].set_ylabel("net gain vs Z0")

    # Panel D: policy/oracle deployment-loss gap.
    mode_worker_loss = {
        (mode, worker): float(frontier[(mode, worker)]["deployment_loss_ci"]["mean"])
        for mode in MODES
        for worker in WORKERS
    }
    z0_rows = [row for row in real_rows if row["signal"] == "Z0"]
    policies: list[tuple[str, float, str]] = []
    for worker in WORKERS:
        values = [mode_worker_loss[(row["mode"], worker)] for row in z0_rows]
        policies.append((f"always\n{WORKER_LABELS[worker]}", float(np.mean(values)), "#bdbdbd"))
    for signal in signals:
        values = [
            mode_worker_loss[(row["mode"], row["worker"])] + float(row["measurement_loss"])
            for row in real_rows
            if row["signal"] == signal
        ]
        policies.append((signal, float(np.mean(values)), "#7aa6c2"))
    oracle_values = [min(mode_worker_loss[(row["mode"], worker)] for worker in WORKERS) for row in z0_rows]
    policies.append(("oracle\nmode", float(np.mean(oracle_values)), "#111111"))
    px = np.arange(len(policies))
    axes[3].bar(px, [value for _, value, _ in policies], color=[color for _, _, color in policies])
    axes[3].set_xticks(px)
    axes[3].set_xticklabels([label for label, _, _ in policies], rotation=30, ha="right", fontsize=7)
    axes[3].set_title("Oracle gap")
    axes[3].set_ylabel("deployment loss")

    save(fig, out_dir, "fig_router_validation_compact")


def plot_negative_controls(report: dict[str, Any], out_dir: Path) -> None:
    controls = [
        row
        for row in report["router"]["gain_summary"]
        if row.get("control") not in REAL_CONTROL and row["signal"] != "Z0"
    ]
    controls.sort(key=lambda row: (row["signal"], row["control"]))
    if not controls:
        return
    fig, ax = plt.subplots(figsize=(10.0, 3.4))
    labels = [f'{row["signal"]}\n{row["control"].replace("_", " ")}' for row in controls]
    means = [float(row["net_gain_ci"]["mean"]) for row in controls]
    ax.axhline(0.0, color="#222222", linewidth=0.9)
    ax.bar(np.arange(len(labels)), means, color="#8f8f8f")
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
    ax.set_ylabel("paired net deployment gain")
    ax.set_title("Negative-control signal checks")
    save(fig, out_dir, "fig_negative_controls")


def write_summary(report: dict[str, Any], out_dir: Path) -> None:
    support = Counter((row["mode"], row["worker"]) for row in report["frontier"])
    lines = [
        "# Reproduced Figures",
        "",
        f"Threshold: `{report.get('threshold')}`",
        f"Analysis label: `{report.get('analysis_label')}`",
        f"Frozen run count: `{report.get('frozen_run_count')}`",
        "",
        "Generated files:",
        "- `fig_worker_frontier_compact.{png,pdf}`",
        "- `fig_router_validation_compact.{png,pdf}`",
        "- `fig_negative_controls.{png,pdf}`",
        "",
        "Frontier cells:",
    ]
    for mode, worker in sorted(support):
        lines.append(f"- `{mode}/{worker}`")
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="results/threeworker_final_analysis.json")
    parser.add_argument("--out-dir", default="figures/reproduced")
    args = parser.parse_args()

    report = load_json(Path(args.input))
    out_dir = Path(args.out_dir)
    plt.style.use("seaborn-v0_8-whitegrid")
    plot_worker_frontier(report, out_dir)
    plot_router_validation(report, out_dir)
    plot_negative_controls(report, out_dir)
    write_summary(report, out_dir)
    print(json.dumps({"output_dir": str(out_dir), "figures": 3}, indent=2))


if __name__ == "__main__":
    main()
