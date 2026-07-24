"""Deterministic local stub for the AutoResearch CIFAR-10 benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vao.agents.base import AgentState
from vao.logging_utils import sha256_file, sha256_text
from vao.schemas import CandidateProposal, ModeDistribution
from vao.structured_edits import StructuredEditError, apply_structured_edits
from vao.taxonomy import MODES


class AutoResearchLocalStubAdapter:
    """Heuristic batch proposer for the AutoResearch CIFAR-10 task.

    The stub does not try to be globally optimal. It encodes a few simple
    training heuristics so the new benchmark can run end-to-end without live
    model calls.
    """

    def __init__(self, model_id: str = "autoresearch-local-stub", **kwargs: object) -> None:
        self.model_id = model_id
        self.config = kwargs

    def propose_step_batch(self, state: AgentState, branch_dirs: dict[str, Path]) -> tuple[ModeDistribution, dict[str, CandidateProposal]]:
        parent_source = (branch_dirs[MODES[0]] / "parent_solution.py").read_text(encoding="utf-8")
        scores = _mode_scores(state.profile_summary)
        total = sum(scores.values())
        mode_probs = {mode: scores[mode] / total for mode in MODES}
        ranking = sorted(MODES, key=lambda mode: mode_probs[mode], reverse=True)
        distribution = ModeDistribution(
            mode_probs=mode_probs,
            mode_ranking=ranking,
            mode_rationales={mode: _mode_rationale(state.profile_summary, mode) for mode in MODES},
            raw_text=json.dumps({"mode_probs": mode_probs}, sort_keys=True),
            parsed_json={
                "adapter": "autoresearch_local_stub",
                "benchmark_id": "autoresearch_cifar10",
                "prompt_template": state.metadata.get("prompt_template"),
            },
        )

        proposals: dict[str, CandidateProposal] = {}
        prompt_hash = sha256_text(parent_source + json.dumps(state.profile_summary, sort_keys=True))
        for mode in MODES:
            branch_dir = branch_dirs[mode]
            parent_path = branch_dir / "parent_solution.py"
            proposed_path = branch_dir / "proposed_solution.py"
            model_edit_path = branch_dir / "model_edit.json"
            edits = _candidate_edits(mode, state.profile_summary)
            errors: list[str] = []
            validation_failures: list[str] = []
            try:
                proposed_source = apply_structured_edits(parent_source, edits)
            except StructuredEditError as exc:
                proposed_source = parent_source
                errors.append(f"structured_edit_failed:{exc}")
                validation_failures.append("structured_edit_failed")
            proposed_path.write_text(proposed_source, encoding="utf-8")
            model_edit_path.write_text(json.dumps(edits, indent=2, sort_keys=True), encoding="utf-8")
            proposals[mode] = CandidateProposal(
                branch_index=MODES.index(mode),
                primary_mode=mode,
                secondary_modes=[],
                declared_mode=mode,
                source_hash=sha256_file(proposed_path),
                source_parent_hash=sha256_file(parent_path),
                file_path=str(proposed_path),
                raw_output_text=json.dumps({"mode": mode, "edits": edits}, sort_keys=True),
                parsed_output_json={
                    "edits": edits,
                    "edit_protocol": "structured_edits",
                    "candidate_generation": "batched_structured_edits",
                    "adapter": "autoresearch_local_stub",
                    "benchmark_id": "autoresearch_cifar10",
                    "mode_description": state.profile_summary.get("task_mode_descriptions", {}).get(mode),
                },
                prompt_hash=prompt_hash,
                changed=sha256_file(parent_path) != sha256_file(proposed_path),
                errors=errors,
                validation_failures=validation_failures,
            )
        return distribution, proposals

    def propose_step_single(self, state: AgentState, branch_dirs: dict[str, Path]) -> tuple[ModeDistribution, CandidateProposal]:
        distribution, proposals = self.propose_step_batch(state, branch_dirs)
        selected_mode = distribution.top_mode
        one_hot = {
            mode: (1.0 if mode == selected_mode else 0.0)
            for mode in MODES
        }
        single_distribution = ModeDistribution(
            mode_probs=one_hot,
            mode_ranking=[selected_mode, *[mode for mode in MODES if mode != selected_mode]],
            mode_rationales={
                mode: (
                    distribution.mode_rationales.get(mode, "")
                    if mode == selected_mode
                    else ""
                )
                for mode in MODES
            },
            raw_text=distribution.raw_text,
            parsed_json={
                **(distribution.parsed_json or {}),
                "candidate_generation": "single_autoresearch_local_stub",
                "selected_mode": selected_mode,
            },
        )
        proposal = proposals[selected_mode]
        proposal.parsed_output_json = {
            **(proposal.parsed_output_json or {}),
            "candidate_generation": "single_autoresearch_local_stub",
            "usage_accounted_on_distribution": True,
        }
        return single_distribution, proposal


def _mode_scores(profile_summary: dict[str, Any]) -> dict[str, float]:
    task_mode = str(profile_summary.get("task_mode_true") or "")
    label_noise = float(profile_summary.get("label_noise_rate", 0.0))
    imbalance_ratio = float(profile_summary.get("imbalance_ratio", 1.0))
    max_steps = int(profile_summary.get("max_train_steps", 0))
    scores = {mode: 1.0 for mode in MODES}
    if max_steps <= 2:
        scores["topk"] += 1.6
        scores["micro"] += 0.8
    else:
        scores["summaries"] += 1.4
        scores["layout"] += 0.6
    if label_noise > 0.0:
        scores["caching"] += 1.8
        scores["indexing"] += 0.7
    if imbalance_ratio < 0.999:
        scores["indexing"] += 1.2
        scores["micro"] += 0.4
    if task_mode == "cnn_compact":
        scores["topk"] += 2.2 if max_steps <= 256 else 0.4
        scores["micro"] += 0.6
    elif task_mode == "mlp_flat":
        scores["indexing"] += 2.2
        scores["micro"] += 0.6
    elif task_mode in {"resnet_micro", "resnet_tiny"}:
        scores["layout"] += 2.0
        scores["summaries"] += 0.8
    return scores


def _mode_rationale(profile_summary: dict[str, Any], mode: str) -> str:
    task_mode = profile_summary.get("task_mode_true", "unknown")
    aliases = profile_summary.get("action_mode_aliases", {})
    if mode == "topk" and task_mode == "cnn_compact":
        return f"{task_mode}: compact convolutional training often responds quickly to learning-rate scale."
    if mode == "indexing" and task_mode == "mlp_flat":
        return f"{task_mode}: optimizer dynamics and coverage are the main bottleneck."
    if mode == "layout" and task_mode in {"resnet_micro", "resnet_tiny"}:
        return f"{task_mode}: model capacity is likely to dominate."
    return f"{task_mode}: heuristic allocation for {aliases.get(mode, mode)}."


def _candidate_edits(mode: str, profile_summary: dict[str, Any]) -> list[dict[str, Any]]:
    task_mode = str(profile_summary.get("task_mode_true") or "")
    max_steps = int(profile_summary.get("max_train_steps", 0))
    label_noise = float(profile_summary.get("label_noise_rate", 0.0))
    imbalance_ratio = float(profile_summary.get("imbalance_ratio", 1.0))

    if mode == "layout":
        capacity_like = task_mode in {"resnet_micro", "resnet_tiny"}
        depth = 3 if capacity_like else 2
        base_channels = 16 if capacity_like else 12
        fc_hidden = 64 if capacity_like else 48
        return [
            {"op": "replace_exact", "old": "DEPTH = 2", "new": f"DEPTH = {depth}"},
            {"op": "replace_exact", "old": "BASE_CHANNELS = 12", "new": f"BASE_CHANNELS = {base_channels}"},
            {"op": "replace_exact", "old": "FC_HIDDEN = 48", "new": f"FC_HIDDEN = {fc_hidden}"},
        ]
    if mode == "indexing":
        optimizer = "sgd" if task_mode == "mlp_flat" or imbalance_ratio < 0.999 else "adamw"
        return [
            {"op": "replace_exact", "old": 'OPTIMIZER = "adam"', "new": f'OPTIMIZER = "{optimizer}"'},
            {"op": "replace_exact", "old": "MOMENTUM = 0.9", "new": "MOMENTUM = 0.95"},
            {"op": "replace_exact", "old": "ADAM_BETAS = (0.9, 0.999)", "new": "ADAM_BETAS = (0.9, 0.99)"},
        ]
    if mode == "topk":
        lr = 0.0015 if task_mode == "cnn_compact" or max_steps <= 2 else 0.0008
        return [
            {"op": "replace_exact", "old": "LEARNING_RATE = 5e-4", "new": f"LEARNING_RATE = {lr}"},
        ]
    if mode == "caching":
        weight_decay = 5e-4 if label_noise > 0.0 else 2e-4
        dropout = 0.15 if label_noise > 0.0 else 0.05
        return [
            {"op": "replace_exact", "old": "WEIGHT_DECAY = 1e-4", "new": f"WEIGHT_DECAY = {weight_decay}"},
            {"op": "replace_exact", "old": "DROPOUT_RATE = 0.0", "new": f"DROPOUT_RATE = {dropout}"},
        ]
    if mode == "summaries":
        return [
            {"op": "replace_exact", "old": "USE_LR_SCHEDULE = False", "new": "USE_LR_SCHEDULE = True"},
            {"op": "replace_exact", "old": "WARMUP_EPOCHS = 2", "new": "WARMUP_EPOCHS = 1"},
            {"op": "replace_exact", "old": "LR_DECAY_FACTOR = 0.1", "new": "LR_DECAY_FACTOR = 0.2"},
        ]
    return [
        {"op": "replace_exact", "old": "BATCH_SIZE = 64", "new": "BATCH_SIZE = 48" if max_steps <= 2 else "BATCH_SIZE = 96"},
    ]
