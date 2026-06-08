"""Summarize 20-step AutoResearch CIFAR-10 long-run comparisons."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _step_dirs(run_dir: Path) -> list[Path]:
    steps_dir = run_dir / "steps"
    if not steps_dir.exists():
        return []
    return sorted(path for path in steps_dir.iterdir() if path.is_dir() and path.name.startswith("step_"))


def _summarize_run(run_dir: Path) -> dict[str, Any]:
    run_summary = _load_json(run_dir / "run_summary.json")
    baseline_loss = float(run_summary["baseline_loss"])
    trajectories: list[dict[str, Any]] = []
    selected_counter: Counter[str] = Counter()
    top1_counter: Counter[str] = Counter()
    productive_counter: Counter[str] = Counter()
    mean_prob_accum: defaultdict[str, float] = defaultdict(float)
    mean_gain_accum: defaultdict[str, float] = defaultdict(float)
    best_visible = baseline_loss

    for step_dir in _step_dirs(run_dir):
        record = _load_json(step_dir / "step_record.json")
        selected_mode = str(record["selected_mode"])
        top1_mode = str(record["selected_mode_top1"])
        selected_counter[selected_mode] += 1
        top1_counter[top1_mode] += 1
        branches = record["branches"]
        positive_branches = [branch for branch in branches if float(branch["gain"]) > 0.0]
        best_branch = min(branches, key=lambda branch: float(branch["latent_loss"]))
        if float(best_branch["gain"]) > 0.0:
            productive_counter[str(best_branch["declared_mode"])] += 1
        for mode, prob in record["mode_probs"].items():
            mean_prob_accum[str(mode)] += float(prob)
        for branch in branches:
            mean_gain_accum[str(branch["declared_mode"])] += float(branch["gain"])
        selected_branch = next(branch for branch in branches if bool(branch["selected_as_visible"]))
        selected_loss = float(selected_branch["latent_loss"])
        best_visible = min(best_visible, selected_loss)
        trajectories.append(
            {
                "step": int(record["step"]),
                "parent_loss": float(record["parent_latent_loss"]),
                "selected_mode": selected_mode,
                "top1_mode": top1_mode,
                "selected_loss": selected_loss,
                "best_branch_mode": str(best_branch["declared_mode"]),
                "best_branch_loss": float(best_branch["latent_loss"]),
                "best_visible_so_far": best_visible,
                "positive_branch_count": len(positive_branches),
            }
        )

    step_count = max(len(trajectories), 1)
    action_modes = sorted(set(mean_prob_accum) | set(mean_gain_accum) | set(selected_counter) | set(productive_counter))
    action_summary = []
    for mode in action_modes:
        action_summary.append(
            {
                "mode": mode,
                "mean_prob": mean_prob_accum[mode] / step_count,
                "mean_gain": mean_gain_accum[mode] / step_count,
                "selected_count": selected_counter[mode],
                "top1_count": top1_counter[mode],
                "productive_count": productive_counter[mode],
            }
        )

    return {
        "run_dir": str(run_dir),
        "model_alias": _infer_model_alias(run_dir.name),
        "latent_mode": _infer_latent_mode(run_dir.name),
        "baseline_loss": baseline_loss,
        "final_best_visible_loss": best_visible,
        "improvement": baseline_loss - best_visible,
        "steps_completed": len(trajectories),
        "elapsed_wall_seconds": float(run_summary["elapsed_wall_seconds"]),
        "trajectories": trajectories,
        "action_summary": action_summary,
    }


def _infer_model_alias(run_name: str) -> str:
    return run_name.split("_seed", 1)[-1].split("_", 1)[-1]


def _infer_latent_mode(run_name: str) -> str:
    marker = "_holdout_"
    if marker not in run_name:
        return "unknown"
    tail = run_name.split(marker, 1)[1]
    return tail.rsplit("_seed", 1)[0]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    root = Path(args.root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_dirs = sorted(path for path in root.iterdir() if path.is_dir() and (path / "run_summary.json").exists())
    summaries = [_summarize_run(run_dir) for run_dir in run_dirs]
    (out_dir / "longrun_summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")

    trajectory_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    report_lines = ["# AutoResearch CIFAR-10 Long-Run Comparison", ""]
    for summary in summaries:
        report_lines.append(f"## {summary['latent_mode']} / {summary['model_alias']}")
        report_lines.append("")
        report_lines.append(
            f"- steps_completed: `{summary['steps_completed']}`; baseline_loss: `{summary['baseline_loss']:.6f}`; "
            f"best_visible_loss: `{summary['final_best_visible_loss']:.6f}`; improvement: `{summary['improvement']:.6f}`; "
            f"elapsed_wall_seconds: `{summary['elapsed_wall_seconds']:.2f}`"
        )
        best_action = max(summary["action_summary"], key=lambda row: row["selected_count"]) if summary["action_summary"] else None
        if best_action is not None:
            report_lines.append(
                f"- most-selected action mode: `{best_action['mode']}` (`{best_action['selected_count']}` selections, mean_gain `{best_action['mean_gain']:.6f}`)"
            )
        report_lines.append("")
        for row in summary["trajectories"]:
            trajectory_rows.append(
                {
                    "latent_mode": summary["latent_mode"],
                    "model_alias": summary["model_alias"],
                    **row,
                }
            )
        for row in summary["action_summary"]:
            action_rows.append(
                {
                    "latent_mode": summary["latent_mode"],
                    "model_alias": summary["model_alias"],
                    **row,
                }
            )

    _write_csv(out_dir / "trajectory.csv", trajectory_rows)
    _write_csv(out_dir / "action_modes.csv", action_rows)
    (out_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"run_count": len(summaries), "out_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
