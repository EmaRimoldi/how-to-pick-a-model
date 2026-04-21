"""Visibility policies for online agent state."""

from __future__ import annotations

import math
from typing import Any

from vao.schemas import StepRecord


def build_visible_history(records: list[StepRecord], regime: str) -> list[dict[str, Any]]:
    if regime not in {"top1_only", "all_branches"}:
        raise ValueError(f"Unknown visibility regime: {regime}")
    visible: list[dict[str, Any]] = []
    for record in records:
        if regime == "all_branches":
            branches = record.branches
        else:
            branches = [branch for branch in record.branches if branch.selected_as_visible]
        visible.append(
            {
                "step": record.step,
                "selected_mode": record.selected_mode,
                "selected_mode_top1": record.selected_mode_top1,
                "selection_policy": record.selection_policy,
                "mode_probs": record.mode_probs,
                "post_feedback_mode_probs": record.post_feedback_mode_probs,
                "feedback_regret_improvement": record.feedback_regret_improvement,
                "feedback_jsd_improvement": record.feedback_jsd_improvement,
                "branches": [
                    {
                        "primary_mode": branch.primary_mode,
                        "declared_mode": branch.declared_mode,
                        "inferred_mode": branch.inferred_mode,
                        "correctness": branch.correctness,
                        "latent_loss": _finite_or_none(branch.latent_loss),
                        "gain": _finite_or_none(branch.gain),
                        "family_losses": branch.family_losses,
                    }
                    for branch in branches
                ],
            }
        )
    return visible


def summarize_history_for_prompt(records: list[StepRecord], max_rows: int = 12) -> str:
    rows = []
    for record in records[-max_rows:]:
        selected = next((branch for branch in record.branches if branch.promoted_as_parent), None)
        rows.append(
            {
                "step": record.step,
                "selected_mode": record.selected_mode,
                "selected_loss": _finite_or_none(selected.latent_loss) if selected else None,
                "selected_correct": selected.correctness if selected else None,
            }
        )
    return "\n".join(str(row) for row in rows)


def _finite_or_none(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return float(value)
