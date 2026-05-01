"""Shared success-threshold helpers for AutoResearch trajectory evaluation."""

from __future__ import annotations

import math
from typing import Iterable


DEFAULT_SUCCESS_THRESHOLD_RELATIVE = 0.05


def validate_relative_threshold(value: float | int | None) -> float:
    threshold = DEFAULT_SUCCESS_THRESHOLD_RELATIVE if value is None else float(value)
    if not math.isfinite(threshold):
        raise ValueError("relative success threshold must be finite")
    if threshold < 0.0:
        raise ValueError("relative success threshold must be non-negative")
    return threshold


def relative_improvement(baseline_loss: float | int | None, best_loss: float | int | None) -> float:
    if baseline_loss is None or best_loss is None:
        return 0.0
    baseline = float(baseline_loss)
    best = float(best_loss)
    if not math.isfinite(baseline) or baseline <= 0.0 or not math.isfinite(best):
        return 0.0
    return max(0.0, (baseline - best) / baseline)


def success_on_relative_threshold(
    baseline_loss: float | int | None,
    best_loss: float | int | None,
    *,
    threshold: float | int | None,
) -> bool:
    return relative_improvement(baseline_loss, best_loss) >= validate_relative_threshold(threshold)


def first_success_step(
    baseline_loss: float | int | None,
    best_losses_by_step: Iterable[float | int | None],
    *,
    threshold: float | int | None,
) -> int | None:
    threshold_value = validate_relative_threshold(threshold)
    running_best = float(baseline_loss) if baseline_loss is not None else math.inf
    if not math.isfinite(running_best):
        running_best = math.inf
    for step_index, loss in enumerate(best_losses_by_step, start=1):
        if loss is None:
            continue
        try:
            candidate = float(loss)
        except (TypeError, ValueError):
            continue
        if math.isfinite(candidate):
            running_best = min(running_best, candidate)
        if success_on_relative_threshold(baseline_loss, running_best, threshold=threshold_value):
            return step_index
    return None
