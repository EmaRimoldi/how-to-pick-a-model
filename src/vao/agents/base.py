"""Agent adapter interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from vao.schemas import CandidateProposal, ModeDistribution


@dataclass(frozen=True)
class AgentState:
    run_id: str
    profile_id: str
    model_id: str
    step: int
    current_solution_path: Path
    current_solution_source: str
    visible_history: list[dict[str, Any]]
    profile_summary: dict[str, Any]
    residual_steps: int
    residual_wall_seconds: float | None
    visibility_regime: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentAdapter(Protocol):
    model_id: str

    def propose_mode_distribution(self, state: AgentState) -> ModeDistribution:
        ...

    def propose_edit_for_mode(self, state: AgentState, mode: str, branch_dir: Path) -> CandidateProposal:
        ...

    def propose_step_single(self, state: AgentState, branch_dirs: dict[str, Path]) -> tuple[ModeDistribution, CandidateProposal]:
        ...

    def propose_single_prompt_trajectory(self, state: AgentState, max_steps: int) -> dict[str, Any]:
        ...
