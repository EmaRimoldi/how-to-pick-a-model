"""Estimator functions for branch tensors and run records."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from vao.schemas import StepRecord
from vao.taxonomy import MODES, normalize_mode_probs, validate_mode


def gain(parent_loss: float, branch_loss: float, correct: bool, incorrect_penalty: float) -> float:
    if not correct:
        return float(incorrect_penalty)
    if not math.isfinite(branch_loss):
        return float(incorrect_penalty)
    if not math.isfinite(parent_loss):
        return 0.0
    return float(parent_loss - branch_loss)


def productive_mode_proxy(gains: dict[str, float], fallback: str = "uniform") -> dict[str, float]:
    _validate_gain_keys(gains)
    if fallback == "hard_argmax":
        best = max(MODES, key=lambda mode: gains[mode])
        return {mode: 1.0 if mode == best else 0.0 for mode in MODES}
    positive = {mode: max(0.0, float(gains[mode])) for mode in MODES}
    total = sum(positive.values())
    if total > 0:
        return {mode: positive[mode] / total for mode in MODES}
    if fallback == "uniform":
        return {mode: 1.0 / len(MODES) for mode in MODES}
    if fallback == "argmax":
        best = max(MODES, key=lambda mode: gains[mode])
        return {mode: 1.0 if mode == best else 0.0 for mode in MODES}
    raise ValueError(f"Unknown productive proxy fallback: {fallback}")


def routing_regret(gains: dict[str, float], selected_mode: str) -> float:
    _validate_gain_keys(gains)
    validate_mode(selected_mode)
    return float(max(gains.values()) - gains[selected_mode])


def jsd(p: dict[str, float], q: dict[str, float]) -> float:
    p = normalize_mode_probs(p)
    q = normalize_mode_probs(q)
    pv = np.array([p[mode] for mode in MODES], dtype=float)
    qv = np.array([q[mode] for mode in MODES], dtype=float)
    m = 0.5 * (pv + qv)
    return float(0.5 * _kl(pv, m) + 0.5 * _kl(qv, m))


def routing_mismatch_jsd(step: StepRecord) -> float:
    gains = gains_by_mode(step)
    pstar = productive_mode_proxy(gains)
    return jsd(step.mode_probs, pstar)


def routing_mismatch_jSd(step: StepRecord) -> float:
    return routing_mismatch_jsd(step)


def gains_by_mode(step: StepRecord) -> dict[str, float]:
    gains = {mode: 0.0 for mode in MODES}
    for branch in step.branches:
        gains[branch.declared_mode] = float(branch.gain)
    return gains


def runtime_phi(records: list[StepRecord]) -> pd.DataFrame:
    rows = []
    for record in records:
        for branch in record.branches:
            rows.append(
                {
                    "model_id": record.model_id,
                    "profile_id": record.profile_id,
                    "mode": branch.inferred_mode,
                    "declared_mode": branch.declared_mode,
                    "gain": branch.gain,
                    "correctness": branch.correctness,
                }
            )
    if not rows:
        return pd.DataFrame(columns=["model_id", "profile_id", "mode", "mean_gain", "median_gain", "count"])
    frame = pd.DataFrame(rows)
    return (
        frame.groupby(["model_id", "profile_id", "mode"], as_index=False)
        .agg(mean_gain=("gain", "mean"), median_gain=("gain", "median"), count=("gain", "size"))
        .sort_values(["model_id", "profile_id", "mode"])
    )


def endpoint_best_loss(records: list[StepRecord]) -> float:
    losses = []
    for record in records:
        for branch in record.branches:
            if branch.promoted_as_parent and branch.correctness and math.isfinite(branch.latent_loss):
                losses.append(branch.latent_loss)
    return min(losses) if losses else math.inf


def success_above_threshold(records: list[StepRecord], threshold: float) -> bool:
    best = endpoint_best_loss(records)
    return math.isfinite(best) and best <= threshold


def cost_per_step(records: list[StepRecord]) -> dict[str, float | None]:
    if not records:
        return {"median_wall_seconds": None, "median_tokens": None, "median_usd": None}
    wall = [
        sum((branch.elapsed_wall_seconds or 0.0) for branch in record.branches)
        for record in records
    ]
    tokens = [
        (record.input_tokens or 0) + (record.output_tokens or 0)
        for record in records
        if record.input_tokens is not None or record.output_tokens is not None
    ]
    usd = [record.agent_cost_usd for record in records if record.agent_cost_usd is not None]
    return {
        "median_wall_seconds": statistics.median(wall) if wall else None,
        "median_tokens": statistics.median(tokens) if tokens else None,
        "median_usd": statistics.median(usd) if usd else None,
    }


def alignment_gain(pre: dict[str, float], post: dict[str, float], pstar: dict[str, float]) -> float:
    return jsd(pre, pstar) - jsd(post, pstar)


def aggregate_run(records: list[StepRecord], success_threshold: float = 1.0) -> dict[str, Any]:
    if not records:
        return {}
    regrets = []
    jsds = []
    invalid = []
    gain_by_mode: dict[str, list[float]] = defaultdict(list)
    for record in records:
        gains = gains_by_mode(record)
        regrets.append(routing_regret(gains, record.selected_mode))
        jsds.append(jsd(record.mode_probs, productive_mode_proxy(gains)))
        invalid.extend([not branch.correctness for branch in record.branches])
        for mode, value in gains.items():
            gain_by_mode[mode].append(value)
    costs = cost_per_step(records)
    result = {
        "run_id": records[0].run_id,
        "profile_id": records[0].profile_id,
        "model_id": records[0].model_id,
        "visibility_regime": records[0].visibility_regime,
        "best_loss": endpoint_best_loss(records),
        "success": success_above_threshold(records, success_threshold),
        "mean_routing_regret": statistics.fmean(regrets) if regrets else math.nan,
        "mean_jsd": statistics.fmean(jsds) if jsds else math.nan,
        "mean_cost_wall": costs["median_wall_seconds"],
        "mean_cost_tokens": costs["median_tokens"],
        "invalid_rate": statistics.fmean(invalid) if invalid else 0.0,
    }
    for mode in MODES:
        values = gain_by_mode.get(mode, [])
        result[f"mean_gain_{mode}"] = statistics.fmean(values) if values else math.nan
    return result


def _kl(a: np.ndarray, b: np.ndarray) -> float:
    mask = a > 0
    return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))


def _validate_gain_keys(gains: dict[str, float]) -> None:
    keys = set(gains)
    if keys != set(MODES):
        raise ValueError(f"gains must contain exactly the six modes; got {sorted(keys)}")
