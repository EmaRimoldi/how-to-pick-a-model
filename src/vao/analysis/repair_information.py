"""Frozen descriptive analysis of public trace acquisition on failed checkpoints."""

import argparse
from decimal import Decimal
import json
from pathlib import Path
import random

from vao.repair.contract_collection import audit, read
from vao.repair.contracts import TRACE_STUDY, QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY, STREAM_TRACE_STUDY
from vao.repair.diagnostic_study import DRAWS
from vao.repair.diagnostics import ARMS
from vao.repair.records import rows, save
from .contract_diagnostic import export_evidence


def interval(values):
    """Fixed seed, 10k paired bug-cluster draws; descriptive with only eight bugs."""
    rng = random.Random(43123)
    draws = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(10000))
    return [draws[249], draws[9749]]


def summarize(output):
    if not ((output / "pilot-completion.json").exists() or (output / "interruption.json").exists()):
        raise ValueError("Do not inspect treatments before collection terminates")
    checked = audit(output)
    frozen = read(output / "manifest.json")["freeze"]
    packet = frozen["packet"]
    if packet["study"] not in (TRACE_STUDY, QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY, STREAM_TRACE_STUDY):
        raise ValueError("Expected the public trace information study")
    arms = ("focused", "focused_trace") if packet["study"] in (QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY, STREAM_TRACE_STUDY) else ARMS
    observed = {r["attempt_id"]: r for r in rows(output / "observations.jsonl")}
    cells = []
    for planned in packet["requests"]:
        meta = planned["metadata"]
        key, row = meta["attempt_id"], observed.get(meta["attempt_id"])
        public_pass, public_fraction, verification_seconds = None, None, None
        if row is not None:
            public_pass, public_fraction, verification_seconds = False, 0, 0
            for channel in ("public", "evaluator"):
                if row[channel] is not None:
                    result = read(output / "cells" / key / "objects" / (row[channel] + ".json"))["result"]
                    verification_seconds += result["verifier_seconds"]
                    if channel == "public":
                        public_pass = result["passed"]
                        public_fraction = result["passed_cases"] / result["total_cases"]
        source = packet["tasks"][meta["task_index"]]
        baseline = source["source_public_result"]
        cells.append({**meta, "observed": row is not None, "full_pass": row["full_pass"] if row else None,
            "public_pass": public_pass, "public_fraction": public_fraction,
            "public_regression": public_fraction < baseline["passed_cases"] / baseline["total_cases"] if row else None,
            "public_false_positive": bool(public_pass and not row["full_pass"]) if row else None,
            "artifact_valid": row["decoded"]["artifact_valid"] if row else None,
            "cost_usd": read(output / "receipts" / (key + ".json"))["cost_usd"]
                         if key in observed or key in checked["paid_without_outcome"] else None,
            "committed_usd": checked["committed_by_attempt_usd"].get(key, "0"),
            "uncertain": key in checked["pending"], "paid_without_outcome": key in checked["paid_without_outcome"],
            "source_prefix_usd": source["source_cost_usd"],
            "source_public_verification_seconds_per_deployment": source["observation"]["verifier_seconds"],
            "diagnostic_executions_per_deployment": source["diagnostic"]["additional_executions"] if meta["arm"] == "focused_trace" else 0,
            "diagnostic_seconds_per_deployment": source["diagnostic"]["diagnostic_seconds"] if meta["arm"] == "focused_trace" else 0,
            "response_verification_seconds": verification_seconds})
    complete = checked["sealed"] and not checked["cap_exceeded"]
    table = []
    for arm in arms:
        scoped = [r for r in cells if r["arm"] == arm]
        successes = sum(r["full_pass"] is True for r in scoped)
        missing = sum(not r["observed"] for r in scoped)
        table.append({"arm": arm, "planned": len(scoped), "observed": len(scoped) - missing,
            "successes": successes, "missing": missing,
            "success_bounds": [successes / len(scoped), (successes + missing) / len(scoped)],
            "public_passes": sum(r["public_pass"] is True for r in scoped),
            "false_positives": sum(r["public_false_positive"] is True for r in scoped),
            "regressions": sum(r["public_regression"] is True for r in scoped),
            "known_usd": str(sum((Decimal(r["cost_usd"]) for r in scoped if r["cost_usd"] is not None), Decimal(0))),
            "committed_usd": str(sum((Decimal(r["committed_usd"]) for r in scoped), Decimal(0))),
            "counterfactual_prefix_usd": str(sum((Decimal(r["source_prefix_usd"]) for r in scoped), Decimal(0))),
            "diagnostic_executions_if_deployed": sum(r["diagnostic_executions_per_deployment"] for r in scoped),
            "diagnostic_seconds_if_deployed": sum(r["diagnostic_seconds_per_deployment"] for r in scoped),
            "source_public_verification_seconds_if_deployed": sum(r["source_public_verification_seconds_per_deployment"] for r in scoped),
            "response_verification_seconds": sum(r["response_verification_seconds"] for r in scoped if r["observed"])})
    if sum((Decimal(r["committed_usd"]) for r in table), Decimal(0)) != Decimal(checked["study_committed_usd"]):
        raise ValueError("Arm accounting fails to reproduce total")
    tasks = []
    for index, record in enumerate(packet["tasks"]):
        tasks.append({"task_index": index, "task": record["public"]["task_id"],
            "eligible": record["eligible"], "reason": record["eligibility_reason"],
            "source_full_pass": record["source_full_pass"], "trace_available": record["diagnostic"]["available"],
            "cells": [r for r in cells if r["task_index"] == index]})
    contrasts = {}
    by_arm = {r["arm"]: r for r in table}
    for treatment, control in (("focused_trace", "focused"), ("focused", "raw"), ("focused_trace", "raw")):
        if control not in arms:
            continue
        a, b = by_arm[treatment], by_arm[control]
        values = []
        if complete:
            for task in tasks:
                if task["eligible"]:
                    values.append((sum(c["full_pass"] for c in task["cells"] if c["arm"] == treatment)
                                   - sum(c["full_pass"] for c in task["cells"] if c["arm"] == control)) / DRAWS)
        contrasts[treatment + "_minus_" + control] = {
            "primary": (treatment, control) == ("focused_trace", "focused"),
            "selected_cell_difference_bounds": [a["success_bounds"][0] - b["success_bounds"][1],
                                                a["success_bounds"][1] - b["success_bounds"][0]],
            "mean_difference": sum(values) / len(values) if complete else None,
            "descriptive_bug_bootstrap_95": interval(values) if complete else None}
    gate, components = "inconclusive_incomplete_bank", None
    if complete:
        repeated_bugs = sum(sum(c["full_pass"] for c in t["cells"] if c["arm"] == "focused_trace") >= 2
                            for t in tasks if t["eligible"])
        halves = []
        for draws in ({0, 1}, {2, 3}):
            halves.append(sum(c["full_pass"] for c in cells if c["arm"] == "focused_trace" and c["draw"] in draws)
                          - sum(c["full_pass"] for c in cells if c["arm"] == "focused" and c["draw"] in draws))
        net = by_arm["focused_trace"]["successes"] - by_arm["focused"]["successes"]
        components = {"bugs_with_two_trace_successes": repeated_bugs, "net_trace_successes": net,
                      "two_draw_half_differences": halves}
        gate = "candidate_for_independent_acquisition_calibration" if repeated_bugs >= 3 and net >= 4 and all(h > 0 for h in halves) else "no_repeated_information_benefit_demonstrated"
    report = {"study": packet["study"], "model_results": True, "status": "complete_development_information_probe" if complete else "incomplete_development_information_probe",
        "packet_id": packet["packet_id"], "freeze_id": frozen["freeze_id"], "source_commit": frozen["source_commit"],
        "accounting": checked, "study_limit_usd": frozen["authorized_limit_usd"],
        "cumulative_limit_usd": frozen["config"]["cumulative_limit_usd"], "arm_table": table,
        "task_table": tasks, "contrasts": contrasts, "gate": gate, "gate_components": components, "fit_selector": False,
        "limitations": ["Eight eligible inspected bugs, four draws at one saved checkpoint each; no held-out or independent-replicate inference.",
            "The other four public passes are retained without intervention, including the known false-positive/specification-ambiguity cases.",
            "Primary contrast: focused_trace minus focused. raw contrasts are secondary and cannot replace a null primary.",
            "Same per-call cap is not equal realized spending or an equal-total-cost policy comparison.",
            "Prefix charges in the arm tables are counterfactual per deployment, not new billed charges; acquisition cached for research is charged per decision in policy accounting.",
            "Local executions and measured seconds are separate resources, not converted into API dollars.",
            "Bootstrap intervals describe eight selected bug clusters; repeated draws and a screening gate do not establish action complementarity or authorize selector training.",
            "A complete-test pass is not a proof of all semantic requirements. Missing outcomes remain unknown; no repeat or imputation."]}
    if packet["study"] == QWEN_TRACE_STUDY:
        report["limitations"][2] = "Primary and only arm contrast: focused_trace minus focused; fresh concurrent controls, no historical-control substitution."
        report["limitations"].append("Solver compatibility qualified this development model. This is not a causal comparison with Gemma or evidence of a scaling law.")
    if packet["study"] == EXTENSION_TRACE_STUDY:
        report["limitations"][0] = "Three inspected development bugs from two projects; four draws each, no held-out or population inference."
        report["limitations"][1] = "Initial checkpoints are original upstream buggy versions, not LLM-generated failures; all three are retained. No generated-prefix API cost exists."
        report["limitations"][2] = "Only primary contrast: focused_trace minus focused on fresh matched requests. No pooling with the closed eight-checkpoint bank."
        report["limitations"][6] = "Bootstrap intervals describe only three purposively selected bug clusters and can be unstable; they cannot justify a population claim or selector training."
        report["limitations"].append("The prospective transport policy can retain one missing call and continue independent cells; a second error stops. Every unknown remains reserved and missing; any incomplete bank has a null mean/bootstrap and inconclusive gate.")
    if packet["study"] == STREAM_TRACE_STUDY:
        report["limitations"][0] = "Eight already exposed failed checkpoints (seven youtube-dl, one httpie), four fresh draws per arm; development only, no held-out inference."
        report["limitations"][2] = "Only primary contrast: focused_trace minus focused in this separate streaming bank; no pooling, historical concurrent controls or filling of old missing cells."
        report["limitations"].extend([
            "Previous outcomes were inspected before this protocol; the same development sources and previously specified screen are retained, with a new seed and explicit 8 MiB streaming envelope. No causal transport or scaling-law inference.",
            "Complete SSE receipts are reconstructed and audited with saved metrics; raw wire bytes are not archived, so their byte-level replay is unavailable.",
            "A first transport error closes the study without retry or resumption; historical uncertainties remain reserved. Incomplete banks have null mean/bootstrap and an inconclusive gate."])
    successor = read(output / 'manifest.json').get('continuation')
    if successor is not None:
        report['continuation'] = {k: successor[k] for k in ('continuation_id', 'source_commit',
            'parent_archive_sha256', 'excluded_attempt_ids', 'allowed_requests_sha256')}
        report['limitations'].append('A manually reviewed successor admits only the original 95 unsent requests. '
            'The original uncertain first call stays missing and reserved; even a finished successor is an incomplete '
            '96-cell bank, with bounds and no passed screening gate or bootstrap interval.')
    return report


def render(report):
    lines = ["# Public-trace information development probe", "",
        f"Status: **{report['status']}**. Gate: **{report['gate']}**. No selector trained.", "",
        f"Study commitment: ${report['accounting']['study_committed_usd']} / ${report['study_limit_usd']}; cumulative including historical reserves: ${report['accounting']['cumulative_committed_usd']} / ${report['cumulative_limit_usd']}.", "",
        "| Arm | Observed/planned | Full successes | Public false positives | Regressions | Missing | Known API USD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in report["arm_table"]:
        lines.append(f"| {r['arm']} | {r['observed']}/{r['planned']} | {r['successes']} | {r['false_positives']} | {r['regressions']} | {r['missing']} | {r['known_usd']} |")
    task_label = "all three task records" if report["study"] == EXTENSION_TRACE_STUDY else "all twelve task records"
    lines += ["", "Primary contrast and all secondary contrasts:", "", "```json", json.dumps(report["contrasts"], indent=2), "```", "",
              f"The screening rule cannot train or certify a policy. Full costs, prefix accounting, local acquisition/verification and {task_label} are in analysis.json.", "", "## Limitations", ""]
    lines += ["- " + item for item in report["limitations"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export-evidence", action="store_true")
    args = parser.parse_args()
    report = summarize(args.input)
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "analysis.json", report)
    (args.output / "REPORT.md").write_text(render(report))
    if args.export_evidence:
        manifest = export_evidence(args.input, args.output, summarize_fn=summarize,
                                   report_entrypoint="report_repair_information_study")
        print(json.dumps({"archive_sha256": manifest["archive_sha256"]}))
    print(json.dumps({"status": report["status"], "gate": report["gate"], "fit_selector": False}))


if __name__ == "__main__":
    main()
