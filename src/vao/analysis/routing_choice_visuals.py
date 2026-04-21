"""Summarize and visualize whether routers chose the verified-best mode."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from vao.logging_utils import read_jsonl, write_json
from vao.taxonomy import MODES, normalize_mode_probs


DEFAULT_DATASETS = {
    "phase2_local": "artifacts/phase2_routing_dataset.jsonl",
    "phase3_haiku_replacement": "artifacts/phase3_haiku_routing_dataset.jsonl",
    "phase35_haiku_patch": "artifacts/phase35_patch_routing_dataset.jsonl",
    "phase4_opus_teacher": "artifacts/phase4_teacher_routing_dataset.jsonl",
}


def summarize_dataset(name: str, path: Path, *, tolerance: float = 1e-9) -> dict[str, Any]:
    records = read_jsonl(path)
    rows = []
    selected_counts: Counter[str] = Counter()
    best_counts: Counter[str] = Counter()
    profile_counts: dict[str, Counter[str]] = {}
    confusion = {selected: {best: 0 for best in MODES} for selected in MODES}
    correct = 0
    label_correct = 0
    regrets = []
    for record in records:
        probs = normalize_mode_probs(record["original_mode_probs"])
        selected = max(MODES, key=lambda mode: probs[mode])
        gains = {mode: float(record["verified_gain_per_mode"][mode]) for mode in MODES}
        best_gain = max(gains.values())
        best_modes = [mode for mode in MODES if abs(gains[mode] - best_gain) <= tolerance]
        canonical_best = best_modes[0]
        selected_gain = gains[selected]
        regret = max(0.0, best_gain - selected_gain)
        is_correct = selected in best_modes
        productive_label = str(record.get("productive_mode_top1", canonical_best))
        selected_counts[selected] += 1
        best_counts[canonical_best] += 1
        confusion[selected][canonical_best] += 1
        correct += int(is_correct)
        label_correct += int(selected == productive_label)
        regrets.append(regret)
        profile = str(record.get("profile_id", "unknown"))
        profile_counts.setdefault(profile, Counter())
        profile_counts[profile]["total"] += 1
        profile_counts[profile]["correct"] += int(is_correct)
        profile_counts[profile]["incorrect"] += int(not is_correct)
        rows.append(
            {
                "run_id": record.get("run_id"),
                "profile_id": profile,
                "step": record.get("step"),
                "selected_mode": selected,
                "verified_best_mode": canonical_best,
                "verified_best_modes": best_modes,
                "productive_mode_top1": productive_label,
                "correct_by_verified_best": is_correct,
                "correct_by_productive_label": selected == productive_label,
                "routing_regret": regret,
                "selected_gain": selected_gain,
                "best_gain": best_gain,
            }
        )
    total = len(rows)
    return {
        "name": name,
        "path": str(path),
        "record_count": total,
        "correct_by_verified_best": correct,
        "incorrect_by_verified_best": total - correct,
        "accuracy_by_verified_best": correct / total if total else None,
        "correct_by_productive_label": label_correct,
        "incorrect_by_productive_label": total - label_correct,
        "accuracy_by_productive_label": label_correct / total if total else None,
        "mean_routing_regret": sum(regrets) / total if total else None,
        "positive_regret_count": sum(1 for value in regrets if value > tolerance),
        "zero_regret_count": sum(1 for value in regrets if value <= tolerance),
        "selected_mode_counts": {mode: selected_counts.get(mode, 0) for mode in MODES},
        "verified_best_mode_counts": {mode: best_counts.get(mode, 0) for mode in MODES},
        "by_profile": {
            profile: {
                "total": counts["total"],
                "correct": counts["correct"],
                "incorrect": counts["incorrect"],
                "accuracy": counts["correct"] / counts["total"] if counts["total"] else None,
            }
            for profile, counts in sorted(profile_counts.items())
        },
        "confusion_selected_vs_verified_best": confusion,
        "rows": rows,
    }


def write_report(summaries: list[dict[str, Any]], markdown_out: Path, plot_paths: dict[str, str]) -> None:
    lines = [
        "# Routing Choice Correctness",
        "",
        "Primary correctness criterion: selected top-probability mode is one of the verified best-gain modes for that checkpoint.",
        "",
        "| dataset | steps | correct | incorrect | accuracy | mean regret |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summaries:
        lines.append(
            f"| `{item['name']}` | `{item['record_count']}` | `{item['correct_by_verified_best']}` | "
            f"`{item['incorrect_by_verified_best']}` | `{item['accuracy_by_verified_best']}` | "
            f"`{item['mean_routing_regret']}` |"
        )
    teacher = next((item for item in summaries if item["name"] == "phase4_opus_teacher"), None)
    if teacher:
        lines.extend(
            [
                "",
                "## Phase 4 Opus Teacher",
                "",
                f"- Correct choices: `{teacher['correct_by_verified_best']}`",
                f"- Incorrect choices: `{teacher['incorrect_by_verified_best']}`",
                f"- Accuracy: `{teacher['accuracy_by_verified_best']}`",
                f"- Mean routing regret: `{teacher['mean_routing_regret']}`",
                f"- Zero-regret steps: `{teacher['zero_regret_count']}`",
                f"- Positive-regret steps: `{teacher['positive_regret_count']}`",
                "",
                "### By Profile",
                "",
                "| profile | steps | correct | incorrect | accuracy |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for profile, row in teacher["by_profile"].items():
            lines.append(
                f"| `{profile}` | `{row['total']}` | `{row['correct']}` | `{row['incorrect']}` | `{row['accuracy']}` |"
            )
        lines.extend(
            [
                "",
                "### Selected Mode Counts",
                _count_table(teacher["selected_mode_counts"]),
                "",
                "### Verified Best Mode Counts",
                _count_table(teacher["verified_best_mode_counts"]),
                "",
                "### Plots",
            ]
        )
        for label, path in plot_paths.items():
            lines.append(f"- {label}: `{path}`")
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_plots(summaries: list[dict[str, Any]], plot_dir: Path) -> dict[str, str]:
    plot_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}
    outputs["accuracy_by_dataset"] = str(plot_dir / "routing_accuracy_by_dataset.png")
    _plot_accuracy_by_dataset(summaries, Path(outputs["accuracy_by_dataset"]))
    teacher = next((item for item in summaries if item["name"] == "phase4_opus_teacher"), None)
    if teacher:
        outputs["teacher_correct_vs_wrong"] = str(plot_dir / "phase4_teacher_correct_vs_wrong.png")
        outputs["teacher_selected_vs_best_counts"] = str(plot_dir / "phase4_teacher_selected_vs_best_counts.png")
        outputs["teacher_confusion"] = str(plot_dir / "phase4_teacher_confusion_selected_vs_best.png")
        outputs["teacher_regret_by_step"] = str(plot_dir / "phase4_teacher_regret_by_step.png")
        _plot_correct_wrong(teacher, Path(outputs["teacher_correct_vs_wrong"]))
        _plot_selected_vs_best_counts(teacher, Path(outputs["teacher_selected_vs_best_counts"]))
        _plot_confusion(teacher, Path(outputs["teacher_confusion"]))
        _plot_regret_by_step(teacher, Path(outputs["teacher_regret_by_step"]))
    return outputs


def _plot_accuracy_by_dataset(summaries: list[dict[str, Any]], path: Path) -> None:
    labels = [item["name"] for item in summaries]
    values = [float(item["accuracy_by_verified_best"] or 0.0) for item in summaries]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(labels, values, color="#3b82f6")
    ax.set_ylim(0, 1)
    ax.set_ylabel("accuracy")
    ax.set_title("Router top-1 correctness by dataset")
    ax.tick_params(axis="x", labelrotation=20)
    for bar, value in zip(bars, values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.2f}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_correct_wrong(summary: dict[str, Any], path: Path) -> None:
    values = [summary["correct_by_verified_best"], summary["incorrect_by_verified_best"]]
    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar(["correct", "incorrect"], values, color=["#16a34a", "#dc2626"])
    ax.set_ylabel("steps")
    ax.set_title("Phase 4 Opus: correct vs incorrect routing")
    for bar, value in zip(bars, values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.1, str(value), ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_selected_vs_best_counts(summary: dict[str, Any], path: Path) -> None:
    selected = [summary["selected_mode_counts"][mode] for mode in MODES]
    best = [summary["verified_best_mode_counts"][mode] for mode in MODES]
    x = list(range(len(MODES)))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar([value - width / 2 for value in x], selected, width=width, label="selected", color="#6366f1")
    ax.bar([value + width / 2 for value in x], best, width=width, label="verified best", color="#f59e0b")
    ax.set_xticks(x, MODES, rotation=20)
    ax.set_ylabel("steps")
    ax.set_title("Phase 4 Opus: selected modes vs verified-best modes")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_confusion(summary: dict[str, Any], path: Path) -> None:
    matrix = [[summary["confusion_selected_vs_verified_best"][selected][best] for best in MODES] for selected in MODES]
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(range(len(MODES)), MODES, rotation=30, ha="right")
    ax.set_yticks(range(len(MODES)), MODES)
    ax.set_xlabel("verified best mode")
    ax.set_ylabel("selected mode")
    ax.set_title("Phase 4 Opus: selected vs verified best")
    for y, row in enumerate(matrix):
        for x, value in enumerate(row):
            ax.text(x, y, str(value), ha="center", va="center", color="black")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_regret_by_step(summary: dict[str, Any], path: Path) -> None:
    rows = summary["rows"]
    labels = [f"{row['profile_id'].replace('_development', '')}:{row['step']}" for row in rows]
    values = [row["routing_regret"] for row in rows]
    colors = ["#16a34a" if value <= 1e-9 else "#dc2626" for value in values]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(labels, values, color=colors)
    ax.set_ylabel("routing regret")
    ax.set_title("Phase 4 Opus: regret by logged checkpoint")
    ax.tick_params(axis="x", labelrotation=45)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _count_table(counts: dict[str, int]) -> str:
    lines = ["| mode | count |", "| --- | ---: |"]
    for mode in MODES:
        lines.append(f"| `{mode}` | `{counts.get(mode, 0)}` |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary_out", default="artifacts/routing_choice_summary.json")
    parser.add_argument("--md_out", default="artifacts/routing_choice_visuals.md")
    parser.add_argument("--plot_dir", default="artifacts/plots")
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Dataset spec name=path. If omitted, known phase routing datasets are used when present.",
    )
    args = parser.parse_args(argv)
    specs = {}
    if args.dataset:
        for item in args.dataset:
            name, raw_path = item.split("=", 1)
            specs[name] = raw_path
    else:
        specs = DEFAULT_DATASETS
    summaries = []
    for name, raw_path in specs.items():
        path = Path(raw_path)
        if path.exists():
            summaries.append(summarize_dataset(name, path))
    plots = make_plots(summaries, Path(args.plot_dir))
    payload = {"datasets": summaries, "plots": plots}
    write_json(Path(args.summary_out), payload)
    write_report(summaries, Path(args.md_out), plots)
    print(json.dumps({"datasets": len(summaries), "summary_out": args.summary_out, "md_out": args.md_out}, indent=2))


if __name__ == "__main__":
    main()
