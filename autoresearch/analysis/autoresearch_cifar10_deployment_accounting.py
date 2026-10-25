"""Deployment-loss and log-effort accounting for AutoResearch CIFAR-10 runs."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vao.success_metrics import relative_improvement, success_on_relative_threshold

EPS = 1e-9


@dataclass(frozen=True)
class RunRecord:
    run_dir: Path
    run_id: str
    split: str
    mode: str
    seed: int | None
    worker: str
    baseline_loss: float
    best_loss: float | None
    final_loss: float | None
    success: bool
    tau_step: int | None
    steps_completed: int
    elapsed_wall_seconds: float
    total_tokens: int | None
    threshold_occupancy: float
    final_relative_improvement: float


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _manifest_mode(manifest: dict[str, Any]) -> str | None:
    mode = manifest.get("task_mode_true")
    if mode:
        return str(mode)
    overrides = (((manifest.get("config") or {}).get("benchmark") or {}).get("instance_overrides") or {})
    workloads = overrides.get("workloads") or overrides.get("families") or []
    return str(workloads[0]) if len(workloads) == 1 else None


def _step_records(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("steps/step_*/step_record.json")):
        rows.append(_load_json(path))
    return rows


def _final_selected_loss(rows: list[dict[str, Any]]) -> float | None:
    final: float | None = None
    for row in rows:
        selected = next((branch for branch in row.get("branches", []) if branch.get("promoted_as_parent")), None)
        if selected and selected.get("correctness") and math.isfinite(_coerce_float(selected.get("latent_loss"))):
            final = float(selected["latent_loss"])
    return final


def _total_tokens(rows: list[dict[str, Any]]) -> int | None:
    total = 0
    seen = False
    for row in rows:
        for key in ("total_tokens", "input_tokens", "output_tokens"):
            value = _coerce_int(row.get(key))
            if value is not None:
                total += value
                seen = True
    return total if seen else None


def load_runs(roots: list[Path], *, threshold: float) -> list[RunRecord]:
    records: list[RunRecord] = []
    for root in roots:
        for summary_path in sorted(root.glob("**/run_summary.json")):
            run_dir = summary_path.parent
            manifest_path = run_dir / "run_manifest.json"
            if not manifest_path.exists():
                continue
            manifest = _load_json(manifest_path)
            summary = _load_json(summary_path)
            mode = _manifest_mode(manifest)
            if not mode:
                continue
            rows = _step_records(run_dir)
            baseline = _coerce_float(summary.get("baseline_loss"))
            best = summary.get("best_visible_loss")
            best_loss = _coerce_float(best) if best is not None else None
            final_loss = _final_selected_loss(rows) or best_loss
            success = success_on_relative_threshold(baseline, best_loss, threshold=threshold)
            occupancy = statistics.fmean(1.0 if row.get("successful_step") else 0.0 for row in rows) if rows else 0.0
            records.append(
                RunRecord(
                    run_dir=run_dir,
                    run_id=str(summary.get("run_id") or run_dir.name),
                    split=str(manifest.get("task_mode_split") or manifest.get("workload_split") or "unspecified"),
                    mode=mode,
                    seed=_coerce_int(manifest.get("instance_seed")),
                    worker=str(manifest.get("model_alias") or "unknown_worker"),
                    baseline_loss=baseline,
                    best_loss=best_loss,
                    final_loss=final_loss,
                    success=success,
                    tau_step=_coerce_int(summary.get("tau_step")),
                    steps_completed=int(summary.get("steps_completed") or len(rows)),
                    elapsed_wall_seconds=_coerce_float(summary.get("elapsed_wall_seconds"), 0.0),
                    total_tokens=_total_tokens(rows),
                    threshold_occupancy=occupancy,
                    final_relative_improvement=relative_improvement(baseline, final_loss),
                )
            )
    return records


def deployment_loss(
    record: RunRecord,
    *,
    alpha_fail: float,
    alpha_occ: float,
    alpha_qual: float,
    lambda_wall: float,
    lambda_tokens: float,
) -> float:
    failure = 0.0 if record.success else 1.0
    occupancy_penalty = 1.0 - record.threshold_occupancy
    quality_penalty = 1.0 - max(0.0, min(1.0, record.final_relative_improvement))
    token_cost = float(record.total_tokens or 0)
    return (
        alpha_fail * failure
        + alpha_occ * occupancy_penalty
        + alpha_qual * quality_penalty
        + lambda_wall * record.elapsed_wall_seconds
        + lambda_tokens * token_cost
    )


def summarize_frontier(records: list[RunRecord], losses: dict[str, float]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[RunRecord]] = {}
    for record in records:
        grouped.setdefault((record.mode, record.worker), []).append(record)
    rows: list[dict[str, Any]] = []
    for (mode, worker), items in sorted(grouped.items()):
        successes = sum(1 for item in items if item.success)
        n = len(items)
        p_raw = successes / n if n else math.nan
        p_smooth = (successes + 0.5) / (n + 1.0)
        hit_costs = [item.elapsed_wall_seconds if item.tau_step is None else item.elapsed_wall_seconds * max(item.tau_step, 1) / max(item.steps_completed, 1) for item in items]
        kappa = statistics.median(hit_costs) if hit_costs else math.inf
        objective = math.log(max(kappa, EPS)) - math.log(max(p_smooth, EPS))
        rows.append(
            {
                "mode": mode,
                "worker": worker,
                "run_count": n,
                "success_count": successes,
                "p_raw": p_raw,
                "p_jeffreys": p_smooth,
                "kappa_wall_median": kappa,
                "mean_tau": statistics.fmean(item.tau_step for item in items if item.tau_step is not None) if any(item.tau_step is not None for item in items) else None,
                "mean_occupancy": statistics.fmean(item.threshold_occupancy for item in items),
                "mean_final_relative_improvement": statistics.fmean(item.final_relative_improvement for item in items),
                "mean_deployment_loss": statistics.fmean(losses[item.run_id] for item in items),
                "log_effort_objective": objective,
            }
        )
    return rows


def _bootstrap_ci(values: list[float], *, rng: random.Random, samples: int) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "lo": None, "hi": None}
    draws = []
    for _ in range(samples):
        draw = [rng.choice(values) for _ in values]
        draws.append(statistics.fmean(draw))
    draws.sort()
    lo = draws[int(0.025 * (samples - 1))]
    hi = draws[int(0.975 * (samples - 1))]
    return {"mean": statistics.fmean(values), "lo": lo, "hi": hi}


def deployment_summary(records: list[RunRecord], losses: dict[str, float], *, bootstrap_samples: int) -> list[dict[str, Any]]:
    rng = random.Random(20260505)
    grouped: dict[tuple[str, str], list[float]] = {}
    for record in records:
        grouped.setdefault((record.mode, record.worker), []).append(losses[record.run_id])
    return [
        {"mode": mode, "worker": worker, "deployment_loss_ci": _bootstrap_ci(values, rng=rng, samples=bootstrap_samples), "run_count": len(values)}
        for (mode, worker), values in sorted(grouped.items())
    ]


def router_residuals(router_decisions: Path | None, frontier_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if router_decisions is None or not router_decisions.exists():
        return []
    score = {(row["mode"], row["worker"]): float(row["log_effort_objective"]) for row in frontier_rows}
    best = {}
    for row in frontier_rows:
        mode = row["mode"]
        best[mode] = min(best.get(mode, math.inf), float(row["log_effort_objective"]))
    rows: list[dict[str, Any]] = []
    for raw in router_decisions.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        item = json.loads(raw)
        output = item.get("router_output") or {}
        worker = output.get("selected_agent_model") or output.get("selected_worker")
        mode = ((item.get("instance") or {}).get("workload_id") or (item.get("signal_record") or {}).get("instance", {}).get("workload_id"))
        if not worker or not mode or (mode, worker) not in score:
            continue
        rows.append(
            {
                "signal_level": item.get("signal_level"),
                "negative_control": item.get("negative_control"),
                "mode": mode,
                "selected_worker": worker,
                "log_effort_regret": score[(mode, worker)] - best[mode],
                "confidence": output.get("confidence"),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_roots", nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--router-decisions", default=None)
    parser.add_argument("--threshold", type=float, default=0.10)
    parser.add_argument("--alpha-fail", type=float, default=1.0)
    parser.add_argument("--alpha-occ", type=float, default=0.25)
    parser.add_argument("--alpha-qual", type=float, default=0.25)
    parser.add_argument("--lambda-wall", type=float, default=1.0 / 1800.0)
    parser.add_argument("--lambda-tokens", type=float, default=0.0)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    args = parser.parse_args(argv)

    records = load_runs([Path(root) for root in args.run_roots], threshold=args.threshold)
    losses = {
        record.run_id: deployment_loss(
            record,
            alpha_fail=args.alpha_fail,
            alpha_occ=args.alpha_occ,
            alpha_qual=args.alpha_qual,
            lambda_wall=args.lambda_wall,
            lambda_tokens=args.lambda_tokens,
        )
        for record in records
    }
    frontier = summarize_frontier(records, losses)
    report = {
        "weights": {
            "alpha_fail": args.alpha_fail,
            "alpha_occ": args.alpha_occ,
            "alpha_qual": args.alpha_qual,
            "lambda_wall": args.lambda_wall,
            "lambda_tokens": args.lambda_tokens,
            "threshold": args.threshold,
        },
        "run_count": len(records),
        "frontier": frontier,
        "deployment_loss_summary": deployment_summary(records, losses, bootstrap_samples=args.bootstrap_samples),
        "router_residuals": router_residuals(Path(args.router_decisions) if args.router_decisions else None, frontier),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    print(json.dumps({"output": str(output), "run_count": len(records)}, indent=2))


if __name__ == "__main__":
    main()
