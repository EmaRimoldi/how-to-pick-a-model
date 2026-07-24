"""Build Phase 3 real-backend summary and failure-mode artifacts."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from vao.estimators import gains_by_mode, jsd, productive_mode_proxy, routing_regret
from vao.records import iter_run_dirs, load_step_records
from vao.taxonomy import MODES


def summarize(runs_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    return summarize_roots([runs_root])


def summarize_roots(runs_roots: list[Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    run_dirs = []
    seen = set()
    for root in runs_roots:
        for run_dir in iter_run_dirs(root):
            resolved = run_dir.resolve()
            if resolved not in seen:
                seen.add(resolved)
                run_dirs.append(run_dir)
    records = []
    for run_dir in run_dirs:
        records.extend(load_step_records(run_dir))

    correctness_by_mode: dict[str, list[bool]] = defaultdict(list)
    gains_by_declared: dict[str, list[float]] = defaultdict(list)
    inferred_agreement: dict[str, list[bool]] = defaultdict(list)
    selected_losses: list[float] = []
    all_losses: list[float] = []
    regrets: list[float] = []
    jsds: list[float] = []
    run_wall_per_step: list[float] = []
    costs: list[float] = []
    token_inputs: list[int] = []
    token_outputs: list[int] = []
    failure_counts = Counter()
    proposal_count = 0
    verifier_failures = 0

    for record in records:
        gains = gains_by_mode(record)
        regrets.append(routing_regret(gains, record.selected_mode))
        jsds.append(jsd(record.mode_probs, productive_mode_proxy(gains)))
        if record.agent_cost_usd is not None:
            costs.append(float(record.agent_cost_usd))
        if record.input_tokens is not None:
            token_inputs.append(int(record.input_tokens))
        if record.output_tokens is not None:
            token_outputs.append(int(record.output_tokens))
        for branch in record.branches:
            proposal_count += 1
            correctness_by_mode[branch.declared_mode].append(branch.correctness)
            gains_by_declared[branch.declared_mode].append(branch.gain)
            inferred_agreement[branch.declared_mode].append(branch.declared_mode == branch.inferred_mode)
            if branch.promoted_as_parent and branch.correctness and math.isfinite(branch.latent_loss):
                selected_losses.append(branch.latent_loss)
            if branch.correctness and math.isfinite(branch.latent_loss):
                all_losses.append(branch.latent_loss)
            if branch.errors:
                verifier_failures += 1
            for item in branch.validation_failures:
                failure_counts[f"branch_validation:{item}"] += 1

    proposal_failures = _proposal_failures(run_dirs)
    for run_dir in run_dirs:
        summary_path = run_dir / "run_summary.json"
        if not summary_path.exists():
            continue
        try:
            run_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        steps = int(run_summary.get("steps_completed") or 0)
        elapsed = run_summary.get("elapsed_wall_seconds")
        if steps > 0 and isinstance(elapsed, int | float):
            run_wall_per_step.append(float(elapsed) / steps)
    failure_counts.update(proposal_failures)
    parse_failure_count = sum(count for name, count in failure_counts.items() if "parse" in name or "repair" in name or "rejected" in name)
    code_validation_failure_count = sum(count for name, count in failure_counts.items() if "source" in name or "validation" in name)

    summary = {
        "run_count": len(run_dirs),
        "step_count": len(records),
        "branch_evaluation_count": sum(len(record.branches) for record in records),
        "correctness_rate_by_mode": _mean_bool_by_mode(correctness_by_mode),
        "average_gain_by_mode": _mean_float_by_mode(gains_by_declared),
        "declared_inferred_agreement_by_mode": _mean_bool_by_mode(inferred_agreement),
        "best_visible_loss": min(selected_losses) if selected_losses else None,
        "best_counterfactual_loss": min(all_losses) if all_losses else None,
        "mean_routing_regret": statistics.fmean(regrets) if regrets else None,
        "mean_jsd": statistics.fmean(jsds) if jsds else None,
        "parse_failure_rate": parse_failure_count / proposal_count if proposal_count else 0.0,
        "code_validation_failure_rate": code_validation_failure_count / proposal_count if proposal_count else 0.0,
        "verifier_failure_rate": verifier_failures / proposal_count if proposal_count else 0.0,
        "average_wall_clock_seconds_per_step": statistics.fmean(run_wall_per_step) if run_wall_per_step else None,
        "average_agent_cost_usd_per_step": statistics.fmean(costs) if costs else None,
        "average_input_tokens_per_step": statistics.fmean(token_inputs) if token_inputs else None,
        "average_output_tokens_per_step": statistics.fmean(token_outputs) if token_outputs else None,
    }
    failure_modes = {
        "proposal_count": proposal_count,
        "failure_counts": dict(failure_counts),
        "parse_failure_count": parse_failure_count,
        "code_validation_failure_count": code_validation_failure_count,
        "verifier_failure_count": verifier_failures,
    }
    return summary, failure_modes


def _proposal_failures(run_dirs: list[Path]) -> Counter:
    counts = Counter()
    for run_dir in run_dirs:
        for proposal_path in run_dir.glob("steps/step_*/branches/*/proposal.json"):
            try:
                proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                counts["proposal_json_decode_error"] += 1
                continue
            for item in proposal.get("validation_failures", []):
                counts[f"proposal_validation:{item}"] += 1
            for item in proposal.get("errors", []):
                prefix = str(item).split(":", 1)[0]
                counts[f"proposal_error:{prefix}"] += 1
            source_validation = proposal.get("source_validation") or {}
            if source_validation.get("passed") is False:
                counts["proposal_source_validation_failed"] += 1
    return counts


def _mean_bool_by_mode(values: dict[str, list[bool]]) -> dict[str, float | None]:
    return {mode: (statistics.fmean(values[mode]) if values.get(mode) else None) for mode in MODES}


def _mean_float_by_mode(values: dict[str, list[float]]) -> dict[str, float | None]:
    return {mode: (statistics.fmean(values[mode]) if values.get(mode) else None) for mode in MODES}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--summary_out", required=True)
    parser.add_argument("--failure_modes_out", required=True)
    args = parser.parse_args(argv)
    summary, failure_modes = summarize_roots([Path(item) for item in args.runs])
    Path(args.summary_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary_out).write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    Path(args.failure_modes_out).write_text(json.dumps(failure_modes, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    print(json.dumps({"summary_out": args.summary_out, "failure_modes_out": args.failure_modes_out}, indent=2))


if __name__ == "__main__":
    main()
