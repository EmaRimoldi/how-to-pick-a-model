"""Offline demo command for Agent Workflow.

The demo is deliberately infrastructure-free: no Claude Code session, GPU, SLURM,
or model provider is required. It writes the same kind of evidence bundle a real
run should produce, using deterministic fixture trajectories.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agent_workflow.outputs.html_report import write_static_report
from agent_workflow.outputs.workflow_card import WorkflowCard, write_workflow_card


@dataclass(frozen=True)
class DemoBundle:
    experiment_dir: Path
    report_html: Path
    report_md: Path
    workflow_card_json: Path
    workflow_card_md: Path
    summary_json: Path


DEMO_AGENTS = [
    {
        "id": "explorer",
        "role": "broad architecture and hyperparameter search",
        "model": "demo-agent",
        "memory": "shared result log",
    },
    {
        "id": "optimizer",
        "role": "conservative refinement of the current best candidate",
        "model": "demo-agent",
        "memory": "shared result log",
    },
    {
        "id": "regularizer",
        "role": "regularization and data-pipeline search",
        "model": "demo-agent",
        "memory": "shared result log",
    },
]

DEMO_TRAJECTORIES = {
    "explorer": [1.34, 1.18, 1.08],
    "optimizer": [1.29, 1.12, 1.04],
    "regularizer": [1.31, 1.15, 1.06],
}


def generate_demo_bundle(
    output_dir: Path,
    experiment_id: str | None = None,
    force: bool = False,
) -> DemoBundle:
    """Generate a deterministic offline demo bundle."""

    exp_id = experiment_id or f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    experiment_dir = output_dir / f"experiment_{exp_id}"
    if experiment_dir.exists() and not force:
        raise FileExistsError(
            f"{experiment_dir} already exists. Pass --force to overwrite it."
        )
    experiment_dir.mkdir(parents=True, exist_ok=True)

    best_agent, best_value = _best_agent(DEMO_TRAJECTORIES)
    baseline_best = 1.18
    card = WorkflowCard(
        experiment_id=exp_id,
        task="offline_toy_search",
        workflow="parallel_shared",
        metric="toy_loss",
        agents=DEMO_AGENTS,
        baseline={
            "workflow": "single_demo_agent",
            "best_value": baseline_best,
            "attempts": 3,
        },
        result={
            "best_agent": best_agent,
            "best_value": best_value,
            "attempts": sum(len(v) for v in DEMO_TRAJECTORIES.values()),
            "delta_vs_baseline": round(best_value - baseline_best, 4),
        },
        claim=(
            "This offline fixture demonstrates the Agent Workflow evidence "
            "format: roster, trajectories, workflow card, and static report."
        ),
        evidence_level="deterministic offline demo fixture; not scientific evidence",
        limitations=[
            "No Claude Code agent was invoked.",
            "No GPU or external evaluator was used.",
            "The trajectories are fixture data for onboarding and UI review.",
        ],
        source="offline_demo_fixture",
    )

    config = {
        "experiment_id": exp_id,
        "mode": "parallel_shared",
        "source": "offline_demo_fixture",
        "agents": DEMO_AGENTS,
        "metric": "toy_loss",
        "lower_is_better": True,
    }
    summary = {
        "experiment_id": exp_id,
        "mode": "parallel_shared",
        "task": "offline_toy_search",
        "metric": "toy_loss",
        "best_agent": best_agent,
        "best_value": best_value,
        "trajectories": DEMO_TRAJECTORIES,
        "warning": "Fixture data only; not live Claude Code evidence.",
    }

    (experiment_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    summary_json = experiment_dir / "summary.json"
    summary_json.write_text(json.dumps(summary, indent=2) + "\n")
    _write_trajectory_csv(experiment_dir / "trajectories.csv", DEMO_TRAJECTORIES)
    workflow_card_json, workflow_card_md = write_workflow_card(card, experiment_dir)
    report_md = _write_markdown_report(experiment_dir, card)
    report_html = write_static_report(
        card=card,
        trajectories=DEMO_TRAJECTORIES,
        output_dir=experiment_dir,
        title="Agent Workflow Offline Demo",
    )
    return DemoBundle(
        experiment_dir=experiment_dir,
        report_html=report_html,
        report_md=report_md,
        workflow_card_json=workflow_card_json,
        workflow_card_md=workflow_card_md,
        summary_json=summary_json,
    )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="agent-workflow demo",
        description="Generate an offline demo evidence bundle without Claude Code or GPU.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="runs",
        help="Directory where the demo experiment folder is written.",
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Optional experiment id. Defaults to a timestamped demo id.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing demo directory with the same experiment id.",
    )
    args = parser.parse_args(argv)

    bundle = generate_demo_bundle(
        output_dir=Path(args.output_dir),
        experiment_id=args.experiment_id,
        force=args.force,
    )
    print("[demo] Offline evidence bundle written.")
    print(f"[demo] Directory:      {bundle.experiment_dir}")
    print(f"[demo] HTML report:    {bundle.report_html}")
    print(f"[demo] Workflow card:  {bundle.workflow_card_md}")
    print("[demo] This is fixture data only; no Claude Code agent or GPU was used.")


def _best_agent(trajectories: dict[str, list[float]]) -> tuple[str, float]:
    best_agent = ""
    best_value = float("inf")
    for agent_id, values in trajectories.items():
        agent_best = min(values)
        if agent_best < best_value:
            best_agent = agent_id
            best_value = agent_best
    return best_agent, best_value


def _write_trajectory_csv(
    path: Path,
    trajectories: dict[str, list[float]],
) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["agent_id", "attempt", "value"])
        writer.writeheader()
        for agent_id, values in trajectories.items():
            for index, value in enumerate(values, start=1):
                writer.writerow(
                    {"agent_id": agent_id, "attempt": index, "value": value}
                )


def _write_markdown_report(output_dir: Path, card: WorkflowCard) -> Path:
    path = output_dir / "report.md"
    lines = [
        "# Agent Workflow Offline Demo",
        "",
        "This bundle is deterministic fixture data for onboarding and report review.",
        "It does not invoke Claude Code, GPUs, SLURM, or external model providers.",
        "",
        "## What To Inspect",
        "",
        "- `workflow_card.md`: compact standardized run summary.",
        "- `workflow_card.json`: machine-readable workflow card.",
        "- `report.html`: static report with trajectory chart.",
        "- `trajectories.csv`: per-agent fixture trajectories.",
        "- `summary.json`: compact run summary.",
        "",
        "## Claim",
        "",
        card.claim,
        "",
        "## Limitation",
        "",
        "Use this command to understand the artifact shape. Use live modes for real evidence.",
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


if __name__ == "__main__":
    main()
