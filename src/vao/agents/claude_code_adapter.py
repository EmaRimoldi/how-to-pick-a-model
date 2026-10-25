"""Claude Code adapter scaffold.

The old repository contains a detailed Claude Code subprocess adapter. The new
protocol needs a stricter two-stage interface: distribution first, then one
mode-constrained candidate per mode. This scaffold keeps that interface stable
and uses the deterministic local backend when the external CLI is unavailable.
"""

from __future__ import annotations

from pathlib import Path

from vao.agents.base import AgentState
from vao.agents.local_stub_adapter import LocalStubAdapter
from vao.schemas import CandidateProposal, ModeDistribution


class ClaudeCodeAdapter:
    def __init__(self, model_id: str, **kwargs: object) -> None:
        self.model_id = model_id
        self.config = kwargs
        self._fallback = LocalStubAdapter(model_id=f"{model_id}:local_stub_fallback")

    def propose_mode_distribution(self, state: AgentState) -> ModeDistribution:
        distribution = self._fallback.propose_mode_distribution(state)
        distribution.parsed_json = {
            **(distribution.parsed_json or {}),
            "adapter_fallback": "claude_code_local_stub",
        }
        return distribution

    def propose_edit_for_mode(self, state: AgentState, mode: str, branch_dir: Path) -> CandidateProposal:
        proposal = self._fallback.propose_edit_for_mode(state, mode, branch_dir)
        proposal.parsed_output_json = {
            **(proposal.parsed_output_json or {}),
            "adapter_fallback": "claude_code_local_stub",
        }
        return proposal
