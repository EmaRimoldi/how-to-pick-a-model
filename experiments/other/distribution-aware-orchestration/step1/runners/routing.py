"""Phase E routing calibration helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runners.common import ARTIFACT_DIR, PROFILE_DIR, read_json, write_json
from runners.workflow import route_from_feature


def calibrate(profile: dict[str, object]) -> dict[str, object]:
    features = profile["features"]  # type: ignore[index]
    decisions = [route_from_feature(feature) for feature in features]  # type: ignore[arg-type]
    counts: dict[str, int] = {}
    repair_budget: dict[str, int] = {}
    for decision in decisions:
        difficulty = str(decision["difficulty"])
        counts[difficulty] = counts.get(difficulty, 0) + 1
        repair_budget[difficulty] = repair_budget.get(difficulty, 0) + int(decision["repair_rounds"])
    return {
        "schema_version": 1,
        "task": "humaneval",
        "method": "DAAO_distribution_thresholds_plus_TDAG_conditional_expansion",
        "profile_sample_size": profile["sample_size"],  # type: ignore[index]
        "thresholds": profile["daao_distribution_estimator"]["thresholds"],  # type: ignore[index]
        "decision_counts": counts,
        "mean_repair_rounds_by_difficulty": {
            difficulty: repair_budget[difficulty] / count for difficulty, count in sorted(counts.items())
        },
        "tdag_expansion": {
            "easy": "fixed short path",
            "medium": "planned path with one bounded repair",
            "hard": "expanded generated-test path with two bounded repairs and mid-tier node agents",
        },
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=str(PROFILE_DIR / "task_profile.json"))
    parser.add_argument("--output", default=str(ARTIFACT_DIR / "routing_calibration.json"))
    args = parser.parse_args(argv)
    profile = read_json(Path(args.profile))
    payload = calibrate(profile)
    write_json(Path(args.output), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

