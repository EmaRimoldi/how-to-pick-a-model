"""Phase F metrics computed from Step 1 raw logs.

Runners write raw traces under ``logs/``. This script is the only place that
derives reports and adaptation curves, so metrics are regenerable without
rerunning model or sandbox work.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from runners.common import ARTIFACT_DIR, LOGS_DIR, METRICS_DIR, gold_instance, load_humaneval, read_jsonl, write_json


GOLD_DIAGNOSTIC_MODULES = {
    "understand_spec": "oracles.check_understand_spec_gold",
    "generate_tests": "oracles.check_generate_tests_gold",
}


def _load_orchestration(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```yaml\n(.*?)\n```", text, re.S)
    if not match:
        raise ValueError(f"{path} does not contain a fenced YAML orchestration block")
    return yaml.safe_load(match.group(1))


def _structural_validity(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload["roles_and_dag"]["nodes"]
    node_ids = [node["id"] for node in nodes]
    node_set = set(node_ids)
    duplicate_nodes = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
    invalid_edges = [
        edge for edge in payload["roles_and_dag"]["edges"] if len(edge) != 2 or edge[0] not in node_set or edge[1] not in node_set
    ]
    terminal_nodes = [node["id"] for node in nodes if node["oracle"]["inference"]["kind"] == "terminal"]
    return {
        "passed": not duplicate_nodes and not invalid_edges and bool(terminal_nodes),
        "node_count": len(nodes),
        "edge_count": len(payload["roles_and_dag"]["edges"]),
        "duplicate_nodes": duplicate_nodes,
        "invalid_edges": invalid_edges,
        "terminal_nodes": terminal_nodes,
    }


def _group_by_run(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        runs[str(row["run_id"])].append(row)
    return dict(sorted(runs.items()))


def _run_summary(rows: list[dict[str, Any]], *, R: float, c: float) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: (row.get("task_id", ""), row.get("node_id", "")))
    task_id = str(rows[0].get("task_id", "unknown")) if rows else "unknown"
    total_T = sum(float(row.get("T_k", 0.0)) for row in rows)
    pass_value = any(bool(row.get("terminal_pass")) for row in rows)
    utility = R * int(pass_value) - c * total_T
    return {"task_id": task_id, "pass": pass_value, "T": total_T, "U": utility}


def _summaries(rows: list[dict[str, Any]], *, R: float, c: float) -> list[dict[str, Any]]:
    return [_run_summary(run_rows, R=R, c=c) for run_rows in _group_by_run(rows).values()]


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _proper_time(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(summaries)
    solved_times = sorted(float(row["T"]) for row in summaries if row["pass"])
    if not n:
        return {
            "instances": 0,
            "tau_bar": None,
            "Fbar_inf": 0.0,
            "best_budget_t": None,
            "curve": [],
        }
    curve = []
    best: dict[str, Any] | None = None
    unique_times = sorted(set(solved_times))
    for t in unique_times:
        solved_within = sum(1 for value in solved_times if value <= t)
        fbar = solved_within / n
        tau_candidate = t / fbar if fbar else None
        row = {
            "t": t,
            "solved_within_budget": solved_within,
            "Fbar_t": fbar,
            "t_over_Fbar_t": tau_candidate,
        }
        curve.append(row)
        if tau_candidate is not None and (best is None or tau_candidate < float(best["tau_bar"])):
            best = {"tau_bar": tau_candidate, "best_budget_t": t, "Fbar_at_best_t": fbar}
    return {
        "instances": n,
        "tau_bar": None if best is None else best["tau_bar"],
        "Fbar_inf": len(solved_times) / n,
        "best_budget_t": None if best is None else best["best_budget_t"],
        "Fbar_at_best_t": None if best is None else best["Fbar_at_best_t"],
        "curve": curve,
    }


def _utility_for_c(summaries: list[dict[str, Any]], *, R: float, c: float) -> float:
    return _mean([R * int(row["pass"]) - c * float(row["T"]) for row in summaries])


def _utility_c_sweep(
    orchestration: list[dict[str, Any]],
    baseline: list[dict[str, Any]],
    *,
    R: float,
) -> dict[str, Any]:
    c_values = [1e-6, 1e-5, 1e-4, 1e-3]
    rows = []
    for c_value in c_values:
        orch_u = _utility_for_c(orchestration, R=R, c=c_value)
        base_u = _utility_for_c(baseline, R=R, c=c_value)
        if orch_u > base_u:
            winner = "orchestration"
        elif base_u > orch_u:
            winner = "single_agent_baseline"
        else:
            winner = "tie"
        rows.append(
            {
                "c": c_value,
                "orchestration_mean_U": orch_u,
                "baseline_mean_U": base_u,
                "winner": winner,
            }
        )
    orch_pass = _mean([float(row["pass"]) for row in orchestration])
    base_pass = _mean([float(row["pass"]) for row in baseline])
    orch_t = _mean([float(row["T"]) for row in orchestration])
    base_t = _mean([float(row["T"]) for row in baseline])
    delta_pass_reward = R * (orch_pass - base_pass)
    delta_t = orch_t - base_t
    flip_c = None
    if delta_t:
        candidate = delta_pass_reward / delta_t
        if candidate > 0:
            flip_c = candidate
    return {
        "rows": rows,
        "flip_c": flip_c,
        "delta_pass_reward": delta_pass_reward,
        "delta_mean_T": delta_t,
        "note": "flip_c is the positive c where orchestration and baseline mean U are equal, if it exists.",
    }


def _per_node_cost_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("node_id", "unknown"))].append(row)
    summary: dict[str, Any] = {}
    for node_id, node_rows in sorted(grouped.items()):
        summary[node_id] = {
            "observations": len(node_rows),
            "mean_T_k": _mean([float(row.get("T_k", 0.0)) for row in node_rows]),
            "mean_prompt_tokens": _mean([float(row.get("tokens_in", 0.0)) for row in node_rows]),
            "mean_completion_tokens": _mean([float(row.get("tokens_out", 0.0)) for row in node_rows]),
            "mean_calls": _mean([float(row.get("calls", 0.0)) for row in node_rows]),
            "mean_wall_ms": _mean([float(row.get("wall_ms", 0.0)) for row in node_rows]),
        }
    return summary


def _oracle_discrimination(payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    node_oracle_kind = {
        node["id"]: node["oracle"]["inference"]["kind"] for node in payload["roles_and_dag"]["nodes"]
    }
    case1_nodes = {
        node_id for node_id, kind in node_oracle_kind.items() if kind == "code"
    }
    statuses: dict[str, set[bool]] = {node_id: set() for node_id in case1_nodes}
    observed_counts: dict[str, int] = {node_id: 0 for node_id in case1_nodes}
    for row in rows:
        node_id = row.get("node_id")
        if node_id not in statuses:
            continue
        value = row.get("oracle_passed")
        if value is None:
            continue
        statuses[str(node_id)].add(bool(value))
        observed_counts[str(node_id)] += 1
    discriminating = {
        node_id: statuses[node_id] == {False, True} for node_id in sorted(case1_nodes)
    }
    fraction = (
        sum(1 for value in discriminating.values() if value) / len(node_oracle_kind)
        if node_oracle_kind
        else 0.0
    )
    case1_fraction = (
        sum(1 for value in discriminating.values() if value) / len(case1_nodes)
        if case1_nodes
        else 0.0
    )
    return {
        "inference_oracle_discriminating_fraction": fraction,
        "case1_code_oracle_discriminating_fraction": case1_fraction,
        "case1_code_nodes": sorted(case1_nodes),
        "node_statuses": {
            node_id: {
                "observed_values": sorted(statuses[node_id]),
                "observed_count": observed_counts[node_id],
                "discriminates": discriminating[node_id],
            }
            for node_id in sorted(case1_nodes)
        },
    }


def _gold_diagnostic_agreement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    gold_rows = {row["task_id"]: gold_instance(row) for row in load_humaneval()}
    modules = {
        node_id: importlib.import_module(module_name)
        for node_id, module_name in GOLD_DIAGNOSTIC_MODULES.items()
    }
    totals: dict[str, int] = {node_id: 0 for node_id in modules}
    agreements: dict[str, int] = {node_id: 0 for node_id in modules}
    errors: dict[str, list[str]] = {node_id: [] for node_id in modules}
    for row in rows:
        node_id = str(row.get("node_id"))
        if node_id not in modules:
            continue
        inference_value = row.get("oracle_passed")
        if inference_value is None:
            continue
        task_id = str(row["task_id"])
        try:
            diagnostic = modules[node_id].check(gold_rows[task_id], row.get("state", {}))
            gold_value = bool(diagnostic.get("passed"))
        except Exception as exc:  # pragma: no cover - diagnostics should not crash metrics.
            errors[node_id].append(f"{task_id}:{type(exc).__name__}:{exc}")
            continue
        totals[node_id] += 1
        agreements[node_id] += int(bool(inference_value) == gold_value)
    return {
        node_id: {
            "available": True,
            "count": totals[node_id],
            "agreement_rate": agreements[node_id] / totals[node_id] if totals[node_id] else None,
            "errors": errors[node_id][:10],
        }
        for node_id in sorted(modules)
    }


def _adaptation_curve(orchestration: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index in range(1, len(orchestration) + 1):
        orch_prefix = orchestration[:index]
        base_prefix = baseline[: min(index, len(baseline))]
        rows.append(
            {
                "instances_seen": index,
                "orchestration_pass_at_1": sum(1 for row in orch_prefix if row["pass"]) / len(orch_prefix),
                "orchestration_mean_U": _mean([float(row["U"]) for row in orch_prefix]),
                "baseline_pass_at_1": sum(1 for row in base_prefix if row["pass"]) / len(base_prefix) if base_prefix else 0.0,
                "baseline_mean_U": _mean([float(row["U"]) for row in base_prefix]),
            }
        )
    return rows


def compute(
    *,
    orchestration_path: Path,
    orchestration_traces_path: Path,
    baseline_traces_path: Path,
    report_output: Path,
    curve_output: Path,
) -> dict[str, Any]:
    payload = _load_orchestration(orchestration_path)
    structural = _structural_validity(payload)
    cost = payload["cost_success"]
    R = float(cost["R"])
    c = float(cost["c"])
    orchestration_rows = read_jsonl(orchestration_traces_path)
    baseline_rows = read_jsonl(baseline_traces_path)
    oracle = _oracle_discrimination(payload, orchestration_rows)
    gold_agreement = _gold_diagnostic_agreement(orchestration_rows)
    orch_summaries = _summaries(orchestration_rows, R=R, c=c)
    base_summaries = _summaries(baseline_rows, R=R, c=c)
    orch_mean_U = _mean([float(row["U"]) for row in orch_summaries])
    base_mean_U = _mean([float(row["U"]) for row in base_summaries])
    proper_time = {
        "definition": "tau_bar = inf_t t / Fbar(t), where Fbar(t) is solved-within-budget fraction over logged runs.",
        "canonical_solution_used": False,
        "orchestration": _proper_time(orch_summaries),
        "single_agent_baseline": _proper_time(base_summaries),
    }
    orch_tau = proper_time["orchestration"]["tau_bar"]
    base_tau = proper_time["single_agent_baseline"]["tau_bar"]
    if orch_tau is not None and base_tau is not None:
        proper_time["winner_lower_tau_bar"] = "orchestration" if orch_tau < base_tau else "single_agent_baseline" if base_tau < orch_tau else "tie"
    else:
        proper_time["winner_lower_tau_bar"] = None
    c_sweep = _utility_c_sweep(orch_summaries, base_summaries, R=R)
    report = {
        "schema_version": 1,
        "phase": "F",
        "source_logs": {
            "orchestration": str(orchestration_traces_path),
            "baseline": str(baseline_traces_path),
        },
        "cost_success": {
            "R": R,
            "c": c,
            "U": "R * pass - c * sum(T_k)",
            "notation": "U(h) = R·1[pass] − c·T(h), T(h) = Σ T_k",
        },
        "phase_f_results": {
            "structural_validity": structural,
            "inference_oracles_discriminate": {
                "passed": oracle["inference_oracle_discriminating_fraction"] > 0.0,
                **oracle,
            },
            "beats_single_agent_baseline_on_EU": {
                "passed": orch_mean_U > base_mean_U,
                "orchestration_mean_U": orch_mean_U,
                "baseline_mean_U": base_mean_U,
            },
            "gold_diagnostic_agreement": gold_agreement,
        },
        "inference_oracle_discriminating_fraction": oracle["inference_oracle_discriminating_fraction"],
        "orchestration": {
            "instances": len(orch_summaries),
            "pass_at_1": sum(1 for row in orch_summaries if row["pass"]) / len(orch_summaries) if orch_summaries else 0.0,
            "mean_U": orch_mean_U,
            "per_node_cost": _per_node_cost_summary(orchestration_rows),
        },
        "single_agent_baseline": {
            "instances": len(base_summaries),
            "pass_at_1": sum(1 for row in base_summaries if row["pass"]) / len(base_summaries) if base_summaries else 0.0,
            "mean_U": base_mean_U,
            "per_node_cost": _per_node_cost_summary(baseline_rows),
        },
        "proper_time_diagnostic": proper_time,
        "utility_c_sweep": c_sweep,
        "canonical_solution_usage_audit": {
            "live_solving_uses_canonical_solution": False,
            "gold_diagnostics_are_offline_only": True,
        },
        "note": (
            "A mock-completion smoke run is expected not to satisfy performance checks. "
            "Run the operator command in PROGRESS.md with real completions for Phase-F production results."
        ),
    }
    curve = {
        "schema_version": 1,
        "source_logs": report["source_logs"],
        "points": _adaptation_curve(orch_summaries, base_summaries),
    }
    write_json(report_output, report)
    write_json(curve_output, curve)
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orchestration", default=str(ARTIFACT_DIR / "orchestration.md"))
    parser.add_argument("--orchestration-traces", default=str(LOGS_DIR / "online_loop_traces.jsonl"))
    parser.add_argument("--baseline-traces", default=str(LOGS_DIR / "baseline_traces.jsonl"))
    parser.add_argument("--report-output", default=str(METRICS_DIR / "step1_report.json"))
    parser.add_argument("--curve-output", default=str(METRICS_DIR / "adaptation_curve.json"))
    args = parser.parse_args(argv)
    report = compute(
        orchestration_path=Path(args.orchestration),
        orchestration_traces_path=Path(args.orchestration_traces),
        baseline_traces_path=Path(args.baseline_traces),
        report_output=Path(args.report_output),
        curve_output=Path(args.curve_output),
    )
    print(
        json.dumps(
            {
                "inference_oracle_discriminating_fraction": report["inference_oracle_discriminating_fraction"],
                "phase_f_results": report["phase_f_results"],
                "proper_time_diagnostic": {
                    "orchestration_tau_bar": report["proper_time_diagnostic"]["orchestration"]["tau_bar"],
                    "baseline_tau_bar": report["proper_time_diagnostic"]["single_agent_baseline"]["tau_bar"],
                    "winner_lower_tau_bar": report["proper_time_diagnostic"]["winner_lower_tau_bar"],
                    "orchestration_Fbar_inf": report["proper_time_diagnostic"]["orchestration"]["Fbar_inf"],
                    "baseline_Fbar_inf": report["proper_time_diagnostic"]["single_agent_baseline"]["Fbar_inf"],
                },
                "utility_c_sweep": report["utility_c_sweep"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
