"""Publish a completed feedback-only bank, audited statistics and static figures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from statistics import mean, median
import subprocess

if __package__:
    from .analyze_feedback_routing import analyze, audit
else:
    from analyze_feedback_routing import analyze, audit


def report_text(report: dict) -> str:
    complete = report["status"] == "complete_prespecified_bank"
    primary = report["contrasts"][0]
    rows = ["# Fixed feedback-only policies on new BigCodeBench tasks", "",
            "All policies use public feedback only; no selector was trained.", "",
            f"Coverage: **{report['task_clusters']} task clusters**, {report['replicates']} replicate per task. "
            + ("All frozen policy outcomes observed." if complete else "Incomplete bank; complete-case intervals are descriptive."), "",
            "The reference-qualified standard-library subset is not representative of all BigCodeBench. "
            "These are new project queries, not proof of absence from model training data.", "",
            "| Fixed policy | Successes / expected | All-selected success bounds | Mean API spend | Mean verifier seconds | Public false positives |",
            "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, policy in report["policies"].items():
        lo, hi = policy["all_selected_success_bounds"]
        spend = policy["mean_observed_cost_usd"]
        wall = policy["mean_observed_verifier_seconds"]
        rows.append(f"| `{name}` | {policy['successes']} / {policy['expected']} | {100*lo:.1f}–{100*hi:.1f}% | "
                    + (f"${spend:.6f}" if spend is not None else "unobserved") + " | "
                    + (f"{wall:.3f}" if wall is not None else "unobserved") + f" | {policy['public_false_positives']} |")
    rows.extend(["", "Equal budget means a **$0.006 API-dollar admission ceiling**, including the initial attempt. "
                 "It does not mean equal realized spend, latency or local hardware cost. Fixed-rule selection "
                 "uses zero API calls; local verification is measured separately. Every failure remains in the denominator.", "",
                 "## Prespecified primary comparison", ""])
    if primary["estimate"] is not None:
        low, high = primary["interval"]
        rows.append(f"Immediate 27B escalation minus repeated 9B: **{100*primary['estimate']:+.2f} percentage points**, "
                    f"95% task-bootstrap interval [{100*low:+.2f}, {100*high:+.2f}]. "
                    f"Complete paired task clusters: {primary['complete_task_clusters']}.")
    bounds = primary["all_selected_missing_bounds"]
    rows.extend(["", f"All-selected missing-outcome bounds: [{100*bounds[0]:+.2f}, {100*bounds[1]:+.2f}] percentage points. "
                 "These bounds are **not confidence intervals**.", "",
                 "Primary gate: **" + ("passed" if report["primary_gate_passed"] else "not passed") + "**. "
                 "The gate requires a complete bank, a positive lower confidence endpoint and at least a five-point estimate. "
                 "A passed gate alone would not establish an adaptive selector advantage. A failed gate does not establish equivalence.", "",
                 "## Secondary comparisons", "",
                 "The following intervals use 98.333% coverage for the three-comparison family; "
                 "they cannot replace a failed primary outcome.", "",
                 "| Difference | Estimate (pp) | Task-bootstrap interval (pp) |", "| --- | ---: | ---: |"])
    for c in report["contrasts"][1:]:
        if c["estimate"] is not None:
            lo, hi = c["interval"]
            rows.append(f"| `{c['left']}` − `{c['right']}` | {100*c['estimate']:+.2f} | [{100*lo:+.2f}, {100*hi:+.2f}] |")
    rows.extend(["", "## Collection and limits", "",
                 f"Known collection charges: ${report['integrity']['known_usd']:.8f}; unresolved full reservations: "
                 f"${report['integrity']['held_usd']:.8f}. The new collection cap is $4.00 under the separate $5 authorization. "
                 "Shared prefixes are paid once in collection and charged separately in each deployment policy.", "",
                 "The policies stop at their first public pass even when full-suite evaluation fails. "
                 "Public examples are weak tests; false positives can hide additional benefits or errors. "
                 "Conservative token reservation can leave budget unused, especially for 27B. "
                 "One replicate per task, one provider/precision, public benchmark contamination, qualification bias, "
                 "a fixed budget point and unpriced local compute limit generalization. "
                 "A 157-task study has limited power for modest improvements. No outcome-based task exclusion or learned tuning is allowed.", "",
                 "All policies assume feedback is the interface. This is **not a feedback-versus-no-feedback test**. "
                 "The code-transfer findings in the previous MBPP+ study remain separate.", "",
                 "![Cost and success of the fixed policies](fixed-policy-comparison.png)", "",
                 "## Reproduce without credentials or candidate execution", "", "```bash",
                 "uv run python scripts/analyze_feedback_routing.py \\",
                 "  --input experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022 \\",
                 "  --output /tmp/feedback-only-analysis.json", "```", "",
                 "The collector source freeze and private/public split are documented in `../../PROTOCOL.md`. "
                 "`source-map.json` binds inert source snapshots to the collection commit; `checksums.json` covers published files.", ""])
    return "\n".join(rows)


def accounting_diagnostics(data: dict) -> dict:
    """Descriptive accounting after collection, separate from the fixed efficacy test."""
    config = data["config"]
    calls = {r["call"]: r for r in data["calls"]}
    scores = {r["call"]: r for r in data["evaluations"]}
    per_policy = {}
    for policy in data["config"].get("policies", ("small_feedback", "immediate_large_feedback", "delayed_large_feedback", "large_direct")):
        rows = [r for r in data["outcomes"] if r["policy"] == policy]
        stopped = [r for r in rows if r["stop_reason"] == "task_budget"]
        per_policy[policy] = {
            "mean_attempts": mean(len(r["calls"]) for r in rows) if rows else None,
            "maximum_attempts_observed": max((len(r["calls"]) for r in rows), default=0),
            "budget_stopped_tasks": len(stopped),
            "mean_spend_when_budget_stopped_usd": mean(r["cost_usd"] for r in stopped) if stopped else None,
            "mean_unused_budget_when_budget_stopped_usd": mean(config["task_budget_usd"] - r["cost_usd"] for r in stopped) if stopped else None,
            "mean_budget_fraction_used_when_budget_stopped": mean(r["cost_usd"] / config["task_budget_usd"] for r in stopped) if stopped else None,
            "median_api_seconds": median(sum(calls[c]["elapsed_seconds"] for c in r["calls"]) for r in rows) if rows else None}
    initial = [r for r in calls.values() if r["policy"] == "small_feedback" and r["attempt"] == 0 and r["call"] in scores]
    public_passes = sum(scores[r["call"]]["visible"]["passed"] for r in initial)
    correct = sum(bool(scores[r["call"]]["heldout"] and scores[r["call"]]["heldout"]["passed"]) for r in initial)
    return {"scope": "Postcollection descriptive accounting/verifier diagnostics; not additional efficacy hypotheses or changed primary labels.",
            "per_policy": per_policy, "cap_usd": config["task_budget_usd"],
            "shared_initial_9b": {"tasks": len(initial), "public_passes": public_passes,
                                  "full_suite_successes": correct,
                                  "public_false_positives_locked_in_all_three_small_start_policies": public_passes - correct}}


def diagnostic_text(report: dict, diagnostics: dict) -> str:
    rows = ["\n## Latency and admission diagnostics", "",
            "These are postcollection descriptive accounting checks, not extra efficacy hypotheses. "
            "The admission rule reserves a worst-case response at model-specific prices. "
            "An equal API cap therefore does not imply equal realized spend or equal opportunity to exhaust it. "
            "A lower bill alone does not establish equal-quality savings or an intrinsic escalation advantage.", "",
            "| Policy | Mean attempts | Mean / median API seconds | Budget-stopped tasks | Mean cap used when budget-stopped |",
            "| --- | ---: | ---: | ---: | ---: |"]
    for policy, d in diagnostics["per_policy"].items():
        if d["mean_attempts"] is None:
            continue
        api = report["policies"][policy]["mean_observed_api_seconds"]
        fraction = d["mean_budget_fraction_used_when_budget_stopped"]
        rows.append(f"| `{policy}` | {d['mean_attempts']:.2f} | {api:.2f} / {d['median_api_seconds']:.2f} | "
                    f"{d['budget_stopped_tasks']} | " + (f"{100*fraction:.1f}%" if fraction is not None else "not applicable") + " |")
    initial = diagnostics["shared_initial_9b"]
    rows.extend(["", "Mean API seconds sum each policy's own model requests; they exclude local verification and collection queue time. "
                 "The median helps distinguish tail retries from a speedup on a typical task. "
                 "Budget-stop fractions are conditional on budget-stopped tasks, not averages over all tasks.", "",
                 f"Of the {initial['tasks']} shared initial 9B responses, {initial['public_passes']} passed the public examples "
                 f"but only {initial['full_suite_successes']} passed the full suite. The "
                 f"{initial['public_false_positives_locked_in_all_three_small_start_policies']} initial public false positives "
                 "terminate all three small-start policies before escalation is possible. "
                 "This is an observed verifier limitation, not a measured benefit of adding stronger tests.", "",
                 "![Admission utilization and terminal outcomes](admission-and-verification.png)", ""])
    return "\n".join(rows)


def plot(report: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(report["policies"])
    labels = ["Repeat 9B", "9B → 27B", "9B ×2 → 27B", "Direct 27B"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    for i, name in enumerate(names):
        policy = report["policies"][name]
        if policy["mean_observed_cost_usd"] is None:
            continue
        low, high = policy["all_selected_success_bounds"]
        mid = (low + high) / 2
        axes[0].errorbar(1000 * policy["mean_observed_cost_usd"], 100 * mid,
                         yerr=100 * (high - low) / 2, fmt="o", capsize=4, label=labels[i])
    axes[0].set(xlabel="Mean observed API spend (milli-USD)", ylabel="Success on all selected tasks (%)",
                title="Same $0.006 API admission cap")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=.2)
    positions = []
    for i, c in enumerate(report["contrasts"]):
        if c["estimate"] is None:
            continue
        low, high = c["interval"]
        value = c["estimate"]
        axes[1].errorbar(value * 100, i, xerr=[[max(0, value-low)*100], [max(0, high-value)*100]],
                         fmt="o", capsize=4, color="C0" if i == 0 else "C1")
        positions.append(i)
    axes[1].axvline(0, color="black", linewidth=.8)
    axes[1].set_yticks(range(4), ["9B → 27B − Repeat 9B", "Delayed − Repeat 9B", "Direct 27B − Repeat 9B", "9B → 27B − Direct 27B"], fontsize=8)
    axes[1].invert_yaxis()
    axes[1].set(xlabel="Success difference (percentage points)", title="Paired task-bootstrap intervals")
    axes[1].grid(axis="x", alpha=.2)
    fig.suptitle(f"{report['task_clusters']} qualified BigCodeBench tasks · feedback only · no selector", fontsize=12)
    fig.supxlabel("Primary: 95% interval; three secondary contrasts: 98.333%. Missing bounds on left are not confidence intervals.", fontsize=8)
    fig.savefig(output / "fixed-policy-comparison.png", dpi=180)
    fig.savefig(output / "fixed-policy-comparison.svg")
    plt.close(fig)


def diagnostic_plot(report: dict, diagnostics: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    policies = list(diagnostics["per_policy"])
    labels = ["Repeat 9B", "9B → 27B", "9B ×2 → 27B", "Direct 27B"]
    positions = np.arange(len(policies))
    used = [100 * (diagnostics["per_policy"][p]["mean_budget_fraction_used_when_budget_stopped"] or 0) for p in policies]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    axes[0].bar(positions, used, color="#4477AA", label="Spent")
    axes[0].bar(positions, [100-u for u in used], bottom=used, color="#DDDDDD", label="Unused cap")
    for i, p in enumerate(policies):
        n = diagnostics["per_policy"][p]["budget_stopped_tasks"]
        axes[0].text(i, 101, f"n={n}", ha="center", fontsize=9)
    axes[0].set_xticks(positions, labels, rotation=15, ha="right", fontsize=8)
    axes[0].set(ylim=(0, 110), ylabel="Mean share of $0.006 API cap (%)", title="Budget-stopped tasks only")
    axes[0].legend(fontsize=8, loc="lower right")
    solved = [report["policies"][p]["successes"] for p in policies]
    false = [report["policies"][p]["public_false_positives"] for p in policies]
    no_public = [report["policies"][p]["observed"] - a - b for p, a, b in zip(policies, solved, false)]
    axes[1].barh(positions, solved, color="#4477AA", label="Full-suite success")
    axes[1].barh(positions, false, left=solved, color="#EE6677", label="Public false positive")
    axes[1].barh(positions, no_public, left=np.array(solved)+false, color="#BBBBBB", label="No public pass")
    for i in positions:
        for value, start in [(solved[i], 0), (false[i], solved[i]), (no_public[i], solved[i]+false[i])]:
            if value:
                axes[1].text(start+value/2, i, str(value), ha="center", va="center", fontsize=9)
    axes[1].set_yticks(positions, labels, fontsize=8)
    axes[1].invert_yaxis()
    axes[1].set(xlabel="Number of tasks", title="Recorded terminal outcomes")
    axes[1].legend(fontsize=8, loc="lower center", bbox_to_anchor=(.5, -.36))
    fig.suptitle("Conservative admission and public verification constrain these policies", fontsize=12)
    for extension in ("png", "svg"):
        fig.savefig(output / ("admission-and-verification." + extension), dpi=180, bbox_inches="tight")
    plt.close(fig)


def publish(source: Path, output: Path, reverification: Path | None = None,
            reverification_source: Path | None = None) -> dict:
    if not (source / "summary.json").exists():
        raise RuntimeError("Collection has not ended; no interim treatment analysis or publication")
    data = audit(source)
    report = analyze(data)
    diagnostics = accounting_diagnostics(data)
    manifest = json.loads((source / "manifest.json").read_text())
    config = data["config"]
    snapshots = {}
    for name, expected in config["source_hashes"].items():
        content = subprocess.check_output(["git", "show", manifest["git_commit"] + ":" + name])
        assert hashlib.sha256(content).hexdigest() == expected
        snapshots[name] = content
    output.mkdir(parents=True, exist_ok=False)
    for name in ("config.json", "manifest.json", "summary.json", "budget.jsonl", "calls.jsonl", "evaluations.jsonl", "outcomes.jsonl", "transport.jsonl"):
        if (source / name).exists():
            shutil.copyfile(source / name, output / name)
    preflight = json.loads((source / "preflight.json").read_text())
    preflight["provider"].pop("available_usd_before", None)
    (output / "preflight.json").write_text(json.dumps(preflight, indent=2) + "\n")
    (output / "source").mkdir()
    source_map = {"git_commit": manifest["git_commit"], "files": {}}
    for name, content in snapshots.items():
        target = "source/" + name.replace("/", "__") + ".txt"
        (output / target).write_bytes(content)
        source_map["files"][name] = {"snapshot": target, "sha256": hashlib.sha256(content).hexdigest()}
    (output / "source-map.json").write_text(json.dumps(source_map, indent=2) + "\n")
    (output / "analysis.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (output / "accounting-diagnostics.json").write_text(json.dumps(diagnostics, indent=2, allow_nan=False) + "\n")
    text = report_text(report) + diagnostic_text(report, diagnostics)
    if reverification is not None:
        repeated = json.loads(reverification.read_text())
        assert repeated["model_calls"] == 0 and repeated["checked_responses"] == len(data["evaluations"])
        assert {r["call"] for r in repeated["rows"]} == {r["call"] for r in data["evaluations"]}
        assert len(repeated["rows"]) == repeated["checked_responses"]
        assert sum(bool(r["mismatches"]) for r in repeated["rows"]) == repeated["mismatching_responses"]
        shutil.copyfile(reverification, output / "verification-repeat.json")
        if reverification_source is not None:
            content = reverification_source.read_bytes()
            target = "source/offline_verifier_repeat.py.txt"
            (output / target).write_bytes(content)
            source_map["postcollection_verification"] = {"snapshot": target, "sha256": hashlib.sha256(content).hexdigest(),
                                                       "scope": "Offline robustness diagnostic; original labels retained"}
            (output / "source-map.json").write_text(json.dumps(source_map, indent=2) + "\n")
        text += ("\n## Offline verifier repeat\n\n"
                 f"Rechecked all {repeated['checked_responses']} preserved responses: reproduced "
                 f"{sum(bool(r.get('format_error_reproduced')) for r in repeated['rows'])} format errors and re-executed "
                 "the public checks for every parseable solution and every originally executed full-suite check, "
                 "under the same frozen sandbox verifier and RNG seed. "
                 f"Observed **{repeated['mismatching_responses']} responses with pass/fail discrepancies**. "
                 "Original primary labels were retained throughout; no model request or paid inference was repeated. "
                 "The diagnostic is preserved in [verification-repeat.json](verification-repeat.json). "
                 "This repeat check does not establish correctness beyond the benchmark tests.\n")
    bundle = Path(config["bundle"])
    disclosure = bundle / "INTERIM-DISCLOSURE.md"
    interim = bundle / "data/user-requested-interim-20261022.json"
    if disclosure.exists() or interim.exists():
        if not (disclosure.exists() and interim.exists()):
            raise RuntimeError("Interim disclosure and immutable record must be published together")
        shutil.copyfile(disclosure, output / "interim-disclosure.md.txt")
        shutil.copyfile(interim, output / "interim-record.json")
        text += ("\n## Human-requested interim disclosure\n\n"
                 "After the freeze, the user requested one descriptive look at the 83 tasks then complete "
                 "under all four policies. Its completion bias was disclosed. No interim confidence interval, "
                 "p-value, primary gate, fitting, efficacy stopping or change to collection followed. "
                 "The final protocol retains all selected tasks, failures and missing-outcome bounds; incomplete-bank intervals are descriptive. "
                 "See [the preserved disclosure](interim-disclosure.md.txt) and [the immutable interim record](interim-record.json). "
                 "The historical interim subset must not replace the final primary comparison.\n")
    (output / "report.md").write_text(text)
    (output / "README.md").write_text("# Audited fixed-policy results\n\nRead [report.md](report.md), the [frozen protocol](../../PROTOCOL.md), and [analysis.json](analysis.json).\n")
    plot(report, output)
    diagnostic_plot(report, diagnostics, output)
    hashes = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "checksums.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reverification", type=Path)
    parser.add_argument("--reverification-source", type=Path)
    args = parser.parse_args()
    report = publish(args.input, args.output, args.reverification, args.reverification_source)
    print(json.dumps({"status": report["status"], "tasks": report["task_clusters"], "primary": report["contrasts"][0]}, indent=2))


if __name__ == "__main__":
    main()
