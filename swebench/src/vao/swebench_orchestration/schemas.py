"""Schemas for distribution-aware orchestration on SWE-bench."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ModeKind = Literal[
    "repo_family",
    "test_localizable",
    "semantic_api",
    "multi_file",
    "numeric_symbolic",
    "dependency_config",
    "unknown",
]


class SWEInstancePublic(BaseModel):
    """Leakage-safe SWE-bench instance record for meta-design prompts."""

    model_config = ConfigDict(extra="allow")

    instance_id: str
    repo: str
    base_commit: str | None = None
    problem_statement: str
    hints_text: str | None = None
    created_at: str | None = None
    version: str | None = None
    declared_mode: str = "unknown"
    public_fields: dict[str, Any] = Field(default_factory=dict)


class ModeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode_id: str
    description: str
    observable_signals: list[str] = Field(default_factory=list)
    expected_strategy: str
    expected_difficulty: Literal["low", "medium", "high", "unknown"] = "unknown"


class ComponentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str
    role: Literal["controller", "localizer", "patcher", "reviewer", "tester", "router", "fallback"]
    model: str
    prompt_summary: str
    max_calls: int = Field(ge=0)
    tools: list[str] = Field(default_factory=list)
    output_contract: str


class ComplexitySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agents: int = Field(ge=1)
    model_families: int = Field(ge=1)
    prompt_templates: int = Field(ge=1)
    routing_branches: int = Field(ge=0)
    tool_policies: int = Field(ge=0)
    max_patch_proposals: int = Field(ge=1)
    context_budget_tokens: int = Field(ge=0)

    def score(self) -> float:
        return (
            1.0 * self.agents
            + 1.0 * self.model_families
            + 0.5 * self.prompt_templates
            + 0.75 * self.routing_branches
            + 0.5 * self.tool_policies
            + 0.25 * self.max_patch_proposals
            + self.context_budget_tokens / 100_000.0
        )


class OrchestrationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orchestration_id: str
    name: str
    orchestration_type: Literal["universal", "mode_specialist", "hierarchical_routed"]
    target_modes: list[str] = Field(default_factory=list)
    objective_summary: str
    components: list[ComponentSpec]
    routing_policy: str
    evidence_policy: str
    patch_policy: str
    verification_policy: str
    fallback_policy: str
    stopping_rule: str
    complexity: ComplexitySpec
    expected_failure_modes: list[str] = Field(default_factory=list)

    @field_validator("components")
    @classmethod
    def components_nonempty(cls, value: list[ComponentSpec]) -> list[ComponentSpec]:
        if not value:
            raise ValueError("orchestration must contain at least one component")
        return value


class OrchestrationDesign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    evidence_level: str
    benchmark: str = "SWE-bench"
    assumptions: list[str]
    mode_taxonomy: list[ModeSpec]
    orchestrations: list[OrchestrationSpec]
    optimization_loss: str
    logging_plan: list[str]
    expected_tradeoffs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_orchestrations(self) -> "OrchestrationDesign":
        if not self.orchestrations:
            raise ValueError("design must contain at least one orchestration")
        orchestration_ids = [item.orchestration_id for item in self.orchestrations]
        duplicates = sorted({item for item in orchestration_ids if orchestration_ids.count(item) > 1})
        if duplicates:
            raise ValueError(f"duplicate orchestration ids: {duplicates}")
        return self


class TraceStep(BaseModel):
    """One logged action from a generated orchestration run."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    orchestration_id: str
    evidence_level: str = "E0"
    instance_id: str
    repo: str | None = None
    mode: str = "unknown"
    split: str = "unspecified"
    step: int = Field(ge=1)
    phase: Literal["observe", "localize", "patch", "review", "verify", "fallback", "other"] = "other"
    agent_id: str | None = None
    model_id: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    api_cost_usd: float = Field(default=0.0, ge=0.0)
    wall_seconds: float = Field(default=0.0, ge=0.0)
    test_seconds: float = Field(default=0.0, ge=0.0)
    verifier_calls: int = Field(default=0, ge=0)
    patch_id: str | None = None
    verified: bool = False
    used_in_verified_path: bool = True
    error: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def scalar_cost(self, *, token_weight: float, wall_weight: float, test_weight: float, api_weight: float) -> float:
        return (
            token_weight * float(self.total_tokens)
            + wall_weight * self.wall_seconds
            + test_weight * self.test_seconds
            + api_weight * self.api_cost_usd
        )
