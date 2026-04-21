"""Deterministic data generation for stateful query engine traces."""

from __future__ import annotations

import random


def generate_initial_items(
    *,
    seed: int,
    size: int,
    key_space: int,
    value_min: int = 1,
    value_max: int = 1000,
) -> dict[int, int]:
    rng = random.Random(seed)
    if size > key_space:
        raise ValueError("size must be <= key_space")
    keys = rng.sample(range(key_space), size)
    return {key: rng.randint(value_min, value_max) for key in keys}

