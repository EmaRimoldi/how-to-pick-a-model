"""Diversity metrics for prompts, trajectories, and model weights.

The optional embedding and weight-space metrics import heavy dependencies
inside their functions so the canonical CLI and lightweight tests do not require
GPU or ML packages.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence


def load_trajectory(jsonl_path: str | Path) -> list[float]:
    """Load a `val_bpb` trajectory from a JSONL file."""
    values: list[float] = []
    with Path(jsonl_path).open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            entry = json.loads(line)
            values.append(float(entry["val_bpb"]))
    return values


def dtw_distance(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute a simple dynamic-time-warping distance without external deps."""
    if not left or not right:
        raise ValueError("DTW requires two non-empty sequences")
    prev = [float("inf")] * (len(right) + 1)
    prev[0] = 0.0
    for x in left:
        curr = [float("inf")] * (len(right) + 1)
        for j, y in enumerate(right, start=1):
            cost = abs(float(x) - float(y))
            curr[j] = cost + min(curr[j - 1], prev[j], prev[j - 1])
        prev = curr
    return float(prev[-1])


def mean_pairwise_dtw_distance(series: Iterable[Sequence[float]]) -> float:
    """Return mean pairwise DTW distance across trajectories."""
    seqs = [list(s) for s in series]
    pairs = list(combinations(seqs, 2))
    if not pairs:
        return 0.0
    return sum(dtw_distance(a, b) for a, b in pairs) / len(pairs)


def measure_h_post_trajectory(
    trajectories_dir: str | Path,
    run_id: str,
) -> float:
    """Compute H_post trajectory as mean pairwise DTW over agent JSONL files."""
    run_dir = Path(trajectories_dir) / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"No trajectory directory: {run_dir}")

    trajectories = [
        load_trajectory(path)
        for path in sorted(run_dir.glob("*.jsonl"))
    ]
    return mean_pairwise_dtw_distance(trajectories)


def measure_h_prior(prompt_dir: str | Path, model_name: str = "all-MiniLM-L6-v2") -> float:
    """Compute mean pairwise cosine distance between prompt embeddings."""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    prompt_paths = sorted(Path(prompt_dir).glob("*.md"))
    texts = [path.read_text(encoding="utf-8") for path in prompt_paths]
    if len(texts) < 2:
        return 0.0

    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, normalize_embeddings=True)
    distances = []
    for i, j in combinations(range(len(embeddings)), 2):
        cosine_sim = float(np.dot(embeddings[i], embeddings[j]))
        distances.append(1.0 - cosine_sim)
    return float(np.mean(distances))


def measure_h_post_weights(weights_dir: str | Path, run_id: str) -> dict[str, object]:
    """Compute lightweight weight-space diversity metrics for `model.pt` files."""
    import numpy as np
    import torch
    from scipy.stats import entropy as scipy_entropy

    def load_weights_flat(path: Path):
        try:
            state_dict = torch.load(path, map_location="cpu", weights_only=True)
        except TypeError:
            state_dict = torch.load(path, map_location="cpu")
        return np.concatenate([v.numpy().flatten() for v in state_dict.values()])

    run_dir = Path(weights_dir) / run_id
    weights = {
        agent_dir.name: load_weights_flat(agent_dir / "model.pt")
        for agent_dir in sorted(run_dir.iterdir()) if (agent_dir / "model.pt").exists()
    }
    if len(weights) < 2:
        return {"pairwise_l2_mean": None, "per_model_entropy": {}, "sharpness_proxy": {}}

    l2_distances = [
        float(np.linalg.norm(a - b))
        for a, b in combinations(weights.values(), 2)
    ]
    entropies = {}
    sharpness = {}
    for agent_id, flat in weights.items():
        hist, _ = np.histogram(flat, bins=100, density=True)
        hist = hist + 1e-10
        hist = hist / hist.sum()
        entropies[agent_id] = float(scipy_entropy(hist))
        sharpness[agent_id] = float(np.std(flat))

    return {
        "pairwise_l2_mean": float(np.mean(l2_distances)),
        "per_model_entropy": entropies,
        "sharpness_proxy": sharpness,
    }
