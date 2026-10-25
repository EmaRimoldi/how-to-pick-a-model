"""Compute factored certified-resource calibration tables for AutoResearch."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Any


GAMMA = 0.05
DELTA = 0.10
LAMBDA_WALL = 1.0 / 1800.0
LAMBDA_TOKENS = 1.0 / 1_000_000.0


def load_analysis_module(repo_root: Path):
    path = repo_root / "scripts" / "analyze_autoresearch_threeworker_final.py"
    spec = importlib.util.spec_from_file_location("threeworker_analysis", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def empirical_t(values: list[float], delta: float) -> float:
    xs = sorted(values)
    if not xs:
        return math.inf
    k = math.ceil((1.0 - delta) * len(xs))
    return xs[k - 1]


def step_records(analysis, row: dict[str, Any]) -> list[dict[str, Any]]:
    return analysis.step_records(Path(row["run_dir"]))


def first_hit_step(analysis, row: dict[str, Any], gamma: float) -> float:
    tau = analysis.first_hit_step(row["baseline_loss"], row["best_losses_by_step"], gamma)
    return float(tau) if tau is not None else math.inf


def first_hit_wall(analysis, row: dict[str, Any], gamma: float) -> float:
    stat = analysis.row_at_threshold(row, gamma, LAMBDA_WALL)
    return float(stat["c_gamma"]) if stat["success"] else math.inf


def first_hit_tokens_m(analysis, row: dict[str, Any], gamma: float) -> float:
    tau = analysis.first_hit_step(row["baseline_loss"], row["best_losses_by_step"], gamma)
    if tau is None:
        return math.inf
    steps = step_records(analysis, row)
    return LAMBDA_TOKENS * sum(int(step.get("total_tokens") or 0) for step in steps[:tau])


def finite_or_none(value: float) -> float | None:
    return None if math.isinf(value) or math.isnan(value) else value


def select_per_cell(analysis, rows: list[dict[str, Any]], n: int | None) -> list[dict[str, Any]]:
    if n is None:
        return rows
    selected: list[dict[str, Any]] = []
    for mode in analysis.MODES:
        for worker in analysis.WORKERS:
            cell = [row for row in rows if row["mode"] == mode and row["worker"] == worker]
            selected.extend(cell[:n])
    return selected


def compute_tables(analysis, rows: list[dict[str, Any]], gamma: float, delta: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kappa: dict[str, dict[str, float]] = {}
    for worker in analysis.WORKERS:
        cell = [row for row in rows if row["worker"] == worker]
        wall_per_step = [
            float(row["elapsed_wall_seconds"]) / max(int(row["steps_completed"]), 1)
            for row in cell
            if float(row.get("elapsed_wall_seconds") or 0.0) > 0
        ]
        token_per_step = [
            float(row["total_tokens"]) / max(int(row["steps_completed"]), 1)
            for row in cell
            if int(row.get("total_tokens") or 0) > 0
        ]
        kappa[worker] = {
            "wall_seconds_per_step_mean": fmean(wall_per_step) if wall_per_step else math.inf,
            "wall_seconds_per_step_median": median(wall_per_step) if wall_per_step else math.inf,
            "tokens_per_step_mean": fmean(token_per_step) if token_per_step else math.inf,
            "tokens_per_step_median": median(token_per_step) if token_per_step else math.inf,
        }

    out: list[dict[str, Any]] = []
    for mode in analysis.MODES:
        for worker in analysis.WORKERS:
            cell = [row for row in rows if row["mode"] == mode and row["worker"] == worker]
            taus = [first_hit_step(analysis, row, gamma) for row in cell]
            t0_step = empirical_t(taus, delta)
            mode_wall_per_step = [
                float(row["elapsed_wall_seconds"]) / max(int(row["steps_completed"]), 1)
                for row in cell
                if float(row.get("elapsed_wall_seconds") or 0.0) > 0
            ]
            mode_token_per_step = [
                float(row["total_tokens"]) / max(int(row["steps_completed"]), 1)
                for row in cell
                if int(row.get("total_tokens") or 0) > 0
            ]
            mode_wall_kappa = median(mode_wall_per_step) if mode_wall_per_step else math.inf
            mode_token_kappa = median(mode_token_per_step) if mode_token_per_step else math.inf
            factored_wall = LAMBDA_WALL * kappa[worker]["wall_seconds_per_step_median"] * t0_step
            factored_tokens = LAMBDA_TOKENS * kappa[worker]["tokens_per_step_median"] * t0_step
            factored_mode_wall = LAMBDA_WALL * mode_wall_kappa * t0_step
            factored_mode_tokens = LAMBDA_TOKENS * mode_token_kappa * t0_step
            end_to_end_wall = empirical_t([first_hit_wall(analysis, row, gamma) for row in cell], delta)
            end_to_end_tokens = empirical_t([first_hit_tokens_m(analysis, row, gamma) for row in cell], delta)
            out.append(
                {
                    "mode": mode,
                    "mode_label": analysis.MODE_LABELS[mode],
                    "agent_system": worker,
                    "agent_system_label": analysis.WORKER_LABELS[worker],
                    "n": len(cell),
                    "successes": sum(math.isfinite(value) for value in taus),
                    "gamma": gamma,
                    "delta_cert": delta,
                    "kappa_wall_seconds_per_step_median": finite_or_none(kappa[worker]["wall_seconds_per_step_median"]),
                    "kappa_tokens_per_step_median": finite_or_none(kappa[worker]["tokens_per_step_median"]),
                    "kappa_wall_seconds_per_step_mode_median": finite_or_none(mode_wall_kappa),
                    "kappa_tokens_per_step_mode_median": finite_or_none(mode_token_kappa),
                    "t0_step_quantile": finite_or_none(t0_step),
                    "factored_wall_resource": finite_or_none(factored_wall),
                    "factored_token_resource_millions": finite_or_none(factored_tokens),
                    "factored_mode_wall_resource": finite_or_none(factored_mode_wall),
                    "factored_mode_token_resource_millions": finite_or_none(factored_mode_tokens),
                    "end_to_end_wall_resource": finite_or_none(end_to_end_wall),
                    "end_to_end_token_resource_millions": finite_or_none(end_to_end_tokens),
                }
            )
    return out, {"kappa": kappa}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", default="autoresearch/campaigns/h20_delta005_20260505")
    parser.add_argument("--output-dir", default="autoresearch/campaigns/h20_delta005_20260505/accounting/factored_calibration")
    parser.add_argument("--total-per-cell", type=int, default=30)
    parser.add_argument("--calibration-per-cell", type=int, default=None)
    parser.add_argument("--gamma", type=float, default=GAMMA)
    parser.add_argument("--delta-cert", type=float, default=DELTA)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    analysis = load_analysis_module(repo_root)
    rows, selection = analysis.load_pooled_runs(
        Path(args.campaign_root),
        pilot_per_cell=10,
        holdout_per_cell=25,
        total_per_cell=args.total_per_cell,
    )
    rows = select_per_cell(analysis, rows, args.calibration_per_cell)
    table, meta = compute_tables(analysis, rows, args.gamma, args.delta_cert)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "factored_calibration_table.csv", table)
    payload = {
        "gamma": args.gamma,
        "delta_cert": args.delta_cert,
        "total_per_cell": args.total_per_cell,
        "calibration_per_cell": args.calibration_per_cell,
        "selection": selection,
        "meta": meta,
        "table": table,
    }
    (out_dir / "factored_calibration_table.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(out_dir), "rows": len(table)}, indent=2))


if __name__ == "__main__":
    main()
