"""OpenAI-compatible adapter scaffold for future local/open-weight serving."""

from __future__ import annotations

from pathlib import Path

from vao.agents.base import AgentState
from vao.agents.local_stub_adapter import LocalStubAdapter
from vao.schemas import CandidateProposal, ModeDistribution


class OpenAICompatibleAdapter:
    """Config-compatible placeholder.

    The routing protocol does not depend on vendor-specific APIs. Until a
    vLLM/SGLang endpoint is configured, this adapter falls back to the local
    deterministic backend and records the configured model id.
    """

    def __init__(self, model_id: str, **kwargs: object) -> None:
        self.model_id = model_id
        self.config = kwargs
        self._fallback = LocalStubAdapter(model_id=f"{model_id}:local_stub_fallback")

    def propose_mode_distribution(self, state: AgentState) -> ModeDistribution:
        return self._fallback.propose_mode_distribution(state)

    def propose_edit_for_mode(self, state: AgentState, mode: str, branch_dir: Path) -> CandidateProposal:
        proposal = self._fallback.propose_edit_for_mode(state, mode, branch_dir)
        proposal.parsed_output_json = {
            **(proposal.parsed_output_json or {}),
            "adapter_fallback": "openai_compatible_local_stub",
        }
        return proposal
