"""Pydantic schemas for protocol records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vao.taxonomy import MODES, MODE_SET, normalize_mode_probs, validate_mode


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModeDistribution(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode_probs: dict[str, float]
    mode_ranking: list[str]
    mode_rationales: dict[str, str] = Field(default_factory=dict)
    raw_text: str | None = None
    parsed_json: dict[str, Any] | None = None
    retries: int = 0
    agent_contract_failed: bool = False
    validation_failures: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_contract(self) -> "ModeDistribution":
        self.mode_probs = normalize_mode_probs(self.mode_probs)
        if set(self.mode_ranking) != MODE_SET or len(self.mode_ranking) != len(MODES):
            raise ValueError("mode_ranking must be a permutation of the six modes")
        self.mode_ranking = list(self.mode_ranking)
        for mode in self.mode_ranking:
            validate_mode(mode)
        if not self.mode_rationales:
            self.mode_rationales = {mode: "" for mode in MODES}
        if set(self.mode_rationales) != MODE_SET:
            self.mode_rationales = {mode: str(self.mode_rationales.get(mode, "")) for mode in MODES}
        return self

    @property
    def top_mode(self) -> str:
        return max(MODES, key=lambda mode: self.mode_probs[mode])


class CandidateProposal(BaseModel):
    model_config = ConfigDict(extra="allow")

    branch_index: int
    primary_mode: str
    secondary_modes: list[str] = Field(default_factory=list)
    declared_mode: str
    source_hash: str
    source_parent_hash: str
    file_path: str
    raw_output_text: str | None = None
    parsed_output_json: dict[str, Any] | None = None
    prompt_hash: str | None = None
    changed: bool = True
    errors: list[str] = Field(default_factory=list)
    validation_failures: list[str] = Field(default_factory=list)

    @field_validator("primary_mode", "declared_mode")
    @classmethod
    def validate_primary_mode(cls, value: str) -> str:
        return validate_mode(value)

    @field_validator("secondary_modes")
    @classmethod
    def validate_secondary_modes(cls, value: list[str]) -> list[str]:
        return [validate_mode(mode) for mode in value]


class BranchEvaluation(BaseModel):
    model_config = ConfigDict(extra="allow")

    branch_index: int = 0
    primary_mode: str
    secondary_modes: list[str] = Field(default_factory=list)
    declared_mode: str
    inferred_mode: str
    source_hash: str
    source_parent_hash: str | None = None
    file_path: str
    model_edit_path: str | None = None
    correctness: bool
    latent_loss: float
    gain: float = 0.0
    family_losses: dict[str, float] = Field(default_factory=dict)
    first_divergence: dict[str, Any] | None = None
    selected_as_visible: bool = False
    promoted_as_parent: bool = False
    median_p95_latency_ns: float | None = None
    median_peak_memory_bytes: float | None = None
    raw_verifier_path: str | None = None
    elapsed_wall_seconds: float | None = None
    accounting_cost: float | None = None
    validation_failures: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @field_validator("primary_mode", "declared_mode", "inferred_mode")
    @classmethod
    def validate_modes(cls, value: str) -> str:
        return validate_mode(value)


class StepRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str
    profile_id: str
    model_id: str
    model_alias: str | None = None
    task_mode_true: str | None = None
    task_mode_source: str | None = None
    task_mode_split: str | None = None
    instance_seed: int | None = None
    step: int
    timestamp: str = Field(default_factory=utc_now_iso)
    current_solution_hash: str
    parent_solution_hash: str
    parent_latent_loss: float | None = None
    mode_probs: dict[str, float]
    mode_ranking: list[str]
    selected_mode_top1: str
    selected_mode: str
    selection_policy: str = "top1"
    selected_mode_reason: str | None = None
    selected_branch: str
    candidate_batch_id: str
    visibility_regime: Literal["top1_only", "all_branches"]
    branches: list[BranchEvaluation]
    residual_steps: int
    residual_wall_seconds: float | None = None
    step_wall_seconds: float | None = None
    agent_cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    model_output_raw_text: str | None = None
    parsed_model_output_json: dict[str, Any] | None = None
    post_feedback_mode_probs: dict[str, float] | None = None
    post_feedback_mode_ranking: list[str] | None = None
    post_feedback_model_output_raw_text: str | None = None
    post_feedback_parsed_model_output_json: dict[str, Any] | None = None
    post_feedback_errors: list[str] = Field(default_factory=list)
    post_feedback_retries: int = 0
    post_feedback_validation_failures: list[str] = Field(default_factory=list)
    feedback_regret_improvement: float | None = None
    feedback_jsd_improvement: float | None = None
    best_visible_so_far: float | None = None
    relative_improvement_so_far: float | None = None
    success_threshold_relative: float | None = None
    successful_step: bool | None = None
    errors: list[str] = Field(default_factory=list)
    retries: int = 0
    validation_failures: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)

    @model_validator(mode="after")
    def validate_step(self) -> "StepRecord":
        self.mode_probs = normalize_mode_probs(self.mode_probs)
        if set(self.mode_ranking) != MODE_SET:
            raise ValueError("mode_ranking must contain exactly the six modes")
        validate_mode(self.selected_mode_top1)
        validate_mode(self.selected_mode)
        if self.selection_policy == "top1" and self.selected_mode_top1 != self.selected_mode:
            raise ValueError("selected_mode_top1 and selected_mode must match in the C(a) protocol")
        if self.post_feedback_mode_probs is not None:
            self.post_feedback_mode_probs = normalize_mode_probs(self.post_feedback_mode_probs)
            if self.post_feedback_mode_ranking is not None and set(self.post_feedback_mode_ranking) != MODE_SET:
                raise ValueError("post_feedback_mode_ranking must contain exactly the six modes")
        return self


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str
    profile_id: str
    model_id: str
    model_alias: str | None = None
    task_mode_true: str | None = None
    task_mode_source: str | None = None
    task_mode_split: str | None = None
    instance_seed: int | None = None
    visibility_regime: Literal["top1_only", "all_branches"]
    modes: list[str]
    max_steps: int
    selection_policy: str = "top1"
    feedback_condition: str = "ca"
    wall_budget_seconds: float | None = None
    success_threshold_relative: float | None = None
    stop_on_success: bool = False
    created_at: str = Field(default_factory=utc_now_iso)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("modes")
    @classmethod
    def validate_modes(cls, value: list[str]) -> list[str]:
        if value != MODES:
            raise ValueError(f"modes must be exactly {MODES}")
        return value


class RoutingRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str
    profile_id: str
    profile_split: str | None = None
    model_id: str
    step: int
    input: dict[str, Any]
    productive_mode_top1: str
    productive_mode_distribution: dict[str, float]
    verified_gain_per_mode: dict[str, float]
    original_mode_probs: dict[str, float]
    original_top1_regret: float
    source_step_record_path: str | None = None

    @model_validator(mode="after")
    def validate_routing_record(self) -> "RoutingRecord":
        validate_mode(self.productive_mode_top1)
        self.productive_mode_distribution = normalize_mode_probs(self.productive_mode_distribution)
        self.original_mode_probs = normalize_mode_probs(self.original_mode_probs)
        if set(self.verified_gain_per_mode) != MODE_SET:
            raise ValueError("verified_gain_per_mode must contain exactly the six modes")
        return self
