"""Compare iterative policy analyses such as top1 versus fixed-mode runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def compare_policies(
    analyses: dict[str, Path],
    *,
    out_dir: Path,
    success_kind: str,
    tau: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trajectory_frames: list[pd.DataFrame] = []
    curve_rows: list[dict[str, Any]] = []
    horizon_key = f"{success_kind}::tau={tau:.3f}"
    summary_rows: list[dict[str, Any]] = []

    for label, analysis_dir in analyses.items():
        trajectory_path = analysis_dir / "trajectory_summary.csv"
        json_path = analysis_dir / "iterative_analysis.json"
        if not trajectory_path.exists() or not json_path.exists():
            raise FileNotFoundError(f"Expected trajectory_summary.csv and iterative_analysis.json in {analysis_dir}")
        trajectory = pd.read_csv(trajectory_path)
        trajectory["policy_label"] = label
        trajectory_frames.append(trajectory)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        curves = payload.get("curves", {}).get(horizon_key, {})
        recommendation = payload.get("recommended_horizons", {}).get(horizon_key, {})
        for horizon_text, row in curves.items():
            curve_rows.append(
                {
                    "policy_label": label,
                    "horizon": int(horizon_text),
                    "oracle_router_holdout_objective": float(row["oracle_router_holdout_objective"]),
                    "pilot_router_holdout_objective": float(row["pilot_router_holdout_objective"]),
                    "single_best_model_holdout_objective": float(row["single_best_model_holdout_objective"]),
                }
            )
        summary_rows.append(
            {
                "policy_label": label,
                "recommended_horizon": recommendation.get("recommended_horizon"),
                "best_horizon": recommendation.get("best_horizon"),
                "best_oracle_objective": recommendation.get("best_oracle_objective"),
            }
        )

    trajectory_frame = pd.concat(trajectory_frames, ignore_index=True)
    curve_frame = pd.DataFrame(curve_rows).sort_values(["policy_label", "horizon"])
    summary_frame = pd.DataFrame(summary_rows).sort_values("policy_label")

    trajectory_frame.to_csv(out_dir / "policy_trajectory_summary.csv", index=False)
    curve_frame.to_csv(out_dir / "policy_curve_summary.csv", index=False)
    summary_frame.to_csv(out_dir / "policy_horizon_summary.csv", index=False)

    _plot_best_improvement(trajectory_frame, path=out_dir / "policy_best_improvement.png")
    _plot_objectives(curve_frame, summary_frame, path=out_dir / "policy_objectives.png")
    _write_report(summary_frame, trajectory_frame, horizon_key, out_dir / "report.md")

    result = {
        "success_kind": success_kind,
        "tau": tau,
        "policies": summary_frame.to_dict(orient="records"),
    }
    (out_dir / "policy_compare.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _plot_best_improvement(frame: pd.DataFrame, *, path: Path) -> None:
    aggregated = (
        frame.groupby(["policy_label", "split"], as_index=False)
        .agg(
            mean_best_relative_improvement=("best_so_far_relative_improvement", "mean"),
            mean_terminal_relative_improvement=("terminal_relative_improvement", "mean"),
        )
        .sort_values(["split", "policy_label"])
    )
    if aggregated.empty:
        return
    splits = list(dict.fromkeys(aggregated["split"]))
    labels = list(dict.fromkeys(aggregated["policy_label"]))
    width = 0.35
    x = list(range(len(labels)))
    fig, axes = plt.subplots(len(splits), 1, figsize=(8.5, 3.2 * len(splits)), squeeze=False)
    for axis, split in zip(axes[:, 0], splits):
        subset = aggregated.loc[aggregated["split"] == split].set_index("policy_label").reindex(labels)
        axis.bar([item - width / 2 for item in x], subset["mean_best_relative_improvement"], width=width, label="best-so-far")
        axis.bar([item + width / 2 for item in x], subset["mean_terminal_relative_improvement"], width=width, label="terminal")
        axis.set_xticks(x, labels, rotation=20, ha="right")
        axis.set_ylabel("relative improvement")
        axis.set_title(split)
        axis.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_objectives(curve_frame: pd.DataFrame, summary_frame: pd.DataFrame, *, path: Path) -> None:
    if curve_frame.empty:
        return
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    for policy_label, subset in curve_frame.groupby("policy_label"):
        ax.plot(subset["horizon"], subset["oracle_router_holdout_objective"], marker="o", label=policy_label)
    for _, row in summary_frame.iterrows():
        if pd.notna(row["recommended_horizon"]):
            ax.axvline(float(row["recommended_horizon"]), color="#9ca3af", linestyle="--", linewidth=1.0)
    ax.set_xlabel("horizon")
    ax.set_ylabel("oracle holdout objective")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_report(summary_frame: pd.DataFrame, trajectory_frame: pd.DataFrame, horizon_key: str, path: Path) -> None:
    lines = [
        "# Policy Comparison",
        "",
        f"- Setting: `{horizon_key}`",
        "",
        "## Recommended Horizons",
        "",
    ]
    for _, row in summary_frame.iterrows():
        lines.append(
            f"- `{row['policy_label']}`: recommended_horizon=`{row['recommended_horizon']}`, "
            f"best_oracle_objective=`{row['best_oracle_objective']}`"
        )
    lines += [
        "",
        "## Trajectory Means",
        "",
    ]
    aggregated = (
        trajectory_frame.groupby(["policy_label", "split"], as_index=False)
        .agg(
            mean_best_relative_improvement=("best_so_far_relative_improvement", "mean"),
            mean_terminal_relative_improvement=("terminal_relative_improvement", "mean"),
        )
        .sort_values(["split", "policy_label"])
    )
    for _, row in aggregated.iterrows():
        lines.append(
            f"- `{row['split']}` / `{row['policy_label']}`: "
            f"best_rel=`{row['mean_best_relative_improvement']:.4f}`, "
            f"terminal_rel=`{row['mean_terminal_relative_improvement']:.4f}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_mapping(items: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected label=path; got {item!r}")
        label, path_text = item.split("=", 1)
        mapping[label] = Path(path_text)
    return mapping


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--analysis", nargs="+", required=True, help="One or more label=analysis_dir items.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--success-kind", default="anytime")
    parser.add_argument("--tau", type=float, default=0.05)
    args = parser.parse_args(argv)
    result = compare_policies(
        _parse_mapping(args.analysis),
        out_dir=Path(args.out_dir),
        success_kind=args.success_kind,
        tau=float(args.tau),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
