"""Score computation for the stateful query engine benchmark."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from benchmarks.stateful_query_engine.harness.evaluate_perf import PerfEvaluation
from benchmarks.stateful_query_engine.harness.verify_correctness import CorrectnessResult


@dataclass
class ScoreResult:
    latent_loss: float
    family_losses: dict[str, float]
    weights: dict[str, float]
    correct: bool

    def to_dict(self) -> dict:
        return {
            "latent_loss": self.latent_loss,
            "family_losses": self.family_losses,
            "weights": self.weights,
            "correct": self.correct,
        }


def compute_score(
    correctness: CorrectnessResult,
    candidate_perf: PerfEvaluation | None,
    baseline_perf: PerfEvaluation,
    *,
    latency_weight: float,
    memory_weight: float,
) -> ScoreResult:
    weights = {"latency": latency_weight, "peak_memory": memory_weight}
    if not correctness.passed or candidate_perf is None:
        return ScoreResult(
            latent_loss=math.inf,
            family_losses={},
            weights=weights,
            correct=False,
        )
    family_losses: dict[str, float] = {}
    for family, cand in candidate_perf.family_metrics.items():
        base = baseline_perf.family_metrics[family]
        latency_ratio = cand["median_p95_latency_ns"] / max(base["median_p95_latency_ns"], 1.0)
        memory_ratio = cand["median_peak_memory_bytes"] / max(base["median_peak_memory_bytes"], 1.0)
        family_losses[family] = latency_weight * latency_ratio + memory_weight * memory_ratio
    latent_loss = statistics.fmean(family_losses.values()) if family_losses else math.inf
    return ScoreResult(
        latent_loss=latent_loss,
        family_losses=family_losses,
        weights=weights,
        correct=True,
    )

