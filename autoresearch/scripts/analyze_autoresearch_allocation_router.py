"""Analyze allocation-router outputs against mode labels and calibration tables."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

MODES = ["mlp_flat", "cnn_compact", "resnet_micro"]
WORKERS = ["gpt_5_3_codex", "gpt_5_4", "gpt_5_4_mini"]
EPS = 1e-12


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def load_router_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.is_dir():
            for child in sorted(path.glob("**/*.jsonl")):
                rows.extend(read_jsonl(child))
        else:
            rows.extend(read_jsonl(path))
    return rows


def load_calibration(path: Path, metric: str) -> dict[tuple[str, str], float]:
    key = {
        "factored_wall": "factored_wall_resource",
        "factored_tokens": "factored_token_resource_millions",
        "factored_mode_wall": "factored_mode_wall_resource",
        "factored_mode_tokens": "factored_mode_token_resource_millions",
        "end_to_end_wall": "end_to_end_wall_resource",
        "end_to_end_tokens": "end_to_end_token_resource_millions",
    }[metric]
    table: dict[tuple[str, str], float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw = row.get(key) or ""
            table[(row["mode"], row["agent_system"])] = float(raw) if raw else math.inf
    return table


def entropy(dist: dict[str, float]) -> float:
    return -sum(float(dist.get(mode, 0.0)) * math.log(max(float(dist.get(mode, 0.0)), EPS)) for mode in MODES)


def brier(dist: dict[str, float], true_mode: str) -> float:
    return sum((float(dist.get(mode, 0.0)) - (1.0 if mode == true_mode else 0.0)) ** 2 for mode in MODES)


def top_mode(dist: dict[str, float]) -> str:
    return max(MODES, key=lambda mode: float(dist.get(mode, 0.0)))


def top_mode_contains(dist: dict[str, float], mode: str, *, tol: float = 1e-6) -> bool:
    best = max(float(dist.get(candidate, 0.0)) for candidate in MODES)
    return float(dist.get(mode, 0.0)) >= best - tol


def allocation_scheduler_choice(
    posterior: dict[str, float],
    q: dict[str, float],
    table: dict[tuple[str, str], float],
) -> tuple[str, dict[str, float]]:
    scores: dict[str, float] = {}
    for worker in WORKERS:
        score = 0.0
        for mode in MODES:
            pi_mass = float(posterior.get(mode, 0.0))
            q_mass = float(q.get(mode, 0.0))
            if pi_mass <= EPS:
                continue
            if q_mass <= EPS:
                score = math.inf
                break
            score += pi_mass * table[(mode, worker)] / q_mass
        scores[worker] = score
    return min(scores, key=scores.get), scores


def posterior_worker_choice(
    posterior: dict[str, float],
    table: dict[tuple[str, str], float],
) -> tuple[str, dict[str, float]]:
    scores: dict[str, float] = {}
    for worker in WORKERS:
        scores[worker] = sum(float(posterior.get(mode, 0.0)) * table[(mode, worker)] for mode in MODES)
    return min(scores, key=scores.get), scores


def allocation_weighted_worker_choice(
    q: dict[str, float],
    table: dict[tuple[str, str], float],
) -> tuple[str, dict[str, float]]:
    scores: dict[str, float] = {}
    for worker in WORKERS:
        scores[worker] = sum(float(q.get(mode, 0.0)) * table[(mode, worker)] for mode in MODES)
    return min(scores, key=scores.get), scores


def realized_choice(true_mode: str, q: dict[str, float], table: dict[tuple[str, str], float]) -> tuple[str, dict[str, float]]:
    q_mass = float(q.get(true_mode, 0.0))
    scores = {
        worker: (table[(true_mode, worker)] / q_mass if q_mass > EPS else math.inf)
        for worker in WORKERS
    }
    return min(scores, key=scores.get), scores


def induced_choice(
    policy_rule: str,
    posterior: dict[str, float],
    q: dict[str, float],
    table: dict[tuple[str, str], float],
) -> tuple[str, dict[str, float]]:
    if policy_rule == "allocation_scheduler":
        return allocation_scheduler_choice(posterior, q, table)
    if policy_rule == "posterior_worker":
        return posterior_worker_choice(posterior, table)
    if policy_rule == "allocation_weighted_worker":
        return allocation_weighted_worker_choice(q, table)
    raise ValueError(f"unknown policy rule: {policy_rule}")


def summarize(values: list[float]) -> float | None:
    return fmean(values) if values else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("router_paths", nargs="+")
    parser.add_argument("--calibration-table", required=True)
    parser.add_argument(
        "--calibration-metric",
        default="factored_wall",
        choices=[
            "factored_wall",
            "factored_tokens",
            "factored_mode_wall",
            "factored_mode_tokens",
            "end_to_end_wall",
            "end_to_end_tokens",
        ],
    )
    parser.add_argument(
        "--policy-rule",
        default="allocation_scheduler",
        choices=["allocation_scheduler", "posterior_worker", "allocation_weighted_worker"],
        help=(
            "allocation_scheduler scores sum_s pi_z(s) C(M,s)/q_z(s); "
            "posterior_worker scores a hard worker choice by sum_s pi_z(s) C(M,s); "
            "allocation_weighted_worker uses sum_s q_z(s) C(M,s) as a descriptive audit."
        ),
    )
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()

    router_rows = load_router_rows([Path(path) for path in args.router_paths])
    calibration = load_calibration(Path(args.calibration_table), args.calibration_metric)

    diagnostics: list[dict[str, Any]] = []
    for row in router_rows:
        output = row.get("router_output") or {}
        posterior = output.get("mode_posterior") or {}
        allocation = output.get("mode_allocation") or {}
        true_mode = str(row.get("true_mode") or row.get("instance", {}).get("workload_id") or "")
        if true_mode not in MODES:
            continue
        induced, scores = induced_choice(args.policy_rule, posterior, allocation, calibration)
        realized, realized_scores = realized_choice(true_mode, allocation, calibration)
        direct = output.get("selected_agent_model")
        diagnostics.append(
            {
                "router_model_key": row.get("router_model_key"),
                "signal_level": row.get("signal_level"),
                "true_mode": true_mode,
                "seed": row.get("instance", {}).get("seed"),
                "posterior_top_mode": top_mode(posterior),
                "posterior_true_mass": float(posterior.get(true_mode, 0.0)),
                "posterior_entropy": entropy(posterior),
                "posterior_nll": -math.log(max(float(posterior.get(true_mode, 0.0)), EPS)),
                "posterior_brier": brier(posterior, true_mode),
                "allocation_top_mode": top_mode(allocation),
                "allocation_true_mass": float(allocation.get(true_mode, 0.0)),
                "allocation_entropy": entropy(allocation),
                "direct_agent_system": direct,
                "policy_rule": args.policy_rule,
                "induced_agent_system": induced,
                "direct_matches_induced": direct == induced,
                "realized_agent_system": realized,
                "realized_matches_induced": realized == induced,
                **{f"posterior_{mode}": float(posterior.get(mode, 0.0)) for mode in MODES},
                **{f"allocation_{mode}": float(allocation.get(mode, 0.0)) for mode in MODES},
                **{f"induced_score_{worker}": scores[worker] for worker in WORKERS},
                **{f"realized_score_{worker}": realized_scores[worker] for worker in WORKERS},
            }
        )

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in diagnostics:
        groups[(str(row["router_model_key"]), str(row["signal_level"]))].append(row)

    summary_rows: list[dict[str, Any]] = []
    for (router, signal), rows in sorted(groups.items()):
        n = len(rows)
        summary_rows.append(
            {
                "router_model_key": router,
                "signal_level": signal,
                "n": n,
                "posterior_top_mode_contains_true": summarize([
                    1.0 if top_mode_contains(
                        {mode: row[f"posterior_{mode}"] for mode in MODES},
                        row["true_mode"],
                    )
                    else 0.0
                    for row in rows
                ]),
                "allocation_top_mode_contains_true": summarize([
                    1.0 if top_mode_contains(
                        {mode: row[f"allocation_{mode}"] for mode in MODES},
                        row["true_mode"],
                    )
                    else 0.0
                    for row in rows
                ]),
                "mean_posterior_true_mass": summarize([row["posterior_true_mass"] for row in rows]),
                "mean_allocation_true_mass": summarize([row["allocation_true_mass"] for row in rows]),
                "mean_posterior_entropy": summarize([row["posterior_entropy"] for row in rows]),
                "mean_allocation_entropy": summarize([row["allocation_entropy"] for row in rows]),
                "mean_posterior_nll": summarize([row["posterior_nll"] for row in rows]),
                "mean_posterior_brier": summarize([row["posterior_brier"] for row in rows]),
                "direct_matches_induced_rate": summarize([1.0 if row["direct_matches_induced"] else 0.0 for row in rows]),
                "realized_matches_induced_rate": summarize([1.0 if row["realized_matches_induced"] else 0.0 for row in rows]),
                "direct_selection_counts": json.dumps(_counts(row["direct_agent_system"] for row in rows), sort_keys=True),
                "induced_selection_counts": json.dumps(_counts(row["induced_agent_system"] for row in rows), sort_keys=True),
                "realized_selection_counts": json.dumps(_counts(row["realized_agent_system"] for row in rows), sort_keys=True),
            }
        )

    output_json = Path(args.output_json)
    output_csv = Path(args.output_csv)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "calibration_table": str(args.calibration_table),
                "calibration_metric": args.calibration_metric,
                "policy_rule": args.policy_rule,
                "router_records": len(router_rows),
                "diagnostic_records": len(diagnostics),
                "summary": summary_rows,
                "diagnostics": diagnostics,
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]) if summary_rows else [])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(json.dumps({"output_json": str(output_json), "output_csv": str(output_csv), "records": len(diagnostics)}, indent=2))


def _counts(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value)
        out[key] = out.get(key, 0) + 1
    return out


if __name__ == "__main__":
    main()
