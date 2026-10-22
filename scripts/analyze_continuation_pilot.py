"""Audit saved pilot receipts/outcomes and render an exploratory cost/success plot."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from vao.decisions.pilot import summarize


def read_jsonl(path: Path) -> list[dict]:
    """Read existing records without contacting providers or running candidate code."""
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(root: Path) -> dict:
    """Reconcile every receipt against the ledger and inspect actual branch coverage."""
    manifest = json.loads((root / "manifest.json").read_text())
    calls = read_jsonl(root / "calls.jsonl")
    outcomes = read_jsonl(root / "outcomes.jsonl")
    evaluations = read_jsonl(root / "evaluations.jsonl")
    budget = read_jsonl(root / "budget.jsonl")
    summary = json.loads((root / "summary.json").read_text())
    ids = [c["call"] for c in calls]
    assert len(ids) == len(set(ids)), "Duplicate call receipts"
    reservations = {r["call"]: Decimal(str(r["reserved_usd"])) for r in budget if r["event"] == "reserve"}
    settled = {r["call"]: Decimal(str(r["cost_usd"])) for r in budget if r["event"] == "settle"}
    assert len(settled) == sum(r["event"] == "settle" for r in budget), "Duplicate settlement"
    assert set(ids) == set(settled), "Missing settled receipt or unknown billed response"
    for call in calls:
        cost = Decimal(str(call["usage"]["cost"]))
        assert cost == settled[call["call"]], "Receipt/settlement mismatch"
        assert cost <= reservations[call["call"]], "Price/token reservation exceeded"
        assert call["provider"] == "SiliconFlow", "Provider changed"
        assert call["seed_sent"] is None, "Unexpected sampler seed"
        assert call["usage"].get("completion_tokens_details", {}).get("reasoning_tokens", 0) == 0
    assert sum(settled.values()) == Decimal(str(summary["actual_collection_cost_usd"]))
    assert sum(settled.values()) <= Decimal(str(summary["budget_usd"]))
    assert {e["call"] for e in evaluations} == set(ids), "Missing evaluated output"
    assert all(o["call"] in settled for o in outcomes), "Outcome lacks a charged receipt"
    recomputed = summarize(outcomes, manifest["config"])
    assert recomputed["strategies"] == summary["strategies"], "Summary differs from saved outcomes"
    by_call = {e["call"]: e for e in evaluations}
    initial = [c for c in calls if c["action"] == "initial"]
    failed = [c for c in initial if not by_call[c["call"]]["visible"]["passed"]]
    false_positives = [c["task_id"] for c in initial
                      if by_call[c["call"]]["visible"]["passed"]
                      and not by_call[c["call"]]["heldout"]["passed"]]
    return {"receipts_reconciled": True, "model_calls": len(calls),
            "generation_cost_usd": float(sum(settled.values())),
            "initial_checkpoints": len(initial), "visible_failed_checkpoints": len(failed),
            "false_positive_initial_task_ids": false_positives,
            "actual_continuation_calls": sum(c["action"] not in {"initial", "strong_direct"} for c in calls),
            "calls_by_action": dict(Counter(c["action"] for c in calls)),
            "verifier_wall_seconds": sum(e["verifier_seconds"] for e in evaluations),
            "model_request_wall_seconds": sum(c["elapsed_seconds"] for c in calls),
            "summary": recomputed}


def plot(report: dict, output: Path) -> None:
    """Render measured pilot means; this is not a fitted deployment frontier."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    strategies = report["summary"]["strategies"]
    # A stopped policy can have outcomes without executing any repair. Do not
    # turn reused prefixes into a visual claim about unobserved action efficacy.
    labels = list(strategies) if report["actual_continuation_calls"] else ["cheap_stop", "strong_direct"]
    if not all(strategies[s]["tasks"] for s in labels):
        return
    display = {"cheap_stop": "9B once", "strong_direct": "27B direct",
               "continue": "9B repair", "restart": "9B restart",
               "switch_fresh": "27B fresh", "switch_context": "27B + context"}
    colors = (["#2878b5", "#df7345"] + ["#708a81"] * 4)[:len(labels)]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), layout="constrained")
    values = [[100 * strategies[s]["success_rate"] for s in labels],
              [1000 * strategies[s]["mean_policy_cost_usd"] for s in labels]]
    titles = ["Full HumanEval+ success (%)", "Mean policy cost (milli-USD)"]
    for index, (ax, data, title) in enumerate(zip(axes, values, titles)):
        bars = ax.bar(range(len(labels)), data, color=colors)
        ax.set_xticks(range(len(labels)), [display[s] for s in labels], rotation=30, ha="right")
        ax.set_title(title)
        ax.bar_label(bars, fmt="%.1f" if index == 0 else "%.3f", padding=3, fontsize=8)
        ax.set_ylim(0, max(data) * 1.18 if max(data) else 1)
        ax.spines[["top", "right"]].set_visible(False)
    n = len(report["summary"]["complete_task_ids"])
    subtitle = ("No continuation actions evaluated; no learned controller" if not report["actual_continuation_calls"]
                else "Continuation policies stop when public examples pass; no learned controller")
    fig.suptitle(f"Development pilot — {n} tasks, {report['visible_failed_checkpoints']} visibly failed checkpoints\n"
                 + subtitle, fontsize=11)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    """Audit a finished run and write only regenerable local analysis artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    root = Path(args.input)
    report = audit(root)
    (root / "audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    plot(report, root / "cost_success.png")
    print(json.dumps({k: v for k, v in report.items() if k != "summary"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
