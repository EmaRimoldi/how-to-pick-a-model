#!/usr/bin/env python3
"""Summarize SAI-3 scout eligibility without computing four-term closure."""

from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path
from typing import Any


def wilson_upper(successes: int, trials: int, z: float = 1.959963984540054) -> float:
    if trials == 0:
        return math.nan
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = p + z * z / (2.0 * trials)
    radius = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials))
    return (center + radius) / denominator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = collections.defaultdict(list)
    reasons: collections.Counter[str] = collections.Counter()
    for path in args.inputs:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                key = (row["model"], int(row["mode"]), row["relation"])
                groups[key].append(row)
                if not row["verification"]["passed"]:
                    reasons[row["verification"]["reason"]] += 1

    cells = []
    by_model: dict[str, dict[str, int]] = collections.defaultdict(lambda: collections.Counter())
    for (model, mode, relation), rows in sorted(groups.items()):
        successes = sum(bool(row["verification"]["passed"]) for row in rows)
        parsed = sum(bool(row["verification"]["parsed"]) for row in rows)
        cell = {
            "model": model,
            "mode": mode,
            "relation": relation,
            "trials": len(rows),
            "successes": successes,
            "success_rate": successes / len(rows),
            "parse_rate": parsed / len(rows),
            "success_rate_upper_95": wilson_upper(successes, len(rows)),
        }
        cells.append(cell)
        by_model[model][f"{relation}_trials"] += len(rows)
        by_model[model][f"{relation}_successes"] += successes
        by_model[model][f"{relation}_parsed"] += parsed

    models = []
    for model, counts in sorted(by_model.items()):
        matched_trials = counts["matched_trials"]
        wrong_trials = counts["wrong_trials"]
        matched_rate = counts["matched_successes"] / matched_trials if matched_trials else math.nan
        wrong_rate = counts["wrong_successes"] / wrong_trials if wrong_trials else math.nan
        models.append(
            {
                "model": model,
                "matched_trials": matched_trials,
                "matched_success_rate": matched_rate,
                "matched_parse_rate": counts["matched_parsed"] / matched_trials if matched_trials else math.nan,
                "wrong_trials": wrong_trials,
                "wrong_success_rate": wrong_rate,
                "wrong_success_rate_upper_95": wilson_upper(counts["wrong_successes"], wrong_trials),
                "focused_regime_eligible": 0.15 <= matched_rate <= 0.65,
            }
        )

    summary = {
        "schema_version": 1,
        "analysis": "eligibility_only_closure_prohibited",
        "models": models,
        "cells": cells,
        "failure_reasons": dict(reasons.most_common()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
