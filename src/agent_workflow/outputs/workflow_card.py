"""Agent Workflow Card serialization.

A workflow card is a compact, reviewable summary of one agent-workflow run.
It is intentionally small enough to paste into an issue, paper appendix, or
launch post without dragging along the full run directory.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkflowCard:
    """Portable summary of an agent-workflow evaluation."""

    experiment_id: str
    task: str
    workflow: str
    metric: str
    agents: list[dict[str, Any]]
    baseline: dict[str, Any]
    result: dict[str, Any]
    claim: str
    evidence_level: str
    limitations: list[str] = field(default_factory=list)
    source: str = "run"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        lines = [
            "# Agent Workflow Card",
            "",
            f"- Experiment: `{self.experiment_id}`",
            f"- Task: {self.task}",
            f"- Workflow: `{self.workflow}`",
            f"- Metric: `{self.metric}`",
            f"- Evidence level: {self.evidence_level}",
            f"- Source: {self.source}",
            "",
            "## Agents",
            "",
        ]
        for agent in self.agents:
            role = agent.get("role", "")
            model = agent.get("model", "")
            memory = agent.get("memory", "")
            lines.append(
                f"- `{agent.get('id', '?')}`: {role} "
                f"(model={model}, memory={memory})"
            )
        lines.extend(
            [
                "",
                "## Baseline",
                "",
            ]
        )
        for key, value in self.baseline.items():
            lines.append(f"- {key}: {value}")
        lines.extend(
            [
                "",
                "## Result",
                "",
            ]
        )
        for key, value in self.result.items():
            lines.append(f"- {key}: {value}")
        lines.extend(
            [
                "",
                "## Claim",
                "",
                self.claim,
            ]
        )
        if self.limitations:
            lines.extend(["", "## Limitations", ""])
            lines.extend(f"- {item}" for item in self.limitations)
        return "\n".join(lines) + "\n"


def write_workflow_card(card: WorkflowCard, output_dir: Path) -> tuple[Path, Path]:
    """Write JSON and Markdown workflow-card artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "workflow_card.json"
    md_path = output_dir / "workflow_card.md"
    json_path.write_text(card.to_json())
    md_path.write_text(card.to_markdown())
    return json_path, md_path
