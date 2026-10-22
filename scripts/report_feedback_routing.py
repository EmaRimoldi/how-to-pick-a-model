"""Publish a completed feedback-only bank, audited statistics and static figures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
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


def publish(source: Path, output: Path) -> dict:
    if not (source / "summary.json").exists():
        raise RuntimeError("Collection has not ended; no interim treatment analysis or publication")
    data = audit(source)
    report = analyze(data)
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
    (output / "report.md").write_text(report_text(report))
    (output / "README.md").write_text("# Audited fixed-policy results\n\nRead [report.md](report.md), the [frozen protocol](../../PROTOCOL.md), and [analysis.json](analysis.json).\n")
    plot(report, output)
    hashes = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "checksums.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = publish(args.input, args.output)
    print(json.dumps({"status": report["status"], "tasks": report["task_clusters"], "primary": report["contrasts"][0]}, indent=2))


if __name__ == "__main__":
    main()
