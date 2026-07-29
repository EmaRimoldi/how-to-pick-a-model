from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from scipy.stats import gaussian_kde


COLORS = {
    "1.5b": "#0B6E69",
    "7b": "#4C5B9B",
    "32b": "#E76F51",
    "router": "#D49B22",
    "oracle": "#273043",
    "stat_oracle": "#7A7F87",
    "grid": "#D8DCE2",
    "text": "#20242A",
}

LABELS = {
    "always_1.5b": "Qwen 1.5B",
    "always_7b": "Qwen 7B",
    "always_32b": "Qwen 32B",
    "router": "Router",
    "oracle": "Oracle",
    "stat_oracle": "Stat. oracle",
}

MODE_LABELS = {"easy": "Mode 1", "medium": "Mode 2", "hard": "Mode 3"}


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 8.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.5,
            "axes.edgecolor": COLORS["text"],
            "axes.labelcolor": COLORS["text"],
            "text.color": COLORS["text"],
            "xtick.color": COLORS["text"],
            "ytick.color": COLORS["text"],
            "axes.linewidth": 0.7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def save(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(output_dir / f"{stem}.png", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def clean_axis(ax: plt.Axes, *, grid_axis: str = "both") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, color=COLORS["grid"], linewidth=0.55, alpha=0.75)
    ax.set_axisbelow(True)


def plot_speed_accounting(summary: dict[str, Any], output_dir: Path) -> None:
    fig, (ax_tradeoff, ax_speed) = plt.subplots(
        1,
        2,
        figsize=(7.05, 2.72),
        gridspec_kw={"width_ratios": [1.08, 0.92], "wspace": 0.42},
    )

    methods = ["always_1.5b", "always_7b", "always_32b", "router", "oracle"]
    markers = {
        "always_1.5b": "o",
        "always_7b": "s",
        "always_32b": "^",
        "router": "D",
        "oracle": "*",
    }
    method_colors = {
        "always_1.5b": COLORS["1.5b"],
        "always_7b": COLORS["7b"],
        "always_32b": COLORS["32b"],
        "router": COLORS["router"],
        "oracle": COLORS["oracle"],
    }
    offsets = {
        "always_1.5b": (5, -2),
        "always_7b": (7, 13),
        "always_32b": (-7, 6),
        "router": (5, -10),
        "oracle": (5, 5),
    }
    aligns = {"always_32b": "right"}

    for method in methods:
        values = summary["methods"][method]
        x = float(values["mean_time_all"])
        y = 100.0 * float(values["solved_rate"])
        ax_tradeoff.scatter(
            x,
            y,
            s=62 if method != "oracle" else 86,
            marker=markers[method],
            color=method_colors[method],
            edgecolor="white",
            linewidth=0.7,
            zorder=3,
        )
        ax_tradeoff.annotate(
            LABELS[method],
            (x, y),
            xytext=offsets[method],
            textcoords="offset points",
            ha=aligns.get(method, "left"),
            va="center",
        )

    base = summary["methods"]["always_7b"]
    router = summary["methods"]["router"]
    reduction = 100.0 * (
        float(base["mean_time_all"]) - float(router["mean_time_all"])
    ) / float(base["mean_time_all"])
    base_point = (float(base["mean_time_all"]), 100.0 * float(base["solved_rate"]))
    router_point = (float(router["mean_time_all"]), 100.0 * float(router["solved_rate"]))
    ax_tradeoff.annotate(
        "",
        xy=router_point,
        xytext=base_point,
        arrowprops={"arrowstyle": "->", "color": COLORS["router"], "lw": 1.15},
    )
    ax_tradeoff.text(
        5.0,
        89.4,
        f"{reduction:.0f}% lower time",
        ha="left",
        va="center",
        fontsize=7.5,
    )
    ax_tradeoff.set_xscale("log")
    ax_tradeoff.set_xlim(0.75, 75)
    ax_tradeoff.set_ylim(79, 96)
    ax_tradeoff.set_xlabel("Mean verified first-hit time (s, log scale)")
    ax_tradeoff.set_ylabel("Solved within 10 attempts (%)")
    ax_tradeoff.set_title("a  Speed--reliability plane", loc="left")
    clean_axis(ax_tradeoff)

    entries = [("Overall", summary["time_saved_vs_best_single"])]
    entries.extend(
        (MODE_LABELS[mode], summary["by_mode"][mode]["time_saved_vs_best_single"])
        for mode in ["easy", "medium", "hard"]
    )
    labels = [label for label, _ in entries]
    means = np.array([float(entry["mean"]) for _, entry in entries])
    lows = np.array([float(entry["ci95"]["lo"]) for _, entry in entries])
    highs = np.array([float(entry["ci95"]["hi"]) for _, entry in entries])
    y = np.arange(len(entries))
    bar_colors = [COLORS["router"], COLORS["1.5b"], COLORS["7b"], COLORS["32b"]]
    ax_speed.barh(y, means, height=0.54, color=bar_colors, alpha=0.94, zorder=2)
    ax_speed.errorbar(
        means,
        y,
        xerr=np.vstack([means - lows, highs - means]),
        fmt="none",
        ecolor=COLORS["text"],
        elinewidth=0.8,
        capsize=2.4,
        capthick=0.8,
        zorder=3,
    )
    ax_speed.axvline(0, color=COLORS["text"], linewidth=0.75)
    for yi, mean in zip(y, means):
        ax_speed.text(
            mean - 0.16,
            yi,
            f"{mean:.2f}",
            ha="right",
            va="center",
            fontsize=7.2,
            color="white",
            fontweight="bold",
        )
    ax_speed.set_yticks(y, labels)
    ax_speed.invert_yaxis()
    ax_speed.set_xlim(min(-7.2, lows.min() - 0.5), highs.max() + 1.1)
    ax_speed.set_xlabel("Seconds saved vs. best single model")
    ax_speed.set_title("b  Paired routing gain", loc="left")
    clean_axis(ax_speed, grid_axis="x")

    save(fig, output_dir, "humaneval_speed_accounting")


def first_pass_index(statuses: list[str]) -> int | None:
    for idx, status in enumerate(statuses, start=1):
        if status == "pass":
            return idx
    return None


def plot_retry_and_frontier(
    raw_paths: dict[str, Path],
    tau: dict[str, Any],
    output_dir: Path,
) -> None:
    fig, (ax_retry, ax_heat) = plt.subplots(
        1,
        2,
        figsize=(7.05, 2.72),
        gridspec_kw={"width_ratios": [1.12, 0.88], "wspace": 0.38},
    )

    attempts = np.arange(1, 11)
    for short_name in ["1.5b", "7b", "32b"]:
        rows = read_jsonl(raw_paths[short_name])
        first_passes = [first_pass_index(row["attempt_statuses"]) for row in rows]
        success = np.array(
            [100.0 * np.mean([fp is not None and fp <= depth for fp in first_passes]) for depth in attempts]
        )
        ax_retry.plot(
            attempts,
            success,
            color=COLORS[short_name],
            marker={"1.5b": "o", "7b": "s", "32b": "^"}[short_name],
            markersize=3.4,
            linewidth=1.55,
            label=f"Qwen {short_name.upper()}",
        )
    ax_retry.set_xlim(1, 10)
    ax_retry.set_ylim(15, 95)
    ax_retry.set_xticks([1, 2, 4, 6, 8, 10])
    ax_retry.set_xlabel("Retry depth")
    ax_retry.set_ylabel("Verified success by depth (%)")
    ax_retry.set_title("a  Verified success across retries", loc="left")
    ax_retry.legend(frameon=False, loc="lower right", handlelength=2.2)
    clean_axis(ax_retry)

    modes = ["easy", "medium", "hard"]
    models = ["1.5b", "7b", "32b"]
    model_ids = {
        "1.5b": "qwen2.5-coder:1.5b",
        "7b": "qwen2.5-coder:7b",
        "32b": "qwen2.5-coder:32b",
    }
    values = np.array(
        [[float(tau[f"{model_ids[model]}|{mode}"]["tau_star"]) for model in models] for mode in modes]
    )
    cmap = LinearSegmentedColormap.from_list(
        "paper_effort", ["#F4F1DE", "#E9C46A", "#0B6E69"]
    )
    image = ax_heat.imshow(values, cmap=cmap, aspect="auto")
    for row, mode in enumerate(modes):
        winner = int(np.argmin(values[row]))
        for col, value in enumerate(values[row]):
            normalized = (value - values.min()) / max(1.0, values.max() - values.min())
            color = "white" if normalized > 0.58 else COLORS["text"]
            weight = "bold" if col == winner else "normal"
            marker = "\u25cf " if col == winner else ""
            ax_heat.text(
                col,
                row,
                f"{marker}{value:.0f}",
                ha="center",
                va="center",
                color=color,
                fontweight=weight,
                fontsize=8,
            )
    ax_heat.set_xticks(np.arange(len(models)), [f"Qwen {model.upper()}" for model in models])
    ax_heat.set_yticks(np.arange(len(modes)), [MODE_LABELS[mode] for mode in modes])
    ax_heat.set_xlabel("Model")
    ax_heat.set_ylabel("Task stratum")
    ax_heat.set_title("b  Conditional proper-time frontier", loc="left")
    for spine in ax_heat.spines.values():
        spine.set_visible(False)
    ax_heat.tick_params(length=0)
    colorbar = fig.colorbar(image, ax=ax_heat, fraction=0.046, pad=0.035)
    colorbar.set_label(r"Proper time $\tau^*$ (tokens)")
    colorbar.outline.set_linewidth(0.5)

    save(fig, output_dir, "humaneval_retry_frontier")


def operational_log_time(result: dict[str, Any], *, p_min: float = 0.05) -> float:
    seconds = max(float(result["time_seconds"]), 1.0e-4)
    return math.log(seconds) - (0.0 if result["solved"] else math.log(p_min))


def bootstrap_relative_indices(
    records: list[dict[str, Any]],
    *,
    B: int = 1000,
    seed: int = 23,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = len(records)
    time_index = np.empty(B, dtype=float)
    accuracy_index = np.empty(B, dtype=float)
    for idx in range(B):
        sample = [records[int(i)] for i in rng.integers(0, n, size=n)]
        base_time = np.mean([float(row["best_single"]["time_seconds"]) for row in sample])
        routed_time = np.mean([float(row["router"]["time_seconds"]) for row in sample])
        base_accuracy = np.mean([bool(row["best_single"]["solved"]) for row in sample])
        routed_accuracy = np.mean([bool(row["router"]["solved"]) for row in sample])
        time_index[idx] = 100.0 * routed_time / max(base_time, 1.0e-8)
        accuracy_index[idx] = 100.0 * routed_accuracy / max(base_accuracy, 1.0e-8)
    return time_index, accuracy_index


def half_violin(
    ax: plt.Axes,
    data: list[np.ndarray],
    positions: np.ndarray,
    colors: list[str],
) -> None:
    violins = ax.violinplot(
        data,
        positions=positions,
        widths=0.76,
        showextrema=False,
        orientation="horizontal",
    )
    for body, color in zip(violins["bodies"], colors):
        body.set_facecolor(color)
        body.set_edgecolor("none")
        body.set_alpha(0.24)
        vertices = body.get_paths()[0].vertices
        center = float(np.mean(vertices[:, 1]))
        vertices[:, 1] = np.maximum(vertices[:, 1], center)


def plot_information_speed_effect(
    records: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    fig, (ax_effect, ax_dist) = plt.subplots(
        1,
        2,
        figsize=(7.15, 3.15),
        gridspec_kw={"width_ratios": [0.78, 1.42], "wspace": 0.34},
    )

    base_time = float(np.mean([row["best_single"]["time_seconds"] for row in records]))
    routed_time = float(np.mean([row["router"]["time_seconds"] for row in records]))
    base_accuracy = float(np.mean([row["best_single"]["solved"] for row in records]))
    routed_accuracy = float(np.mean([row["router"]["solved"] for row in records]))
    time_endpoint = 100.0 * routed_time / base_time
    accuracy_endpoint = 100.0 * routed_accuracy / base_accuracy
    time_gain = 100.0 - time_endpoint
    accuracy_loss = 100.0 - accuracy_endpoint
    effect_ratio = time_gain / max(accuracy_loss, 1.0e-8)
    time_boot, accuracy_boot = bootstrap_relative_indices(records)

    x = np.array([0.0, 1.0])
    for endpoint in time_boot[::4]:
        ax_effect.plot(x, [100.0, endpoint], color=COLORS["router"], alpha=0.018, lw=0.55)
    for endpoint in accuracy_boot[::4]:
        ax_effect.plot(x, [100.0, endpoint], color=COLORS["7b"], alpha=0.018, lw=0.55)
    ax_effect.plot(x, [100.0, time_endpoint], color=COLORS["router"], lw=2.35, zorder=3)
    ax_effect.plot(x, [100.0, accuracy_endpoint], color=COLORS["7b"], lw=2.35, zorder=3)
    ax_effect.scatter(x, [100.0, time_endpoint], s=48, marker="D", color=COLORS["router"], edgecolor="white", lw=0.7, zorder=4)
    ax_effect.scatter(x, [100.0, accuracy_endpoint], s=48, marker="s", color=COLORS["7b"], edgecolor="white", lw=0.7, zorder=4)
    ax_effect.errorbar(
        [1.0],
        [time_endpoint],
        yerr=[[time_endpoint - np.percentile(time_boot, 2.5)], [np.percentile(time_boot, 97.5) - time_endpoint]],
        fmt="none",
        ecolor=COLORS["router"],
        lw=1.0,
        capsize=2.5,
        zorder=5,
    )
    ax_effect.errorbar(
        [1.0],
        [accuracy_endpoint],
        yerr=[[accuracy_endpoint - np.percentile(accuracy_boot, 2.5)], [np.percentile(accuracy_boot, 97.5) - accuracy_endpoint]],
        fmt="none",
        ecolor=COLORS["7b"],
        lw=1.0,
        capsize=2.5,
        zorder=5,
    )
    ax_effect.text(1.07, time_endpoint, f"Time  {time_endpoint:.1f}", color=COLORS["text"], va="center", fontsize=8)
    ax_effect.text(1.07, accuracy_endpoint, f"Accuracy  {accuracy_endpoint:.1f}", color=COLORS["text"], va="center", fontsize=8)
    ax_effect.text(0.52, 80.0, f"{time_gain:.1f}% less time", ha="center", va="center", fontsize=8, color=COLORS["text"])
    ax_effect.text(0.52, 98.0, f"{accuracy_loss:.1f}% relative loss", ha="center", va="bottom", fontsize=7.5, color=COLORS["text"])
    ax_effect.text(0.5, 61.8, f"{effect_ratio:.1f}x larger relative time effect", ha="center", va="bottom", fontsize=7.5)
    ax_effect.annotate(
        "available routing information",
        xy=(0.92, 104.1),
        xytext=(0.08, 104.1),
        ha="center",
        va="center",
        fontsize=7.2,
        arrowprops={"arrowstyle": "->", "color": COLORS["text"], "lw": 0.7},
    )
    ax_effect.set_xticks([0, 1], ["No routing\nfixed best model", "+ in-context\ntraining traces"])
    ax_effect.set_xlim(-0.15, 1.28)
    ax_effect.set_ylim(60, 106)
    ax_effect.set_ylabel("Index (no routing = 100)")
    ax_effect.set_title("a  Information-to-speed effect", loc="left")
    clean_axis(ax_effect, grid_axis="y")

    groups = ["overall", "easy", "medium", "hard"]
    group_colors = [COLORS["router"], COLORS["1.5b"], COLORS["7b"], COLORS["32b"]]
    data: list[np.ndarray] = []
    for group in groups:
        subset = records if group == "overall" else [row for row in records if row["mode"] == group]
        data.append(
            np.array(
                [operational_log_time(row["best_single"]) - operational_log_time(row["router"]) for row in subset],
                dtype=float,
            )
        )
    all_values = np.concatenate(data)
    limit = max(abs(float(np.percentile(all_values, 0.5))), abs(float(np.percentile(all_values, 99.5))), 1.0)
    positions = np.arange(len(groups))
    ax_dist.axvspan(-limit * 1.12, 0, color=COLORS["32b"], alpha=0.045, lw=0)
    ax_dist.axvspan(0, limit * 1.12, color=COLORS["1.5b"], alpha=0.055, lw=0)
    half_violin(ax_dist, data, positions, group_colors)
    rng = np.random.default_rng(17)
    for pos, values, color in zip(positions, data, group_colors):
        jitter = rng.uniform(-0.24, -0.055, size=len(values))
        ax_dist.scatter(values, pos + jitter, s=8, color=color, alpha=0.32, linewidth=0, rasterized=True)
        q1, median, q3 = np.percentile(values, [25, 50, 75])
        ax_dist.plot([q1, q3], [pos + 0.08, pos + 0.08], color=COLORS["text"], lw=4.6, solid_capstyle="butt")
        ax_dist.scatter([median], [pos + 0.08], marker="|", s=75, color="white", linewidth=1.2, zorder=5)
        positive = 100.0 * float(np.mean(values > 0))
        ax_dist.text(limit * 1.08, pos, f"{positive:.0f}% faster", ha="right", va="center", fontsize=7.5)
    ax_dist.axvline(0, color=COLORS["text"], lw=0.85)
    ax_dist.text(-limit * 0.57, -0.58, "baseline faster", ha="center", va="center", fontsize=7.2)
    ax_dist.text(limit * 0.57, -0.58, "router faster", ha="center", va="center", fontsize=7.2)
    ax_dist.set_xlim(-limit * 1.12, limit * 1.12)
    ax_dist.set_yticks(positions, ["Overall", *[MODE_LABELS[group] for group in groups[1:]]])
    ax_dist.set_ylim(len(groups) - 0.4, -0.78)
    ax_dist.set_xlabel(r"Paired operational log-speedup  $\log T_{\rm single}-\log T_{\rm router}$")
    ax_dist.set_title("b  Task-level speedup distribution", loc="left")
    clean_axis(ax_dist, grid_axis="x")
    top_axis = ax_dist.secondary_xaxis("top")
    factors = np.array([0.1, 0.5, 1.0, 2.0, 10.0])
    ticks = np.log(factors)
    valid = (ticks >= -limit * 1.08) & (ticks <= limit * 1.08)
    top_axis.set_xticks(ticks[valid], [f"{factor:g}x" for factor in factors[valid]])
    top_axis.set_xlabel("Router speed factor", labelpad=3)
    top_axis.tick_params(axis="x", labelsize=7.2, pad=2)
    top_axis.spines["top"].set_visible(False)

    save(fig, output_dir, "humaneval_information_speed_effect")


def first_hit_durations(records: list[dict[str, Any]], method: str) -> np.ndarray:
    return np.array(
        [
            float(row[method]["time_seconds"]) if row[method]["solved"] else float("inf")
            for row in records
        ],
        dtype=float,
    )


def profile_on_grid(durations: np.ndarray, timeline: np.ndarray) -> np.ndarray:
    return np.mean(durations[:, None] <= timeline[None, :], axis=0)


def bootstrap_profile(
    durations: np.ndarray,
    timeline: np.ndarray,
    *,
    B: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = len(durations)
    values = np.empty((B, len(timeline)), dtype=float)
    for idx in range(B):
        sample = durations[rng.integers(0, n, size=n)]
        values[idx] = profile_on_grid(sample, timeline)
    return np.percentile(values, 2.5, axis=0), np.percentile(values, 97.5, axis=0)


def time_at_coverage(durations: np.ndarray, coverage: float) -> float | None:
    rank = int(math.ceil(coverage * len(durations)))
    finite = np.sort(durations[np.isfinite(durations)])
    if rank <= 0 or len(finite) < rank:
        return None
    return float(finite[rank - 1])


def plot_data_profiles(records: list[dict[str, Any]], output_dir: Path) -> None:
    finite_times = [
        float(row[method]["time_seconds"])
        for row in records
        for method in ["best_single", "router"]
        if row[method]["solved"] and float(row[method]["time_seconds"]) > 0
    ]
    xmin = max(0.15, min(finite_times) * 0.8)
    xmax = max(finite_times) * 1.25
    timeline = np.geomspace(xmin, xmax, 220)
    groups = ["overall", "easy", "medium", "hard"]
    group_labels = {"overall": "Overall", **MODE_LABELS}
    fig, axes = plt.subplots(2, 2, figsize=(7.05, 4.35), sharex=True, sharey=True)
    axes = axes.flatten()
    coverage = 0.70

    for panel_idx, (ax, group) in enumerate(zip(axes, groups)):
        subset = records if group == "overall" else [row for row in records if row["mode"] == group]
        base = first_hit_durations(subset, "best_single")
        routed = first_hit_durations(subset, "router")
        base_profile = profile_on_grid(base, timeline)
        routed_profile = profile_on_grid(routed, timeline)
        base_lo, base_hi = bootstrap_profile(base, timeline, B=500, seed=101 + panel_idx)
        routed_lo, routed_hi = bootstrap_profile(routed, timeline, B=500, seed=201 + panel_idx)

        ax.fill_between(timeline, base_lo, base_hi, step="post", color=COLORS["7b"], alpha=0.10, linewidth=0)
        ax.fill_between(timeline, routed_lo, routed_hi, step="post", color=COLORS["1.5b"], alpha=0.12, linewidth=0)
        ax.fill_between(
            timeline,
            base_profile,
            routed_profile,
            where=routed_profile >= base_profile,
            step="post",
            color=COLORS["1.5b"],
            alpha=0.14,
            interpolate=True,
            linewidth=0,
        )
        ax.fill_between(
            timeline,
            base_profile,
            routed_profile,
            where=routed_profile < base_profile,
            step="post",
            color=COLORS["32b"],
            alpha=0.10,
            interpolate=True,
            linewidth=0,
        )
        ax.step(timeline, base_profile, where="post", color=COLORS["7b"], lw=1.55, label="No routing")
        ax.step(timeline, routed_profile, where="post", color=COLORS["1.5b"], lw=1.8, label="+ in-context traces")

        base_t = time_at_coverage(base, coverage)
        routed_t = time_at_coverage(routed, coverage)
        if base_t is not None and routed_t is not None:
            reduction = 100.0 * (base_t - routed_t) / base_t
            ax.hlines(coverage, routed_t, base_t, color=COLORS["text"], lw=0.75, linestyle=(0, (2, 2)))
            ax.annotate(
                "",
                xy=(base_t, coverage),
                xytext=(routed_t, coverage),
                arrowprops={"arrowstyle": "<->", "color": COLORS["text"], "lw": 0.8},
            )
            midpoint = math.sqrt(base_t * routed_t)
            ax.text(
                midpoint,
                coverage - 0.055,
                f"{reduction:.0f}% less time\nat 70% coverage",
                ha="center",
                va="top",
                fontsize=6.5,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 0.6},
                zorder=8,
            )

        base_plateau = float(np.mean(np.isfinite(base)))
        routed_plateau = float(np.mean(np.isfinite(routed)))
        label_x = xmax * 0.98
        ax.text(label_x, base_plateau + 0.014, f"{100 * base_plateau:.1f}%", color=COLORS["7b"], ha="right", va="bottom", fontsize=7)
        ax.text(label_x, routed_plateau - 0.014, f"{100 * routed_plateau:.1f}%", color=COLORS["1.5b"], ha="right", va="top", fontsize=7)
        ax.axhline(coverage, color=COLORS["grid"], lw=0.55, zorder=0)
        ax.set_xscale("log")
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(0, 1.01)
        ax.set_title(f"{chr(97 + panel_idx)}  {group_labels[group]}", loc="left")
        clean_axis(ax)

    axes[0].legend(frameon=False, loc="upper left", ncol=1, handlelength=2.5)
    axes[0].set_ylabel("Verified tasks solved")
    axes[2].set_ylabel("Verified tasks solved")
    axes[2].set_xlabel("Wall-clock budget (s, log scale)")
    axes[3].set_xlabel("Wall-clock budget (s, log scale)")
    for ax in axes:
        ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(xmax=1.0, decimals=0))
    fig.suptitle("Verified-solution data profiles", y=1.01, fontweight="bold")
    fig.tight_layout(pad=0.8, h_pad=1.0, w_pad=1.2)
    save(fig, output_dir, "humaneval_data_profiles")


def relative_quality_speed(
    records: list[dict[str, Any]],
) -> tuple[float, float]:
    base_time = float(np.mean([row["best_single"]["time_seconds"] for row in records]))
    routed_time = float(np.mean([row["router"]["time_seconds"] for row in records]))
    base_accuracy = float(np.mean([row["best_single"]["solved"] for row in records]))
    routed_accuracy = float(np.mean([row["router"]["solved"] for row in records]))
    retained = 100.0 * routed_accuracy / max(base_accuracy, 1.0e-8)
    speedup = base_time / max(routed_time, 1.0e-8)
    return retained, speedup


def bootstrap_quality_speed(
    records: list[dict[str, Any]],
    *,
    B: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = len(records)
    retained = np.empty(B, dtype=float)
    speedup = np.empty(B, dtype=float)
    for idx in range(B):
        sample = [records[int(i)] for i in rng.integers(0, n, size=n)]
        retained[idx], speedup[idx] = relative_quality_speed(sample)
    return retained, speedup


def bootstrap_density_contours(
    ax: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    color: str,
) -> None:
    x_lo, x_hi = np.percentile(x, [0.5, 99.5])
    y_lo, y_hi = np.percentile(y, [0.5, 99.5])
    x_pad = max(0.25, 0.08 * (x_hi - x_lo))
    y_pad = max(0.05, 0.08 * (y_hi - y_lo))
    gx = np.linspace(x_lo - x_pad, x_hi + x_pad, 120)
    gy = np.linspace(y_lo - y_pad, y_hi + y_pad, 100)
    xx, yy = np.meshgrid(gx, gy)
    scale_x = max(float(np.std(x)), 1.0e-6)
    scale_y = max(float(np.std(y)), 1.0e-6)
    samples = np.vstack([(x - np.mean(x)) / scale_x, (y - np.mean(y)) / scale_y])
    kde = gaussian_kde(samples)
    query = np.vstack(
        [
            ((xx - np.mean(x)) / scale_x).ravel(),
            ((yy - np.mean(y)) / scale_y).ravel(),
        ]
    )
    density = kde(query).reshape(xx.shape)
    flat = np.sort(density.ravel())[::-1]
    mass = np.cumsum(flat)
    mass /= mass[-1]
    level_50 = float(flat[np.searchsorted(mass, 0.50)])
    level_90 = float(flat[np.searchsorted(mass, 0.90)])
    top = float(density.max()) * 1.001
    ax.contourf(
        xx,
        yy,
        density,
        levels=[level_90, level_50, top],
        colors=[color, color],
        alpha=0.075,
        antialiased=True,
    )
    ax.contour(
        xx,
        yy,
        density,
        levels=[level_90, level_50],
        colors=[color, color],
        linewidths=[0.55, 0.85],
        alpha=0.42,
    )


def plot_quality_speed_map(records: list[dict[str, Any]], output_dir: Path) -> None:
    groups = ["overall", "easy", "medium", "hard"]
    colors = [COLORS["router"], COLORS["1.5b"], COLORS["7b"], COLORS["32b"]]
    markers = ["D", "o", "s", "^"]
    payload: list[dict[str, Any]] = []
    for idx, group in enumerate(groups):
        subset = records if group == "overall" else [row for row in records if row["mode"] == group]
        retained, speedup = relative_quality_speed(subset)
        retained_boot, speedup_boot = bootstrap_quality_speed(subset, B=1200, seed=301 + idx)
        payload.append(
            {
                "group": group,
                "retained": retained,
                "speedup": speedup,
                "retained_boot": retained_boot,
                "speedup_boot": speedup_boot,
                "color": colors[idx],
                "marker": markers[idx],
            }
        )

    all_retained = np.concatenate([item["retained_boot"] for item in payload])
    all_speedup = np.concatenate([item["speedup_boot"] for item in payload])
    xmin = min(89.0, float(np.percentile(all_retained, 0.5)) - 0.7)
    xmax = max(102.0, float(np.percentile(all_retained, 99.5)) + 0.7)
    ymin = min(0.72, float(np.percentile(all_speedup, 0.5)) - 0.12)
    ymax = max(4.55, float(np.percentile(all_speedup, 99.5)) + 0.2)

    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    ax.axhspan(1.0, ymax, color=COLORS["1.5b"], alpha=0.045, linewidth=0)
    ax.axvspan(100.0, xmax, color=COLORS["7b"], alpha=0.035, linewidth=0)
    ax.axhline(1.0, color=COLORS["text"], lw=0.8, linestyle=(0, (4, 3)))
    ax.axvline(100.0, color=COLORS["text"], lw=0.8, linestyle=(0, (4, 3)))
    ax.scatter([100.0], [1.0], marker="*", s=105, color=COLORS["oracle"], edgecolor="white", lw=0.8, zorder=6)
    ax.text(100.15, 0.96, "no-routing baseline", ha="left", va="top", fontsize=7.5)

    label_offsets = {
        "overall": (0.35, 0.15),
        "easy": (0.28, -0.05),
        "medium": (0.28, 0.12),
        "hard": (0.28, 0.13),
    }
    for item in payload:
        rb = item["retained_boot"]
        sb = item["speedup_boot"]
        bootstrap_density_contours(ax, rb, sb, item["color"])
        ax.plot([100.0, item["retained"]], [1.0, item["speedup"]], color=item["color"], lw=0.7, alpha=0.28, zorder=1)
        ax.scatter(
            [item["retained"]],
            [item["speedup"]],
            marker=item["marker"],
            s=64,
            color=item["color"],
            edgecolor="white",
            lw=0.75,
            zorder=5,
        )
        dx, dy = label_offsets[item["group"]]
        ax.text(
            item["retained"] + dx,
            item["speedup"] + dy,
            f"{('Overall' if item['group'] == 'overall' else MODE_LABELS[item['group']])}  "
            f"{item['speedup']:.2f}x at {item['retained']:.1f}%",
            ha="left",
            va="center",
            fontsize=8,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.62, "pad": 0.5},
        )

    ax.text(xmin + 0.35, ymax - 0.2, "faster verified solution", ha="left", va="top", fontsize=8)
    ax.text(100.2, ymax - 0.2, "no accuracy loss", ha="left", va="top", fontsize=8)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_xlabel("Verified accuracy retained relative to no routing (%)")
    ax.set_ylabel("Verified first-hit speedup factor")
    ax.set_title("Speed gained at retained accuracy", loc="left")
    clean_axis(ax)
    fig.tight_layout(pad=0.7)
    save(fig, output_dir, "humaneval_quality_speed_map")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HumanEval+ paper figures.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output_dir = args.output_dir.resolve()
    configure_style()
    summary = read_json(root / "experiments/humaneval-plus/retry-allocation-router/results/processed/router_summary.json")
    records = read_jsonl(root / "experiments/humaneval-plus/retry-allocation-router/results/processed/router_results.jsonl")
    tau = read_json(root / "experiments/humaneval-plus/qwen-model-size-frontier/results/processed/tau_star.json")
    raw_paths = {
        "1.5b": root / "experiments/humaneval-plus/qwen-model-size-frontier/data/raw/runs_qwen2.5-coder_1.5b_full_20260616T0640Z.jsonl",
        "7b": root / "experiments/humaneval-plus/qwen-model-size-frontier/data/raw/runs_qwen2.5-coder_7b_full_20260616T0640Z.jsonl",
        "32b": root / "experiments/humaneval-plus/qwen-model-size-frontier/data/raw/runs_qwen2.5-coder_32b_full_20260616T0640Z.jsonl",
    }
    plot_speed_accounting(summary, output_dir)
    plot_retry_and_frontier(raw_paths, tau, output_dir)
    plot_information_speed_effect(records, output_dir)
    plot_data_profiles(records, output_dir)
    plot_quality_speed_map(records, output_dir)
    print(f"Wrote paper figures to {output_dir}")


if __name__ == "__main__":
    main()
