"""Utilities for benchmark dev/holdout profile splits."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_PROFILE_SPLITS_PATH = Path("configs/profiles.yaml")


def load_profile_splits(path: Path = DEFAULT_PROFILE_SPLITS_PATH) -> dict[str, list[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    profiles = data.get("profiles", {})
    return {str(split): [str(profile) for profile in values] for split, values in profiles.items()}


def split_for_profile(profile_id: str, splits: dict[str, list[str]]) -> str | None:
    for split in ("dev", "holdout"):
        if profile_id in splits.get(split, []):
            return split
    for split, profiles in splits.items():
        if profile_id in profiles:
            return split
    return None


def holdout_profiles(splits: dict[str, list[str]]) -> set[str]:
    return set(splits.get("holdout", []))


def dev_profiles(splits: dict[str, list[str]]) -> set[str]:
    return set(splits.get("dev", []))


def assert_disjoint_dev_holdout(splits: dict[str, list[str]]) -> None:
    overlap = sorted(dev_profiles(splits) & holdout_profiles(splits))
    if overlap:
        raise ValueError(f"dev and holdout profile splits overlap: {overlap}")


def summarize_profile_splits(splits: dict[str, list[str]], benchmark_profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    assert_disjoint_dev_holdout(splits)
    known = set(benchmark_profiles or {})
    missing = {
        split: sorted(profile for profile in profiles if known and profile not in known)
        for split, profiles in splits.items()
    }
    seed_by_profile = {
        profile: benchmark_profiles[profile].get("seed")
        for profile in sorted(known)
        if benchmark_profiles is not None
    }
    dev_seeds = {seed_by_profile.get(profile) for profile in splits.get("dev", [])}
    holdout_seeds = {seed_by_profile.get(profile) for profile in splits.get("holdout", [])}
    seed_overlap = sorted(seed for seed in dev_seeds & holdout_seeds if seed is not None)
    return {
        "splits": splits,
        "counts": {split: len(profiles) for split, profiles in splits.items()},
        "dev_holdout_overlap": sorted(dev_profiles(splits) & holdout_profiles(splits)),
        "missing_from_benchmark": missing,
        "dev_holdout_seed_overlap": seed_overlap,
        "benchmark_profile_count": len(known),
    }
