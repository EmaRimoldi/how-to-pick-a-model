"""Analyze SWE-bench orchestration traces under certified deployment loss."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from vao.swebench_orchestration.schemas import OrchestrationDesign, TraceStep

EPS = 1e-9


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _scalar_cost(row: TraceStep, weights: dict[str, float]) -> float:
    return row.scalar_cost(
        token_weight=weights["token"],
        wall_weight=weights["wall"],
        test_weight=weights["test"],
        api_weight=weights["api"],
    ) + weights["verifier_call"] * row.verifier_calls


def _complexity_by_orchestration(path: Path | None) -> dict[str, float]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    design = OrchestrationDesign.model_validate(payload)
    orchestration = design.orchestration
    return {orchestration.orchestration_id: orchestration.complexity.score()}


def _summarize_run(
    rows: list[TraceStep],
    *,
    weights: dict[str, float],
    alpha_fail: float,
) -> dict[str, Any]:
    rows = sorted(rows, key=lambda item: item.step)
    verified_steps = [item.step for item in rows if item.verified]
    tau = min(verified_steps) if verified_steps else None
    cutoff = tau if tau is not None else max((item.step for item in rows), default=0)
    prefix = [item for item in rows if item.step <= cutoff]
    total_cost = sum(_scalar_cost(item, weights) for item in prefix)
    wasted_cost = sum(_scalar_cost(item, weights) for item in prefix if not item.used_in_verified_path)
    return {
        "run_id": rows[0].run_id,
        "orchestration_id": rows[0].orchestration_id,
        "evidence_level": rows[0].evidence_level,
        "instance_id": rows[0].instance_id,
        "repo": rows[0].repo,
        "mode": rows[0].mode,
        "split": rows[0].split,
        "success": tau is not None,
        "tau_step": tau,
        "steps_observed": max((item.step for item in rows), default=0),
        "total_cost_to_tau_or_horizon": total_cost,
        "wasted_cost_to_tau_or_horizon": wasted_cost,
        "wasted_effort_ratio": wasted_cost / max(total_cost, EPS),
        "deployment_loss": (0.0 if tau is not None else alpha_fail) + total_cost,
        "tokens_to_tau_or_horizon": sum(item.total_tokens for item in prefix),
        "wall_seconds_to_tau_or_horizon": sum(item.wall_seconds for item in prefix),
        "test_seconds_to_tau_or_horizon": sum(item.test_seconds for item in prefix),
        "verifier_calls_to_tau_or_horizon": sum(item.verifier_calls for item in prefix),
    }


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
    return values[index]


def _summarize_cells(run_rows: list[dict[str, Any]], complexity: dict[str, float], *, delta: float) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in run_rows:
        groups[(row["evidence_level"], row["orchestration_id"], row["mode"])].append(row)
    cells: list[dict[str, Any]] = []
    for (evidence_level, orchestration_id, mode), rows in sorted(groups.items()):
        successes = [row for row in rows if row["success"]]
        tau_values = [float(row["tau_step"]) for row in successes if row["tau_step"] is not None]
        cost_values = [float(row["total_cost_to_tau_or_horizon"]) for row in rows]
        kappa = statistics.median(cost_values) if cost_values else math.inf
        t0 = _quantile(tau_values, 1.0 - delta)
        certified_resource = None if t0 is None else kappa * t0
        cells.append(
            {
                "evidence_level": evidence_level,
                "orchestration_id": orchestration_id,
                "mode": mode,
                "run_count": len(rows),
                "success_count": len(successes),
                "success_rate": len(successes) / len(rows) if rows else None,
                "kappa_median_cost": kappa,
                "t0_steps_quantile": t0,
                "certified_resource": certified_resource,
                "mean_deployment_loss": statistics.fmean(row["deployment_loss"] for row in rows),
                "mean_wasted_effort_ratio": statistics.fmean(row["wasted_effort_ratio"] for row in rows),
                "mean_verifier_calls": statistics.fmean(row["verifier_calls_to_tau_or_horizon"] for row in rows),
                "complexity_score": complexity.get(orchestration_id),
            }
        )
    return cells


def _frontier_by_mode(cells: list[dict[str, Any]]) -> dict[str, float]:
    frontier: dict[str, float] = {}
    for cell in cells:
        value = cell.get("certified_resource")
        if value is None:
            continue
        mode = str(cell["mode"])
        frontier[mode] = min(frontier.get(mode, math.inf), float(value))
    return frontier


def _imbalance(cells: list[dict[str, Any]], frontier: dict[str, float]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for cell in cells:
        value = cell.get("certified_resource")
        mode = str(cell["mode"])
        if value is None or mode not in frontier or frontier[mode] <= 0:
            continue
        grouped[(str(cell["evidence_level"]), str(cell["orchestration_id"]))].append(
            math.log(max(float(value), EPS) / max(frontier[mode], EPS))
        )
    rows: list[dict[str, Any]] = []
    for (evidence_level, orchestration_id), ratios in sorted(grouped.items()):
        rows.append(
            {
                "evidence_level": evidence_level,
                "orchestration_id": orchestration_id,
                "mode_count": len(ratios),
                "mean_log_frontier_ratio": statistics.fmean(ratios),
                "mode_imbalance_variance": statistics.pvariance(ratios) if len(ratios) > 1 else 0.0,
                "worst_log_frontier_ratio": max(ratios),
            }
        )
    return rows


def analyze(
    *,
    trace_path: Path,
    orchestration_design_path: Path | None,
    output_path: Path,
    delta: float,
    alpha_fail: float,
    weights: dict[str, float],
) -> dict[str, Any]:
    raw_rows = _read_jsonl(trace_path)
    steps = [TraceStep.model_validate(row) for row in raw_rows]
    runs: dict[str, list[TraceStep]] = defaultdict(list)
    for step in steps:
        runs[step.run_id].append(step)
    run_rows = [_summarize_run(rows, weights=weights, alpha_fail=alpha_fail) for rows in runs.values()]
    complexity = _complexity_by_orchestration(orchestration_design_path)
    cells = _summarize_cells(run_rows, complexity, delta=delta)
    frontier = _frontier_by_mode(cells)
    report = {
        "trace_path": str(trace_path),
        "orchestration_design_path": str(orchestration_design_path) if orchestration_design_path else None,
        "delta": delta,
        "alpha_fail": alpha_fail,
        "weights": weights,
        "run_summaries": sorted(run_rows, key=lambda row: row["run_id"]),
        "cell_summaries": cells,
        "mode_frontier": frontier,
        "imbalance": _imbalance(cells, frontier),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", required=True)
    parser.add_argument("--orchestration-design", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--delta", type=float, default=0.10)
    parser.add_argument("--alpha-fail", type=float, default=100.0)
    parser.add_argument("--token-weight", type=float, default=1.0 / 100_000.0)
    parser.add_argument("--wall-weight", type=float, default=1.0 / 3600.0)
    parser.add_argument("--test-weight", type=float, default=1.0 / 3600.0)
    parser.add_argument("--api-weight", type=float, default=1.0)
    parser.add_argument("--verifier-call-weight", type=float, default=0.05)
    args = parser.parse_args(argv)
    report = analyze(
        trace_path=Path(args.traces),
        orchestration_design_path=Path(args.orchestration_design) if args.orchestration_design else None,
        output_path=Path(args.output),
        delta=args.delta,
        alpha_fail=args.alpha_fail,
        weights={
            "token": args.token_weight,
            "wall": args.wall_weight,
            "test": args.test_weight,
            "api": args.api_weight,
            "verifier_call": args.verifier_call_weight,
        },
    )
    print(json.dumps({key: report[key] for key in ("mode_frontier", "imbalance")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
