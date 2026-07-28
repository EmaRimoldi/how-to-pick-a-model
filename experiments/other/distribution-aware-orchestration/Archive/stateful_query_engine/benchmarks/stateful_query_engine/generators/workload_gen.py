"""Procedural workload generators for hidden stateful query traces."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any

from benchmarks.stateful_query_engine.generators.data_gen import generate_initial_items


QUERY_OPS = {"get", "range_sum", "top_k", "aggregate_count"}
UPDATE_OPS = {"put", "delete"}
ALL_FAMILIES = [
    "uniform_read_heavy",
    "zipf_hot_key",
    "bursty_mixed",
    "range_local_scans",
    "distribution_shift",
    "wide_range_churn",
    "temporal_repeat_windows",
    "topk_stress",
    "negative_lookup_churn",
]


@dataclass
class WorkloadTrace:
    trace_id: str
    family: str
    seed: int
    initial_items: dict[int, int]
    operations: list[dict[str, Any]]
    hidden_params: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "family": self.family,
            "seed": self.seed,
            "initial_size": len(self.initial_items),
            "operation_count": len(self.operations),
            "hidden_param_keys": sorted(self.hidden_params),
        }

    def to_dict(self, include_operations: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_operations:
            data.pop("operations", None)
            data["initial_items"] = {"count": len(self.initial_items)}
        return data


def generate_trace_suite(profile: str, config: dict[str, Any]) -> list[WorkloadTrace]:
    profiles = config["profiles"]
    if profile not in profiles:
        raise KeyError(f"Unknown profile {profile!r}; expected one of {sorted(profiles)}")
    spec = profiles[profile]
    families = spec.get("families") or ALL_FAMILIES
    traces_per_family = int(spec.get("traces_per_family", 1))
    base_seed = int(spec.get("seed", 0))
    traces: list[WorkloadTrace] = []
    for family_index, family in enumerate(families):
        for trace_index in range(traces_per_family):
            seed = base_seed + family_index * 10_000 + trace_index
            traces.append(
                generate_trace(
                    family=family,
                    seed=seed,
                    length=int(spec["trace_length"]),
                    initial_size=int(spec["initial_size"]),
                    key_space=int(spec["key_space"]),
                    value_max=int(spec.get("value_max", 1000)),
                    profile=profile,
                )
            )
    return traces


def generate_trace(
    *,
    family: str,
    seed: int,
    length: int,
    initial_size: int,
    key_space: int,
    value_max: int,
    profile: str,
) -> WorkloadTrace:
    rng = random.Random(seed)
    initial_items = generate_initial_items(
        seed=seed + 101,
        size=initial_size,
        key_space=key_space,
        value_max=value_max,
    )
    if family == "uniform_read_heavy":
        ops, params = _uniform_read_heavy(rng, length, key_space, value_max)
    elif family == "zipf_hot_key":
        ops, params = _zipf_hot_key(rng, length, key_space, value_max, profile)
    elif family == "bursty_mixed":
        ops, params = _bursty_mixed(rng, length, key_space, value_max)
    elif family == "range_local_scans":
        ops, params = _range_local_scans(rng, length, key_space, value_max, profile)
    elif family == "distribution_shift":
        ops, params = _distribution_shift(rng, length, key_space, value_max)
    elif family == "wide_range_churn":
        ops, params = _wide_range_churn(rng, length, key_space, value_max)
    elif family == "temporal_repeat_windows":
        ops, params = _temporal_repeat_windows(rng, length, key_space, value_max)
    elif family == "topk_stress":
        ops, params = _topk_stress(rng, length, key_space, value_max)
    elif family == "negative_lookup_churn":
        ops, params = _negative_lookup_churn(rng, length, key_space, value_max)
    else:
        raise ValueError(f"Unknown workload family: {family}")
    trace_id = f"{profile}_{family}_{seed}"
    return WorkloadTrace(
        trace_id=trace_id,
        family=family,
        seed=seed,
        initial_items=initial_items,
        operations=ops,
        hidden_params=params,
    )


def query_output_expected(op_name: str) -> bool:
    return op_name in QUERY_OPS


def _uniform_read_heavy(
    rng: random.Random,
    length: int,
    key_space: int,
    value_max: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ops = []
    read_probability = 0.82
    range_width = max(5, key_space // 100)
    for _ in range(length):
        if rng.random() < read_probability:
            ops.append(_random_query(rng, key_space, range_width))
        else:
            ops.append(_random_update(rng, key_space, value_max))
    return ops, {"read_probability": read_probability, "range_width": range_width}


def _zipf_hot_key(
    rng: random.Random,
    length: int,
    key_space: int,
    value_max: int,
    profile: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hot_set_size = max(8, key_space // (35 if profile != "holdout" else 25))
    hot_keys = rng.sample(range(key_space), hot_set_size)
    hot_probability = 0.78 if profile != "holdout" else 0.68
    range_width = max(4, key_space // 160)
    ops = []
    for _ in range(length):
        key = rng.choice(hot_keys) if rng.random() < hot_probability else rng.randrange(key_space)
        roll = rng.random()
        if roll < 0.42:
            ops.append({"op": "get", "key": key})
        elif roll < 0.72:
            ops.append(_range_around(rng, key, key_space, range_width))
        elif roll < 0.88:
            ops.append({"op": "put", "key": key, "value": rng.randint(1, value_max)})
        elif roll < 0.94:
            ops.append({"op": "delete", "key": key})
        else:
            lo, hi = _bounds_around(key, key_space, range_width * 2)
            ops.append({"op": "top_k", "lo": lo, "hi": hi, "k": rng.randint(1, 8)})
    return ops, {"hot_set_size": hot_set_size, "hot_probability": hot_probability, "range_width": range_width}


def _bursty_mixed(
    rng: random.Random,
    length: int,
    key_space: int,
    value_max: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ops = []
    phase_length = max(20, length // 8)
    range_width = max(5, key_space // 80)
    for index in range(length):
        write_heavy = (index // phase_length) % 2 == 0
        update_probability = 0.72 if write_heavy else 0.16
        if rng.random() < update_probability:
            ops.append(_random_update(rng, key_space, value_max))
        else:
            center = rng.randrange(key_space)
            if rng.random() < 0.70:
                ops.append(_range_around(rng, center, key_space, range_width))
            else:
                ops.append({"op": "get", "key": center})
    return ops, {"phase_length": phase_length, "write_heavy_update_probability": 0.72, "read_heavy_update_probability": 0.16}


def _range_local_scans(
    rng: random.Random,
    length: int,
    key_space: int,
    value_max: int,
    profile: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ops = []
    width = max(12, key_space // (60 if profile != "holdout" else 45))
    stride = max(3, width // 3)
    center = rng.randrange(key_space)
    for index in range(length):
        if index % 7 == 0:
            center = (center + rng.choice([-stride, stride, stride * 2])) % key_space
        roll = rng.random()
        if roll < 0.36:
            ops.append({"op": "range_sum", **_range_dict(center, key_space, width)})
        elif roll < 0.64:
            ops.append({"op": "aggregate_count", **_range_dict(center, key_space, width)})
        elif roll < 0.82:
            ops.append({"op": "top_k", **_range_dict(center, key_space, width), "k": rng.randint(3, 12)})
        elif roll < 0.92:
            key = _clamp(center + rng.randint(-width, width), 0, key_space - 1)
            ops.append({"op": "put", "key": key, "value": rng.randint(1, value_max)})
        else:
            key = _clamp(center + rng.randint(-width, width), 0, key_space - 1)
            ops.append({"op": "delete", "key": key})
    return ops, {"range_width": width, "stride": stride}


def _distribution_shift(
    rng: random.Random,
    length: int,
    key_space: int,
    value_max: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ops = []
    hot_band_start = rng.randrange(max(1, key_space // 3))
    hot_band_width = max(20, key_space // 6)
    update_probability = 0.24
    topk_probability = 0.24
    for _ in range(length):
        center = _clamp(hot_band_start + rng.randint(0, hot_band_width), 0, key_space - 1)
        roll = rng.random()
        if roll < update_probability:
            ops.append(_random_update_near(rng, center, key_space, value_max, hot_band_width // 4))
        elif roll < update_probability + topk_probability:
            ops.append({"op": "top_k", **_range_dict(center, key_space, hot_band_width // 5), "k": rng.randint(5, 16)})
        elif roll < 0.70:
            ops.append({"op": "range_sum", **_range_dict(center, key_space, hot_band_width // 4)})
        else:
            ops.append({"op": "aggregate_count", **_range_dict(center, key_space, hot_band_width // 4)})
    return ops, {"shift": "hot_band_range_heavy", "hot_band_width": hot_band_width}


def _wide_range_churn(
    rng: random.Random,
    length: int,
    key_space: int,
    value_max: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ops = []
    wide_width = max(50, key_space // 3)
    medium_width = max(20, key_space // 20)
    for index in range(length):
        center = rng.randrange(key_space)
        roll = rng.random()
        if index % 11 in {0, 1, 2}:
            ops.append(_random_update(rng, key_space, value_max))
        elif roll < 0.34:
            ops.append({"op": "range_sum", **_range_dict(center, key_space, wide_width)})
        elif roll < 0.62:
            ops.append({"op": "aggregate_count", **_range_dict(center, key_space, wide_width)})
        elif roll < 0.76:
            ops.append({"op": "top_k", **_range_dict(center, key_space, medium_width), "k": rng.randint(8, 24)})
        else:
            ops.append(_random_update(rng, key_space, value_max))
    return ops, {"wide_width": wide_width, "medium_width": medium_width, "purpose": "broad range/update tradeoff"}


def _temporal_repeat_windows(
    rng: random.Random,
    length: int,
    key_space: int,
    value_max: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ops = []
    window_count = 12
    width = max(12, key_space // 120)
    centers = [rng.randrange(key_space) for _ in range(window_count)]
    for index in range(length):
        if index % 23 == 0:
            center = rng.choice(centers)
            ops.append(_random_update_near(rng, center, key_space, value_max, width))
            continue
        center = rng.choice(centers)
        roll = rng.random()
        if roll < 0.44:
            ops.append({"op": "range_sum", **_range_dict(center, key_space, width)})
        elif roll < 0.70:
            ops.append({"op": "aggregate_count", **_range_dict(center, key_space, width)})
        elif roll < 0.88:
            ops.append({"op": "top_k", **_range_dict(center, key_space, width), "k": rng.randint(3, 10)})
        else:
            ops.append({"op": "get", "key": _clamp(center + rng.randint(-width, width), 0, key_space - 1)})
    return ops, {"window_count": window_count, "range_width": width, "purpose": "cacheable repeated windows"}


def _topk_stress(
    rng: random.Random,
    length: int,
    key_space: int,
    value_max: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ops = []
    width = max(40, key_space // 8)
    churn_width = max(10, key_space // 80)
    for index in range(length):
        center = rng.randrange(key_space)
        roll = rng.random()
        if index % 9 == 0:
            ops.append(_random_update_near(rng, center, key_space, value_max, churn_width))
        elif roll < 0.58:
            ops.append({"op": "top_k", **_range_dict(center, key_space, width), "k": rng.randint(10, 32)})
        elif roll < 0.76:
            ops.append({"op": "range_sum", **_range_dict(center, key_space, width // 3)})
        elif roll < 0.88:
            ops.append({"op": "aggregate_count", **_range_dict(center, key_space, width // 3)})
        else:
            ops.append(_random_update_near(rng, center, key_space, value_max, churn_width))
    return ops, {"range_width": width, "churn_width": churn_width, "purpose": "broad top-k pressure"}


def _negative_lookup_churn(
    rng: random.Random,
    length: int,
    key_space: int,
    value_max: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ops = []
    absent_start = key_space * 2
    absent_span = max(100, key_space // 5)
    range_width = max(8, key_space // 160)
    for index in range(length):
        roll = rng.random()
        if roll < 0.45:
            ops.append({"op": "get", "key": absent_start + rng.randrange(absent_span)})
        elif roll < 0.62:
            ops.append({"op": "delete", "key": absent_start + rng.randrange(absent_span)})
        elif roll < 0.76:
            ops.append(_random_update(rng, key_space, value_max))
        elif roll < 0.88:
            center = rng.randrange(key_space)
            ops.append({"op": "range_sum", **_range_dict(center, key_space, range_width)})
        else:
            center = rng.randrange(key_space)
            ops.append({"op": "aggregate_count", **_range_dict(center, key_space, range_width)})
    return ops, {"absent_span": absent_span, "range_width": range_width, "purpose": "negative point-query/delete pressure"}


def _random_query(rng: random.Random, key_space: int, range_width: int) -> dict[str, Any]:
    roll = rng.random()
    if roll < 0.38:
        return {"op": "get", "key": rng.randrange(key_space)}
    center = rng.randrange(key_space)
    if roll < 0.66:
        return {"op": "range_sum", **_range_dict(center, key_space, range_width)}
    if roll < 0.86:
        return {"op": "aggregate_count", **_range_dict(center, key_space, range_width)}
    return {"op": "top_k", **_range_dict(center, key_space, range_width), "k": rng.randint(1, 10)}


def _random_update(rng: random.Random, key_space: int, value_max: int) -> dict[str, Any]:
    key = rng.randrange(key_space)
    if rng.random() < 0.78:
        return {"op": "put", "key": key, "value": rng.randint(1, value_max)}
    return {"op": "delete", "key": key}


def _random_update_near(
    rng: random.Random,
    center: int,
    key_space: int,
    value_max: int,
    width: int,
) -> dict[str, Any]:
    key = _clamp(center + rng.randint(-width, width), 0, key_space - 1)
    if rng.random() < 0.8:
        return {"op": "put", "key": key, "value": rng.randint(1, value_max)}
    return {"op": "delete", "key": key}


def _range_around(rng: random.Random, center: int, key_space: int, width: int) -> dict[str, Any]:
    roll = rng.random()
    if roll < 0.45:
        return {"op": "range_sum", **_range_dict(center, key_space, width)}
    if roll < 0.78:
        return {"op": "aggregate_count", **_range_dict(center, key_space, width)}
    return {"op": "top_k", **_range_dict(center, key_space, width), "k": rng.randint(1, 10)}


def _range_dict(center: int, key_space: int, width: int) -> dict[str, int]:
    lo, hi = _bounds_around(center, key_space, width)
    return {"lo": lo, "hi": hi}


def _bounds_around(center: int, key_space: int, width: int) -> tuple[int, int]:
    half = max(1, width // 2)
    lo = _clamp(center - half, 0, key_space - 1)
    hi = _clamp(center + half, 0, key_space - 1)
    return lo, hi


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))
