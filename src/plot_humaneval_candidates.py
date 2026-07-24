from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.tri import Triangulation


COLORS = {
    "1.5b": "#0B6E69",
    "7b": "#4C5B9B",
    "32b": "#E76F51",
    "router": "#D49B22",
    "oracle": "#273043",
    "easy": "#2A9D8F",
    "medium": "#5E6FAE",
    "hard": "#E76F51",
    "grid": "#D8DCE2",
    "text": "#20242A",
    "muted": "#8A9099",
    "paper": "#FAFAF8",
}

MODEL_ORDER = ("1.5b", "7b", "32b")
MODE_ORDER = ("easy", "medium", "hard")
MODE_LABELS = {"easy": "Mode 1", "medium": "Mode 2", "hard": "Mode 3"}
MODEL_LABELS = {"1.5b": "Qwen 1.5B", "7b": "Qwen 7B", "32b": "Qwen 32B"}


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.edgecolor": COLORS["text"],
            "axes.labelcolor": COLORS["text"],
            "text.color": COLORS["text"],
            "xtick.color": COLORS["text"],
            "ytick.color": COLORS["text"],
            "axes.linewidth": 0.75,
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
    fig.savefig(output_dir / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.03)
    fig.savefig(output_dir / f"{stem}.png", dpi=260, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def clean_axis(ax: plt.Axes, *, grid_axis: str = "both") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, color=COLORS["grid"], linewidth=0.55, alpha=0.8)
    ax.set_axisbelow(True)


def load_trace_bank(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    paths = {
        "1.5b": root / "data/raw/runs_qwen2.5-coder_1.5b_full_20260616T0640Z.jsonl",
        "7b": root / "data/raw/runs_qwen2.5-coder_7b_full_20260616T0640Z.jsonl",
        "32b": root / "data/raw/runs_qwen2.5-coder_32b_full_20260616T0640Z.jsonl",
    }
    bank: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for model, path in paths.items():
        for row in read_jsonl(path):
            bank[str(row["task_id"])][model] = row
    return dict(bank)


def allocation_grid(budget: int, *, exact: bool) -> list[dict[str, int]]:
    values: list[dict[str, int]] = []
    for n_small in range(budget + 1):
        for n_mid in range(budget + 1 - n_small):
            max_large = budget - n_small - n_mid
            large_values = [max_large] if exact else range(max_large + 1)
            for n_large in large_values:
                total = n_small + n_mid + n_large
                if total == 0 or (exact and total != budget):
                    continue
                values.append({"1.5b": n_small, "7b": n_mid, "32b": n_large})
    return values


def execute(
    task_id: str,
    alloc: dict[str, int],
    bank: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    seconds = 0.0
    tokens = 0
    attempts = 0
    for model in MODEL_ORDER:
        trace = bank[task_id][model]
        requested = int(alloc.get(model, 0))
        for idx in range(min(requested, len(trace["attempt_statuses"]))):
            seconds += float(trace["attempt_seconds"][idx])
            tokens += int(trace["attempt_token_counts"][idx])
            attempts += 1
            if trace["attempt_statuses"][idx] == "pass":
                return {
                    "solved": True,
                    "time_seconds": seconds,
                    "tokens": tokens,
                    "attempts": attempts,
                    "first_pass_model": model,
                }
    return {
        "solved": False,
        "time_seconds": seconds,
        "tokens": tokens,
        "attempts": attempts,
        "first_pass_model": None,
    }


def allocation_metrics(
    task_ids: Iterable[str],
    alloc: dict[str, int],
    bank: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, float]:
    results = [execute(task_id, alloc, bank) for task_id in task_ids]
    solved_rate = float(np.mean([result["solved"] for result in results]))
    mean_time = float(np.mean([result["time_seconds"] for result in results]))
    mean_tokens = float(np.mean([result["tokens"] for result in results]))
    log_effort = math.log(max(mean_time, 1e-8) / max(solved_rate, 0.02))
    return {
        "solved_rate": solved_rate,
        "mean_time": mean_time,
        "mean_tokens": mean_tokens,
        "log_effort": log_effort,
    }


def normalized_alloc(alloc: dict[str, float]) -> np.ndarray:
    values = np.array([float(alloc.get(model, alloc.get(f"n_{model}", 0.0))) for model in MODEL_ORDER])
    total = float(values.sum())
    return values / total if total > 0 else np.full(3, 1.0 / 3.0)


def barycentric(shares: np.ndarray) -> tuple[float, float]:
    vertices = np.array([[0.0, 0.0], [0.5, math.sqrt(3.0) / 2.0], [1.0, 0.0]])
    point = shares @ vertices
    return float(point[0]), float(point[1])


def mean_record_alloc(records: list[dict[str, Any]], key: str) -> dict[str, float]:
    output = {model: 0.0 for model in MODEL_ORDER}
    if not records:
        return output
    for record in records:
        for model in MODEL_ORDER:
            output[model] += float(record[key].get(f"n_{model}", 0))
    return {model: value / len(records) for model, value in output.items()}


def plot_ternary_landscape(
    bank: dict[str, dict[str, dict[str, Any]]],
    records: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    allocations = allocation_grid(10, exact=True)
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.65), constrained_layout=True)
    cmap = LinearSegmentedColormap.from_list("speed_basin", ["#0B6E69", "#E9C46A", "#F4F1DE"])
    all_values: list[float] = []
    mode_payload: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for mode in MODE_ORDER:
        task_ids = [task_id for task_id, traces in bank.items() if traces["1.5b"]["mode"] == mode]
        points = np.array([barycentric(normalized_alloc(alloc)) for alloc in allocations])
        values = np.array([allocation_metrics(task_ids, alloc, bank)["log_effort"] for alloc in allocations])
        mode_payload[mode] = (points[:, 0], points[:, 1], values)
        all_values.extend(values.tolist())
    norm = Normalize(vmin=float(np.percentile(all_values, 3)), vmax=float(np.percentile(all_values, 97)))

    for ax, mode in zip(axes, MODE_ORDER):
        xs, ys, values = mode_payload[mode]
        triangulation = Triangulation(xs, ys)
        contour = ax.tricontourf(triangulation, values, levels=18, cmap=cmap, norm=norm)
        ax.tricontour(triangulation, values, levels=7, colors=COLORS["text"], linewidths=0.35, alpha=0.25)
        ax.plot([0, 0.5, 1, 0], [0, math.sqrt(3) / 2, 0, 0], color=COLORS["text"], lw=0.8)
        ax.scatter(xs, ys, s=5, color=COLORS["text"], alpha=0.16, linewidth=0)

        mode_records = [record for record in records if record["mode"] == mode]
        router_point = barycentric(normalized_alloc(mean_record_alloc(mode_records, "router_alloc")))
        oracle_point = barycentric(normalized_alloc(mean_record_alloc(mode_records, "oracle_alloc")))
        baseline_point = barycentric(np.array([0.0, 1.0, 0.0]))
        ax.annotate(
            "",
            xy=oracle_point,
            xytext=router_point,
            arrowprops={"arrowstyle": "->", "lw": 1.0, "color": COLORS["oracle"]},
            zorder=5,
        )
        ax.scatter(*baseline_point, marker="o", s=38, color=COLORS["7b"], edgecolor="white", lw=0.7, zorder=6)
        ax.scatter(*router_point, marker="D", s=48, color=COLORS["router"], edgecolor="white", lw=0.7, zorder=6)
        ax.scatter(*oracle_point, marker="*", s=78, color="white", edgecolor=COLORS["oracle"], lw=0.8, zorder=6)

        ax.text(-0.03, -0.055, "1.5B", ha="center", va="top")
        ax.text(0.5, math.sqrt(3) / 2 + 0.045, "7B", ha="center", va="bottom")
        ax.text(1.03, -0.055, "32B", ha="center", va="top")
        ax.set_title(MODE_LABELS[mode])
        ax.set_aspect("equal")
        ax.set_xlim(-0.08, 1.08)
        ax.set_ylim(-0.08, 0.98)
        ax.axis("off")

    handles = [
        mpl.lines.Line2D([], [], marker="o", ls="", color=COLORS["7b"], label="best single"),
        mpl.lines.Line2D([], [], marker="D", ls="", color=COLORS["router"], label="router"),
        mpl.lines.Line2D([], [], marker="*", ls="", markerfacecolor="white", markeredgecolor=COLORS["oracle"], label="oracle"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False)
    colorbar = fig.colorbar(contour, ax=axes, fraction=0.025, pad=0.02)
    colorbar.set_label("Operational log-effort (lower is faster)")
    colorbar.outline.set_linewidth(0.5)
    fig.suptitle("Retry-allocation landscape", y=1.03, fontweight="bold")
    save(fig, output_dir, "candidate_ternary_allocation")


def effective_log_time(result: dict[str, Any], *, p_min: float = 0.05) -> float:
    seconds = max(float(result["time_seconds"]), 1e-4)
    return math.log(seconds) - (0.0 if result["solved"] else math.log(p_min))


def plot_raincloud(records: list[dict[str, Any]], output_dir: Path) -> None:
    groups = ["overall", *MODE_ORDER]
    data: list[np.ndarray] = []
    for group in groups:
        subset = records if group == "overall" else [record for record in records if record["mode"] == group]
        values = np.array(
            [effective_log_time(record["best_single"]) - effective_log_time(record["router"]) for record in subset]
        )
        data.append(values)

    fig, ax = plt.subplots(figsize=(7.0, 3.1))
    positions = np.arange(len(groups))
    violins = ax.violinplot(
        data,
        positions=positions,
        widths=0.82,
        showextrema=False,
        orientation="horizontal",
    )
    group_colors = [COLORS["router"], COLORS["easy"], COLORS["medium"], COLORS["hard"]]
    for body, color in zip(violins["bodies"], group_colors):
        body.set_facecolor(color)
        body.set_edgecolor("none")
        body.set_alpha(0.26)
        vertices = body.get_paths()[0].vertices
        center = float(np.mean(vertices[:, 1]))
        vertices[:, 1] = np.maximum(vertices[:, 1], center)

    rng = np.random.default_rng(17)
    for pos, values, color in zip(positions, data, group_colors):
        jitter = rng.uniform(-0.24, -0.05, size=len(values))
        ax.scatter(values, pos + jitter, s=10, color=color, alpha=0.35, linewidth=0, rasterized=True)
        q1, median, q3 = np.percentile(values, [25, 50, 75])
        ax.plot([q1, q3], [pos + 0.08, pos + 0.08], color=COLORS["text"], lw=5, solid_capstyle="butt")
        ax.scatter([median], [pos + 0.08], marker="|", s=90, color="white", linewidth=1.4, zorder=5)
    all_values = np.concatenate(data)
    limit = max(abs(float(np.percentile(all_values, 1))), abs(float(np.percentile(all_values, 99))), 1.0)
    ax.set_xlim(-limit * 1.12, limit * 1.12)
    for pos, values in zip(positions, data):
        positive = 100.0 * float(np.mean(values > 0))
        ax.text(limit * 1.08, pos, f"{positive:.0f}% faster", ha="right", va="center", fontsize=8)
    ax.axvline(0, color=COLORS["text"], lw=0.8)
    ax.set_yticks(positions, ["Overall", *[MODE_LABELS[group] for group in groups[1:]]])
    ax.invert_yaxis()
    ax.set_xlabel(r"Paired operational log-speedup  $\log T_{\rm single}-\log T_{\rm router}$")
    ax.set_title("Where does routing create speed?", loc="left")
    clean_axis(ax, grid_axis="x")
    save(fig, output_dir, "candidate_raincloud_speedup")


def pareto_front(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(points, key=lambda item: (item["mean_time"], -item["solved_rate"]))
    frontier: list[dict[str, Any]] = []
    best_accuracy = -1.0
    for item in ordered:
        if item["solved_rate"] > best_accuracy + 1e-12:
            frontier.append(item)
            best_accuracy = item["solved_rate"]
    return frontier


def plot_pareto(
    bank: dict[str, dict[str, dict[str, Any]]],
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> None:
    task_ids = sorted(bank)
    points: list[dict[str, Any]] = []
    for alloc in allocation_grid(10, exact=False):
        metrics = allocation_metrics(task_ids, alloc, bank)
        points.append({**metrics, "alloc": alloc, "depth": sum(alloc.values())})
    frontier = pareto_front(points)

    fig, ax = plt.subplots(figsize=(6.7, 3.65))
    scatter = ax.scatter(
        [point["mean_time"] for point in points],
        [100.0 * point["solved_rate"] for point in points],
        c=[point["depth"] for point in points],
        cmap=LinearSegmentedColormap.from_list("depth", ["#DDE8E6", "#0B6E69"]),
        s=18,
        alpha=0.6,
        linewidth=0,
        rasterized=True,
    )
    ax.plot(
        [point["mean_time"] for point in frontier],
        [100.0 * point["solved_rate"] for point in frontier],
        color=COLORS["oracle"],
        lw=1.8,
        label="static-allocation Pareto frontier",
        zorder=3,
    )

    highlights = {
        "Qwen 7B": (summary["methods"]["always_7b"], COLORS["7b"], "s"),
        "Router": (summary["methods"]["router"], COLORS["router"], "D"),
        "Oracle": (summary["methods"]["oracle"], COLORS["oracle"], "*"),
    }
    offsets = {"Qwen 7B": (6, 6), "Router": (6, -11), "Oracle": (6, 5)}
    for label, (metrics, color, marker) in highlights.items():
        x = float(metrics["mean_time_all"])
        y = 100.0 * float(metrics["solved_rate"])
        ax.scatter(x, y, s=74 if label != "Oracle" else 105, marker=marker, color=color, edgecolor="white", lw=0.7, zorder=5)
        ax.annotate(label, (x, y), xytext=offsets[label], textcoords="offset points", va="center")
    ax.set_xscale("log")
    ax.set_xlabel("Mean verified first-hit time (s, log scale)")
    ax.set_ylabel("Solved within allocation horizon (%)")
    ax.set_title("The allocation-policy frontier", loc="left")
    clean_axis(ax)
    colorbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    colorbar.set_label("Allocated retry depth")
    colorbar.outline.set_linewidth(0.5)
    ax.legend(frameon=False, loc="lower right")
    save(fig, output_dir, "candidate_pareto_frontier")


def km_curve(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    durations = np.array(
        [float(row["tau_seconds"] if row["solved"] else row["seconds_spent_total"]) for row in rows]
    )
    events = np.array([bool(row["solved"]) for row in rows])
    order = np.argsort(durations)
    durations = durations[order]
    events = events[order]
    survival = 1.0
    xs = [0.0]
    ys = [1.0]
    for time in np.unique(durations):
        at_risk = int(np.sum(durations >= time))
        deaths = int(np.sum((durations == time) & events))
        if deaths:
            survival *= 1.0 - deaths / at_risk
        xs.extend([float(time), float(time)])
        ys.extend([ys[-1], survival])
    return np.array(xs), np.array(ys)


def plot_survival(bank: dict[str, dict[str, dict[str, Any]]], output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.7, 3.55))
    for model in MODEL_ORDER:
        rows = [traces[model] for traces in bank.values()]
        xs, ys = km_curve(rows)
        ax.step(xs, 100.0 * ys, where="post", color=COLORS[model], lw=1.8, label=MODEL_LABELS[model])
        censored = [float(row["seconds_spent_total"]) for row in rows if not row["solved"]]
        if censored:
            sample = np.array(censored)
            nearest = np.searchsorted(xs, sample, side="right") - 1
            nearest = np.clip(nearest, 0, len(ys) - 1)
            ax.scatter(sample, 100.0 * ys[nearest], marker="|", s=34, color=COLORS[model], alpha=0.55)
    ax.set_xscale("log")
    ax.set_xlim(left=0.2)
    ax.set_ylim(0, 102)
    ax.set_xlabel("Wall-clock time to verifier (s, log scale)")
    ax.set_ylabel("Tasks not yet solved (%)")
    ax.set_title("First-hit survival: how long does failure persist?", loc="left")
    ax.legend(frameon=False, ncol=3, loc="upper right")
    clean_axis(ax)
    save(fig, output_dir, "candidate_first_hit_survival")


def ribbon_patch(
    ax: plt.Axes,
    x0: float,
    x1: float,
    y0a: float,
    y0b: float,
    y1a: float,
    y1b: float,
    color: str,
    alpha: float = 0.45,
) -> None:
    dx = (x1 - x0) * 0.48
    vertices = [
        (x0, y0a),
        (x0 + dx, y0a),
        (x1 - dx, y1a),
        (x1, y1a),
        (x1, y1b),
        (x1 - dx, y1b),
        (x0 + dx, y0b),
        (x0, y0b),
        (x0, y0a),
    ]
    codes = [
        MplPath.MOVETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.LINETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CLOSEPOLY,
    ]
    ax.add_patch(PathPatch(MplPath(vertices, codes), facecolor=color, edgecolor="none", alpha=alpha))


def stacked_nodes(labels: list[str], counts: dict[str, int], *, gap: float = 2.0) -> dict[str, tuple[float, float]]:
    cursor = 0.0
    output: dict[str, tuple[float, float]] = {}
    for label in labels:
        height = float(counts.get(label, 0))
        output[label] = (cursor, cursor + height)
        cursor += height + gap
    return output


def plot_alluvial(records: list[dict[str, Any]], output_dir: Path) -> None:
    rows: list[tuple[str, str, str]] = []
    for record in records:
        shares = {model: int(record["router_alloc"].get(f"n_{model}", 0)) for model in MODEL_ORDER}
        dominant = max(MODEL_ORDER, key=lambda model: (shares[model], -MODEL_ORDER.index(model)))
        outcome = record["router"]["first_pass_model"] or "unsolved"
        rows.append((record["mode"], dominant, outcome))

    left_labels = list(MODE_ORDER)
    middle_labels = list(MODEL_ORDER)
    right_labels = [*MODEL_ORDER, "unsolved"]
    left_counts = {label: sum(left == label for left, _, _ in rows) for label in left_labels}
    middle_counts = {label: sum(mid == label for _, mid, _ in rows) for label in middle_labels}
    right_counts = {label: sum(right == label for _, _, right in rows) for label in right_labels}
    nodes = [
        stacked_nodes(left_labels, left_counts),
        stacked_nodes(middle_labels, middle_counts),
        stacked_nodes(right_labels, right_counts),
    ]

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    node_width = 0.035
    x_positions = [0.05, 0.5, 0.95]

    left_offsets = {label: nodes[0][label][0] for label in left_labels}
    middle_in_offsets = {label: nodes[1][label][0] for label in middle_labels}
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for left, middle, _ in rows:
        pair_counts[(left, middle)] += 1
    for left in left_labels:
        for middle in middle_labels:
            count = pair_counts[(left, middle)]
            if not count:
                continue
            y0a = left_offsets[left]
            y0b = y0a + count
            y1a = middle_in_offsets[middle]
            y1b = y1a + count
            ribbon_patch(ax, x_positions[0] + node_width, x_positions[1], y0a, y0b, y1a, y1b, COLORS[middle], 0.42)
            left_offsets[left] = y0b
            middle_in_offsets[middle] = y1b

    middle_out_offsets = {label: nodes[1][label][0] for label in middle_labels}
    right_offsets = {label: nodes[2][label][0] for label in right_labels}
    pair_counts_2: dict[tuple[str, str], int] = defaultdict(int)
    for _, middle, right in rows:
        pair_counts_2[(middle, right)] += 1
    for middle in middle_labels:
        for right in right_labels:
            count = pair_counts_2[(middle, right)]
            if not count:
                continue
            y0a = middle_out_offsets[middle]
            y0b = y0a + count
            y1a = right_offsets[right]
            y1b = y1a + count
            color = COLORS[middle] if right != "unsolved" else COLORS["muted"]
            ribbon_patch(ax, x_positions[1] + node_width, x_positions[2], y0a, y0b, y1a, y1b, color, 0.42)
            middle_out_offsets[middle] = y0b
            right_offsets[right] = y1b

    stage_labels = [left_labels, middle_labels, right_labels]
    node_colors = [
        {mode: COLORS[mode] for mode in MODE_ORDER},
        {model: COLORS[model] for model in MODEL_ORDER},
        {**{model: COLORS[model] for model in MODEL_ORDER}, "unsolved": COLORS["muted"]},
    ]
    display = {
        "easy": "Mode 1",
        "medium": "Mode 2",
        "hard": "Mode 3",
        "1.5b": "1.5B",
        "7b": "7B",
        "32b": "32B",
        "unsolved": "Unsolved",
    }
    for stage_idx, labels in enumerate(stage_labels):
        for label in labels:
            y0, y1 = nodes[stage_idx][label]
            ax.add_patch(
                Rectangle(
                    (x_positions[stage_idx], y0),
                    node_width,
                    y1 - y0,
                    facecolor=node_colors[stage_idx][label],
                    edgecolor="white",
                    lw=0.6,
                    zorder=5,
                )
            )
            ha = "right" if stage_idx == 2 else "left"
            x_text = x_positions[stage_idx] - 0.012 if stage_idx == 2 else x_positions[stage_idx] + node_width + 0.012
            ax.text(x_text, (y0 + y1) / 2, display[label], ha=ha, va="center", fontsize=8)
    max_y = max(max(value[1] for value in stage.values()) for stage in nodes)
    ax.text(x_positions[0], max_y + 7, "Task stratum", ha="left", fontweight="bold")
    ax.text(x_positions[1], max_y + 7, "Largest retry share", ha="center", fontweight="bold")
    ax.text(x_positions[2], max_y + 7, "First verified outcome", ha="right", fontweight="bold")
    ax.set_xlim(0, 1.04)
    ax.set_ylim(-2, max_y + 14)
    ax.axis("off")
    ax.set_title("How routing decisions become verified outcomes", loc="left")
    save(fig, output_dir, "candidate_alluvial_flow")


def plot_regret(records: list[dict[str, Any]], output_dir: Path) -> None:
    values: list[tuple[float, str, str]] = []
    for record in records:
        if not record["oracle"]["solved"]:
            continue
        regret = effective_log_time(record["router"]) - effective_log_time(record["oracle"])
        values.append((regret, record["mode"], record["task_id"]))
    values.sort(key=lambda item: item[0])
    regrets = np.array([value[0] for value in values])
    ranks = np.arange(1, len(values) + 1)

    fig, ax = plt.subplots(figsize=(6.8, 3.55))
    ax.fill_between(ranks, 0, regrets, color=COLORS["router"], alpha=0.16)
    for mode in MODE_ORDER:
        mask = np.array([value[1] == mode for value in values])
        ax.scatter(ranks[mask], regrets[mask], s=14, color=COLORS[mode], alpha=0.72, label=MODE_LABELS[mode], linewidth=0)
    ax.plot(ranks, regrets, color=COLORS["text"], lw=0.7, alpha=0.45)
    ax.axhline(0, color=COLORS["text"], lw=0.8)
    cutoff = int(math.ceil(0.9 * len(values)))
    tail_share = float(regrets[cutoff:].sum() / max(regrets.clip(min=0).sum(), 1e-8))
    ax.axvspan(cutoff, len(values), color=COLORS["hard"], alpha=0.08)
    ax.text(
        cutoff + 2,
        float(np.percentile(regrets, 80)),
        f"top 10% account for\n{100 * tail_share:.0f}% of positive regret",
        ha="left",
        va="center",
        fontsize=8,
    )
    ax.set_xlabel("Tasks ordered by operational routing regret")
    ax.set_ylabel(r"$L(q_\rho)-L(q^\star)$  (nats)")
    ax.set_title("Mismatch is concentrated in a small tail", loc="left")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    clean_axis(ax)
    save(fig, output_dir, "candidate_regret_landscape")


def plot_gallery(output_dir: Path) -> None:
    stems = [
        ("candidate_ternary_allocation", "A  Ternary allocation landscape"),
        ("candidate_raincloud_speedup", "B  Paired speedup raincloud"),
        ("candidate_pareto_frontier", "C  Pareto allocation frontier"),
        ("candidate_first_hit_survival", "D  First-hit survival"),
        ("candidate_alluvial_flow", "E  Routing alluvial"),
        ("candidate_regret_landscape", "F  Regret landscape"),
    ]
    fig, axes = plt.subplots(3, 2, figsize=(10.5, 12.2))
    for ax, (stem, title) in zip(axes.flat, stems):
        image = plt.imread(output_dir / f"{stem}.png")
        ax.imshow(image)
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
        ax.axis("off")
    fig.subplots_adjust(hspace=0.18, wspace=0.08)
    save(fig, output_dir, "candidate_plot_gallery")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate alternative HumanEval+ paper plots.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output_dir = args.output_dir.resolve()
    configure_style()
    bank = load_trace_bank(root)
    records = read_jsonl(root / "data/derived/router_results.jsonl")
    summary = read_json(root / "data/derived/router_summary.json")
    plot_ternary_landscape(bank, records, output_dir)
    plot_raincloud(records, output_dir)
    plot_pareto(bank, records, summary, output_dir)
    plot_survival(bank, output_dir)
    plot_alluvial(records, output_dir)
    plot_regret(records, output_dir)
    plot_gallery(output_dir)
    print(f"Wrote candidate plots to {output_dir}")


if __name__ == "__main__":
    main()
