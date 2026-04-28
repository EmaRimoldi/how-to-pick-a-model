"""Sweep task-mode success thresholds and summarize routing regimes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from vao.analysis.task_mode_decomposition import analyze


def run_sweep(
    roots: list[Path],
    *,
    out_dir: Path,
    thresholds: list[float],
    success_mode: str,
    success_threshold: float,
    cost_metric: str,
    pilot_split: str,
    holdout_split: str,
    smaller_model: str,
    larger_model: str,
    task_prior_mode: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for threshold in thresholds:
        threshold_tag = str(threshold).replace(".", "p")
        result = analyze(
            roots,
            out_dir=out_dir / f"thr_{threshold_tag}",
            success_threshold=success_threshold,
            success_mode=success_mode,
            improvement_threshold=threshold,
            cost_metric=cost_metric,
            pilot_split=pilot_split,
            holdout_split=holdout_split,
            smaller_model=smaller_model,
            larger_model=larger_model,
            task_prior_mode=task_prior_mode,
        )
        holdout_best = result["triviality"]["holdout"]["best_model_by_task_mode"]
        rows.append(
            {
                "threshold": threshold,
                "holdout_routing_trivial": bool(result["triviality"]["holdout"]["routing_is_trivial_empirically"]),
                "pilot_routing_trivial": bool(result["triviality"]["pilot"]["routing_is_trivial_empirically"]),
                "holdout_best_range_local_scans": holdout_best.get("range_local_scans"),
                "holdout_best_topk_stress": holdout_best.get("topk_stress"),
                "pilot_router_holdout_objective": float(result["decomposition"]["pilot_router_holdout_objective"]),
                "oracle_router_holdout_objective": float(result["decomposition"]["oracle_router_holdout_objective"]),
                "single_best_model_holdout_objective": float(result["decomposition"]["single_best_model_holdout_objective"]),
                "pilot_information_gain_nats": float(result["decomposition"]["pilot_information_gain_nats"]),
                "pilot_router_mismatch_nats": float(result["decomposition"]["pilot_router_mismatch_nats"]),
                "cost_ratio": float(result["pairwise_crossover"]["cost_ratio"]),
                "aggregate_d_cross": float(result["pairwise_crossover"]["aggregate_d_cross"]),
            }
        )
    frame = pd.DataFrame(rows).sort_values("threshold")
    frame.to_csv(out_dir / "threshold_sweep.csv", index=False)
    (out_dir / "threshold_sweep.json").write_text(frame.to_json(orient="records", indent=2), encoding="utf-8")
    _plot_objectives(frame, out_dir / "threshold_objectives.png")
    _plot_triviality(frame, out_dir / "threshold_triviality.png")
    _write_report(frame, out_dir / "report.md")
    return frame


def _plot_objectives(frame: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(7, 4.5))
    plt.plot(frame["threshold"], frame["single_best_model_holdout_objective"], marker="o", label="single best model")
    plt.plot(frame["threshold"], frame["pilot_router_holdout_objective"], marker="o", label="pilot router")
    plt.plot(frame["threshold"], frame["oracle_router_holdout_objective"], marker="o", label="oracle router")
    plt.xlabel("Relative-improvement threshold")
    plt.ylabel("Holdout cost-adjusted objective")
    plt.title("Threshold Sweep: Holdout Objectives")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def _plot_triviality(frame: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(7, 4.5))
    trivial = frame["holdout_routing_trivial"].astype(int)
    plt.step(frame["threshold"], trivial, where="post", label="holdout routing trivial")
    for _, row in frame.iterrows():
        label = f"range={row['holdout_best_range_local_scans'].replace('gpt-5.3-', '')}\ntopk={row['holdout_best_topk_stress'].replace('gpt-5.3-', '')}"
        plt.annotate(label, (row["threshold"], trivial.loc[row.name]), textcoords="offset points", xytext=(4, 6), fontsize=7)
    plt.yticks([0, 1], ["non-trivial", "trivial"])
    plt.xlabel("Relative-improvement threshold")
    plt.ylabel("Holdout routing regime")
    plt.title("Threshold Sweep: Routing Triviality")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def _write_report(frame: pd.DataFrame, path: Path) -> None:
    first_non_trivial = frame.loc[~frame["holdout_routing_trivial"]].head(1)
    lines = [
        "# Threshold Sweep",
        "",
        f"- Thresholds swept: `{', '.join(f'{value:.2f}' for value in frame['threshold'])}`",
        f"- First non-trivial holdout threshold: `{first_non_trivial['threshold'].iloc[0] if not first_non_trivial.empty else 'none'}`",
        "",
        "## Holdout Regime By Threshold",
        "",
    ]
    for _, row in frame.iterrows():
        lines.append(
            f"- `tau={row['threshold']:.2f}`: trivial=`{bool(row['holdout_routing_trivial'])}`, "
            f"range=`{row['holdout_best_range_local_scans']}`, topk=`{row['holdout_best_topk_stress']}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--thresholds", default="0.0,0.05,0.1")
    parser.add_argument("--success-mode", choices=["relative_improvement"], default="relative_improvement")
    parser.add_argument("--success-threshold", type=float, default=0.95)
    parser.add_argument("--cost-metric", choices=["wall_seconds", "tokens", "usd"], default="wall_seconds")
    parser.add_argument("--pilot-split", default="pilot")
    parser.add_argument("--holdout-split", default="holdout")
    parser.add_argument("--smaller-model", required=True)
    parser.add_argument("--larger-model", required=True)
    parser.add_argument("--task-prior-mode", choices=["empirical", "uniform"], default="empirical")
    args = parser.parse_args(argv)
    frame = run_sweep(
        [Path(item) for item in args.runs],
        out_dir=Path(args.out_dir),
        thresholds=[float(item) for item in args.thresholds.split(",") if item.strip()],
        success_mode=args.success_mode,
        success_threshold=args.success_threshold,
        cost_metric=args.cost_metric,
        pilot_split=args.pilot_split,
        holdout_split=args.holdout_split,
        smaller_model=args.smaller_model,
        larger_model=args.larger_model,
        task_prior_mode=args.task_prior_mode,
    )
    print(frame.to_json(orient="records", indent=2))


if __name__ == "__main__":
    main()
