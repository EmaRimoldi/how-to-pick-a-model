"""Generate certified-resource figures for the AutoResearch paper."""

from __future__ import annotations

import argparse
import importlib.util
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap


GAMMA = 0.05
DELTAS = [0.05, 0.10, 0.15, 0.20, 0.25]
MODE_POLICY = {
    "mlp_flat": "gpt_5_4",
    "cnn_compact": "gpt_5_4_mini",
    "resnet_micro": "gpt_5_3_codex",
}
ALWAYS_POLICY = "gpt_5_4"
LAMBDA_WALL = 1.0 / 1800.0


def load_analysis_module(repo_root: Path):
    path = repo_root / "scripts" / "analyze_autoresearch_threeworker_final.py"
    spec = importlib.util.spec_from_file_location("threeworker_analysis", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def mode_worker_kappa(rows: list[dict]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for mode in {row["mode"] for row in rows}:
        for worker in {row["worker"] for row in rows}:
            per_step = [
                float(row["elapsed_wall_seconds"]) / max(int(row["steps_completed"]), 1)
                for row in rows
                if row["mode"] == mode and row["worker"] == worker and float(row.get("elapsed_wall_seconds") or 0.0) > 0.0
            ]
            out[(mode, worker)] = float(np.median(per_step)) if per_step else math.inf
    return out


def first_hit_cost(analysis, row: dict, kappa: dict[tuple[str, str], float], gamma: float = GAMMA) -> float:
    tau = analysis.first_hit_step(row["baseline_loss"], row["best_losses_by_step"], gamma)
    if tau is None:
        return math.inf
    return LAMBDA_WALL * kappa[(row["mode"], row["worker"])] * float(tau)


def worker_kappa(rows: list[dict]) -> dict[str, float]:
    """Legacy helper retained for ad hoc comparisons outside the main figure."""
    out = {}
    for worker in {row["worker"] for row in rows}:
        per_step = [
            float(row["elapsed_wall_seconds"]) / max(int(row["steps_completed"]), 1)
            for row in rows
            if row["worker"] == worker and float(row.get("elapsed_wall_seconds") or 0.0) > 0.0
        ]
        out[worker] = float(np.median(per_step)) if per_step else math.inf
    return out


def empirical_t(costs: list[float], delta: float) -> float:
    xs = sorted(costs)
    if not xs:
        return math.inf
    k = math.ceil((1.0 - delta) * len(xs))
    return xs[k - 1]


def weighted_t(costs_by_mode: dict[str, list[float]], weights: dict[str, float], delta: float) -> float:
    grid = sorted({value for values in costs_by_mode.values() for value in values if math.isfinite(value)})
    if not grid:
        return math.inf
    target = 1.0 - delta
    for budget in grid:
        covered = 0.0
        for mode, costs in costs_by_mode.items():
            covered += weights[mode] * sum(value <= budget for value in costs) / len(costs)
        if covered >= target:
            return budget
    return math.inf


def save(fig: plt.Figure, out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.png", dpi=260, bbox_inches="tight")
    fig.savefig(out_dir / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def label(analysis, worker: str) -> str:
    return analysis.WORKER_LABELS[worker].replace("GPT-", "GPT ")


def style() -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.fontsize": 8.5,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#e8e8e8",
            "grid.linewidth": 0.8,
        }
    )


def rows_for_policy(rows: list[dict], policy: str | dict[str, str]) -> list[dict]:
    if isinstance(policy, str):
        return [row for row in rows if row["worker"] == policy]
    return [row for row in rows if row["worker"] == policy[row["mode"]]]


def costs_by_mode_for_policy(analysis, rows: list[dict], kappa: dict[tuple[str, str], float], policy: str | dict[str, str]) -> dict[str, list[float]]:
    out = {}
    for mode in analysis.MODES:
        worker = policy if isinstance(policy, str) else policy[mode]
        out[mode] = [first_hit_cost(analysis, row, kappa) for row in rows if row["mode"] == mode and row["worker"] == worker]
    return out


def plot_speedup_curve(analysis, rows: list[dict], kappa: dict[tuple[str, str], float], out_dir: Path) -> None:
    mode_costs = [first_hit_cost(analysis, row, kappa) for row in rows_for_policy(rows, MODE_POLICY)]
    always_costs = [first_hit_cost(analysis, row, kappa) for row in rows_for_policy(rows, ALWAYS_POLICY)]
    mode_t = [empirical_t(mode_costs, delta) for delta in DELTAS]
    always_t = [empirical_t(always_costs, delta) for delta in DELTAS]
    speedup = [base / mode for base, mode in zip(always_t, mode_t)]

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.axhline(1.0, color="#6b7280", linewidth=1.2, linestyle="--")
    ax.fill_between(DELTAS, 1.0, speedup, color="#c7f0d4", alpha=0.7)
    ax.plot(DELTAS, speedup, color="#12733d", marker="o", linewidth=2.6, markersize=6)
    for x, y in zip(DELTAS, speedup):
        ax.text(x, y + 0.035, f"{y:.2f}x", ha="center", va="bottom", fontsize=9, color="#0f5132")
    ax.set_xlabel(r"certification tolerance $\delta_{\mathrm{cert}}$")
    ax.set_ylabel("certified speedup")
    ax.set_title("Mode-conditioned orchestration under the formula clock")
    ax.set_xticks(DELTAS)
    ax.set_ylim(0.95, max(speedup) + 0.22)
    ax.text(
        DELTAS[-1],
        1.025,
        "no speedup",
        ha="right",
        va="bottom",
        fontsize=8.5,
        color="#6b7280",
    )
    save(fig, out_dir, "certified_speedup_curve")


def plot_resource_heatmap(analysis, rows: list[dict], kappa: dict[tuple[str, str], float], out_dir: Path) -> None:
    delta = 0.10
    matrix = np.zeros((len(analysis.MODES), len(analysis.WORKERS)))
    for i, mode in enumerate(analysis.MODES):
        for j, worker in enumerate(analysis.WORKERS):
            costs = [first_hit_cost(analysis, row, kappa) for row in rows if row["mode"] == mode and row["worker"] == worker]
            matrix[i, j] = empirical_t(costs, delta)

    cmap = LinearSegmentedColormap.from_list("resource", ["#1f7a4d", "#f5d76e", "#b73239"])
    fig, ax = plt.subplots(figsize=(6.6, 3.7))
    image = ax.imshow(matrix, cmap=cmap, aspect="auto")
    ax.set_xticks(np.arange(len(analysis.WORKERS)))
    ax.set_xticklabels([label(analysis, w) for w in analysis.WORKERS], rotation=18, ha="right")
    ax.set_yticks(np.arange(len(analysis.MODES)))
    ax.set_yticklabels([analysis.MODE_LABELS[m] for m in analysis.MODES])
    ax.set_title(r"Factored certified time, $\gamma=0.05$, $\delta_{\mathrm{cert}}=0.10$")
    ax.grid(False)
    for i in range(matrix.shape[0]):
        best_j = int(np.argmin(matrix[i]))
        for j in range(matrix.shape[1]):
            color = "white" if matrix[i, j] > np.nanmean(matrix) else "#111827"
            suffix = " *" if j == best_j else ""
            ax.text(j, i, f"{matrix[i, j]:.3f}{suffix}", ha="center", va="center", color=color, fontweight="bold" if j == best_j else "normal")
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("lower is better")
    save(fig, out_dir, "certified_resource_heatmap")


def certified_speedup_values(analysis, rows: list[dict], kappa: dict[tuple[str, str], float]) -> tuple[list[float], list[float], list[float]]:
    mode_costs = [first_hit_cost(analysis, row, kappa) for row in rows_for_policy(rows, MODE_POLICY)]
    always_costs = [first_hit_cost(analysis, row, kappa) for row in rows_for_policy(rows, ALWAYS_POLICY)]
    mode_t = [empirical_t(mode_costs, delta) for delta in DELTAS]
    always_t = [empirical_t(always_costs, delta) for delta in DELTAS]
    speedup = [base / mode for base, mode in zip(always_t, mode_t)]
    return mode_t, always_t, speedup


def certified_resource_matrix(analysis, rows: list[dict], kappa: dict[tuple[str, str], float], delta: float = 0.10) -> np.ndarray:
    matrix = np.zeros((len(analysis.MODES), len(analysis.WORKERS)))
    for i, mode in enumerate(analysis.MODES):
        for j, worker in enumerate(analysis.WORKERS):
            costs = [first_hit_cost(analysis, row, kappa) for row in rows if row["mode"] == mode and row["worker"] == worker]
            matrix[i, j] = empirical_t(costs, delta)
    return matrix


def plot_unified_summary(analysis, rows: list[dict], kappa: dict[tuple[str, str], float], out_dir: Path) -> None:
    _, _, speedup = certified_speedup_values(analysis, rows, kappa)

    fig, ax_s = plt.subplots(figsize=(6.4, 3.15))
    ax_s.axhline(1.0, color="#94a3b8", linewidth=1.2, linestyle="--")
    ax_s.fill_between(DELTAS, 1.0, speedup, color="#dcfce7", alpha=0.65)
    ax_s.plot(DELTAS, speedup, color="#0f5132", marker="o", linewidth=2.3, markersize=5.8)
    for x, y in zip(DELTAS, speedup):
        va = "bottom" if y >= 1.0 else "top"
        offset = 0.025 if y >= 1.0 else -0.025
        ax_s.text(x, y + offset, f"{y:.2f}x", ha="center", va=va, fontsize=8.5, color="#0f5132")
    ax_s.set_title("Mode-conditioned certified-time ratio", loc="left", fontweight="bold")
    ax_s.set_xlabel(r"certification tolerance $\delta_{\mathrm{cert}}$")
    ax_s.set_ylabel("speedup vs always GPT 5.4")
    ax_s.set_xticks(DELTAS)
    ax_s.set_ylim(min(0.85, min(speedup) - 0.06), max(speedup) + 0.12)
    ax_s.text(
        DELTAS[-1],
        1.015,
        "baseline",
        ha="right",
        va="bottom",
        fontsize=8,
        color="#64748b",
    )
    fig.tight_layout()
    save(fig, out_dir, "certified_resource_summary_unified")


def plot_quality_resource_scatter(analysis, rows: list[dict], kappa: dict[tuple[str, str], float], out_dir: Path) -> None:
    markers = {"mlp_flat": "o", "cnn_compact": "s", "resnet_micro": "^"}
    fig, ax = plt.subplots(figsize=(6.5, 4.1))
    for mode in analysis.MODES:
        for worker in analysis.WORKERS:
            cell = [row for row in rows if row["mode"] == mode and row["worker"] == worker]
            costs = [first_hit_cost(analysis, row, kappa) for row in cell]
            t_value = empirical_t(costs, 0.10)
            final_loss = sum(row["final_loss"] for row in cell) / len(cell)
            is_frontier = MODE_POLICY[mode] == worker
            ax.scatter(
                final_loss,
                t_value,
                s=135 if is_frontier else 82,
                marker=markers[mode],
                color=analysis.WORKER_COLORS[worker],
                edgecolor="#111827" if is_frontier else "white",
                linewidth=1.5,
                alpha=0.95,
                label=f"{label(analysis, worker)} / {analysis.MODE_LABELS[mode]}",
            )
            ax.text(final_loss + 0.006, t_value + 0.006, analysis.MODE_LABELS[mode], fontsize=8, color="#374151")
    ax.annotate(
        "better",
        xy=(0.985, 0.155),
        xytext=(1.085, 0.31),
        arrowprops={"arrowstyle": "->", "color": "#111827", "lw": 1.4},
        fontsize=9,
        color="#111827",
    )
    ax.set_xlabel("mean final validation loss")
    ax.set_ylabel(r"$\widehat T_{\delta}$ at $\delta_{\mathrm{cert}}=0.10$")
    ax.set_title("Final quality and certified resource disagree")
    handles = []
    labels = []
    for worker in analysis.WORKERS:
        handles.append(plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=analysis.WORKER_COLORS[worker], markersize=8))
        labels.append(label(analysis, worker))
    ax.legend(handles, labels, loc="upper right", frameon=True)
    save(fig, out_dir, "quality_vs_certified_resource")


def plot_first_hit_ecdf(analysis, rows: list[dict], kappa: dict[tuple[str, str], float], out_dir: Path) -> None:
    fig, axes = plt.subplots(1, len(analysis.MODES), figsize=(12.3, 3.7), sharey=True)
    target = 0.90
    for ax, mode in zip(axes, analysis.MODES):
        for worker in analysis.WORKERS:
            costs = sorted(first_hit_cost(analysis, row, kappa) for row in rows if row["mode"] == mode and row["worker"] == worker)
            finite = [value for value in costs if math.isfinite(value)]
            if not finite:
                continue
            y = [sum(value <= x for value in costs) / len(costs) for x in finite]
            ax.step(finite, y, where="post", linewidth=2.2, color=analysis.WORKER_COLORS[worker], label=label(analysis, worker))
            t_value = empirical_t(costs, 0.10)
            if math.isfinite(t_value) and worker == MODE_POLICY[mode]:
                ax.axvline(t_value, color=analysis.WORKER_COLORS[worker], linestyle=":", linewidth=1.5)
        ax.axhline(target, color="#111827", linestyle="--", linewidth=1.0)
        ax.set_title(analysis.MODE_LABELS[mode])
        ax.set_xlabel("normalized resource")
        ax.set_ylim(0.0, 1.03)
    axes[0].set_ylabel("fraction successful by budget")
    axes[-1].legend(loc="lower right", frameon=True)
    fig.suptitle(r"Empirical success-by-budget curves at $\gamma=0.05$", y=1.03, fontsize=13)
    save(fig, out_dir, "first_hit_ecdf_by_mode")


def plot_deployment_mix_sensitivity(analysis, rows: list[dict], kappa: dict[tuple[str, str], float], out_dir: Path) -> None:
    mode_costs = costs_by_mode_for_policy(analysis, rows, kappa, MODE_POLICY)
    always_costs = costs_by_mode_for_policy(analysis, rows, kappa, ALWAYS_POLICY)
    xs = np.linspace(1.0 / 3.0, 1.0, 80)
    fig, axes = plt.subplots(1, len(analysis.MODES), figsize=(12.1, 3.6), sharey=True)
    for ax, dominant_mode in zip(axes, analysis.MODES):
        speedups = []
        for share in xs:
            weights = {}
            rest = (1.0 - share) / 2.0
            for mode in analysis.MODES:
                weights[mode] = share if mode == dominant_mode else rest
            t_mode = weighted_t(mode_costs, weights, 0.10)
            t_always = weighted_t(always_costs, weights, 0.10)
            speedups.append(t_always / t_mode if math.isfinite(t_mode) and math.isfinite(t_always) else math.nan)
        ax.axhline(1.0, color="#6b7280", linewidth=1.0, linestyle="--")
        ax.plot(xs, speedups, color="#2563eb", linewidth=2.4)
        ax.fill_between(xs, 1.0, speedups, where=np.array(speedups) >= 1.0, color="#dbeafe", alpha=0.9)
        ax.set_title(f"{analysis.MODE_LABELS[dominant_mode]}-heavy deployment")
        ax.set_xlabel(f"share of {analysis.MODE_LABELS[dominant_mode]}")
        ax.set_ylim(0.95, max(np.nanmax(speedups), 1.05) + 0.15)
    axes[0].set_ylabel("speedup vs always GPT 5.4")
    fig.suptitle(r"Deployment-mix sensitivity, $\gamma=0.05$, $\delta_{\mathrm{cert}}=0.10$", y=1.03, fontsize=13)
    save(fig, out_dir, "deployment_mix_sensitivity")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", default="autoresearch/campaigns/h20_delta005_20260505")
    parser.add_argument("--out-dir", default="autoresearch/paper_figures/current")
    parser.add_argument("--total-per-cell", type=int, default=30)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    analysis = load_analysis_module(repo_root)
    rows, _ = analysis.load_pooled_runs(
        Path(args.campaign_root),
        pilot_per_cell=10,
        holdout_per_cell=25,
        total_per_cell=args.total_per_cell,
    )
    out_dir = Path(args.out_dir)
    kappa = mode_worker_kappa(rows)
    style()
    plot_unified_summary(analysis, rows, kappa, out_dir)
    plot_speedup_curve(analysis, rows, kappa, out_dir)
    plot_resource_heatmap(analysis, rows, kappa, out_dir)
    plot_quality_resource_scatter(analysis, rows, kappa, out_dir)
    plot_first_hit_ecdf(analysis, rows, kappa, out_dir)
    plot_deployment_mix_sensitivity(analysis, rows, kappa, out_dir)


if __name__ == "__main__":
    main()
