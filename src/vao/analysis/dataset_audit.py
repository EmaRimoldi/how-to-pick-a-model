"""Audit routing-supervision datasets without new model calls."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from vao.logging_utils import read_jsonl, sha256_text, write_json
from vao.schemas import StepRecord
from vao.taxonomy import MODES, normalize_mode_probs


def audit_dataset(dataset_path: Path, *, near_duplicate_threshold: float = 0.97) -> dict[str, Any]:
    records = read_jsonl(dataset_path)
    profile_counts = Counter(str(row.get("profile_id")) for row in records)
    productive_counts = Counter(str(row.get("productive_mode_top1")) for row in records)
    selected_counts = Counter(_top_mode(row.get("original_mode_probs", {})) for row in records)
    regrets = [float(row.get("original_top1_regret", 0.0)) for row in records]
    gain_values_by_mode: dict[str, list[float]] = {mode: [] for mode in MODES}
    for row in records:
        gains = row.get("verified_gain_per_mode", {})
        for mode in MODES:
            gain_values_by_mode[mode].append(float(gains.get(mode, 0.0)))

    text_hashes = Counter(_input_hash(row) for row in records)
    solution_hashes = Counter(str((row.get("input") or {}).get("current_solution_hash", "")) for row in records)
    near_duplicates = _near_duplicate_pairs(records, near_duplicate_threshold)
    declared_inferred = _declared_inferred_agreement(records)

    audit = {
        "dataset_path": str(dataset_path),
        "total_examples": len(records),
        "examples_per_profile": _ordered_counts(profile_counts),
        "examples_per_productive_mode": {mode: productive_counts.get(mode, 0) for mode in MODES},
        "examples_per_selected_mode": {mode: selected_counts.get(mode, 0) for mode in MODES},
        "class_imbalance": _class_imbalance(productive_counts),
        "routing_regret_distribution": _numeric_summary(regrets),
        "gain_distribution_by_mode": {mode: _numeric_summary(values) for mode, values in gain_values_by_mode.items()},
        "declared_inferred_agreement": declared_inferred,
        "duplicates": {
            "exact_input_hash_duplicate_groups": sum(1 for count in text_hashes.values() if count > 1),
            "exact_input_hash_duplicate_examples": sum(count for count in text_hashes.values() if count > 1),
            "solution_hash_duplicate_groups": sum(1 for count in solution_hashes.values() if count > 1 and count),
            "solution_hash_duplicate_examples": sum(count for key, count in solution_hashes.items() if key and count > 1),
            "near_duplicate_threshold": near_duplicate_threshold,
            "near_duplicate_pair_count": len(near_duplicates),
            "near_duplicate_pairs": near_duplicates[:50],
        },
    }
    return audit


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    lines = [
        "# Offline Routing Dataset Audit",
        "",
        f"Dataset: `{audit['dataset_path']}`",
        f"Total examples: `{audit['total_examples']}`",
        "",
        "## Profiles",
        _table_counts(audit["examples_per_profile"]),
        "",
        "## Productive Modes",
        _table_counts(audit["examples_per_productive_mode"]),
        "",
        "## Selected Modes",
        _table_counts(audit["examples_per_selected_mode"]),
        "",
        "## Class Imbalance",
        f"Nonzero class ratio max/min: `{audit['class_imbalance']['max_to_min_nonzero_ratio']}`",
        f"Missing productive modes: `{audit['class_imbalance']['missing_modes']}`",
        "",
        "## Regret",
        _summary_lines(audit["routing_regret_distribution"]),
        "",
        "## Gain By Mode",
        _mode_summary_table(audit["gain_distribution_by_mode"]),
        "",
        "## Declared/Inferred Agreement",
        f"Branch count: `{audit['declared_inferred_agreement']['branch_count']}`",
        f"Overall agreement: `{audit['declared_inferred_agreement']['overall_agreement']}`",
        _table_counts(audit["declared_inferred_agreement"]["agreement_by_declared_mode"]),
        "",
        "## Duplicates",
        f"Exact input duplicate groups: `{audit['duplicates']['exact_input_hash_duplicate_groups']}`",
        f"Exact input duplicate examples: `{audit['duplicates']['exact_input_hash_duplicate_examples']}`",
        f"Solution-hash duplicate groups: `{audit['duplicates']['solution_hash_duplicate_groups']}`",
        f"Solution-hash duplicate examples: `{audit['duplicates']['solution_hash_duplicate_examples']}`",
        f"Near-duplicate pairs at threshold `{audit['duplicates']['near_duplicate_threshold']}`: `{audit['duplicates']['near_duplicate_pair_count']}`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _top_mode(probs: dict[str, Any]) -> str:
    normalized = normalize_mode_probs({mode: float((probs or {}).get(mode, 0.0)) for mode in MODES})
    return max(MODES, key=lambda mode: normalized[mode])


def _input_hash(row: dict[str, Any]) -> str:
    payload = row.get("input") or {}
    stable = {
        "profile_summary": payload.get("profile_summary", {}),
        "current_solution_hash": payload.get("current_solution_hash", ""),
        "current_solution_source": payload.get("current_solution_source", ""),
        "visible_history": payload.get("visible_history", []),
        "recent_decision_history": payload.get("recent_decision_history", []),
    }
    return sha256_text(json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str))


def _near_duplicate_pairs(records: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    texts = [_near_duplicate_text(row) for row in records]
    pairs = []
    for i, left in enumerate(texts):
        for j in range(i + 1, len(texts)):
            right = texts[j]
            score = SequenceMatcher(a=left, b=right, autojunk=False).ratio()
            if score >= threshold:
                pairs.append(
                    {
                        "left_index": i,
                        "right_index": j,
                        "similarity": score,
                        "left_run_id": records[i].get("run_id"),
                        "right_run_id": records[j].get("run_id"),
                        "left_step": records[i].get("step"),
                        "right_step": records[j].get("step"),
                    }
                )
    return sorted(pairs, key=lambda item: item["similarity"], reverse=True)


def _near_duplicate_text(row: dict[str, Any]) -> str:
    payload = row.get("input") or {}
    return "\n".join(
        [
            str(row.get("profile_id")),
            str(row.get("step")),
            str(payload.get("current_solution_hash", "")),
            str(payload.get("current_solution_source", "")),
            json.dumps(payload.get("visible_history", []), sort_keys=True, default=str),
        ]
    )


def _declared_inferred_agreement(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_mode: dict[str, list[bool]] = defaultdict(list)
    branch_count = 0
    loaded_steps = 0
    for row in records:
        source = row.get("source_step_record_path")
        if not source:
            continue
        path = Path(str(source))
        if not path.exists():
            continue
        try:
            step = StepRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 - audit should remain best-effort.
            continue
        loaded_steps += 1
        for branch in step.branches:
            branch_count += 1
            by_mode[branch.declared_mode].append(branch.declared_mode == branch.inferred_mode)
    all_values = [value for values in by_mode.values() for value in values]
    return {
        "loaded_step_records": loaded_steps,
        "branch_count": branch_count,
        "overall_agreement": statistics.fmean(all_values) if all_values else None,
        "agreement_by_declared_mode": {
            mode: (statistics.fmean(by_mode[mode]) if by_mode.get(mode) else None) for mode in MODES
        },
    }


def _class_imbalance(counts: Counter[str]) -> dict[str, Any]:
    values = [counts.get(mode, 0) for mode in MODES]
    nonzero = [value for value in values if value > 0]
    return {
        "counts": {mode: counts.get(mode, 0) for mode in MODES},
        "missing_modes": [mode for mode in MODES if counts.get(mode, 0) == 0],
        "max_count": max(values) if values else 0,
        "min_nonzero_count": min(nonzero) if nonzero else 0,
        "max_to_min_nonzero_ratio": (max(nonzero) / min(nonzero) if nonzero else None),
    }


def _numeric_summary(values: list[float]) -> dict[str, Any]:
    values = [float(value) for value in values if math.isfinite(float(value))]
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": ordered[0],
        "max": ordered[-1],
        "p10": _quantile(ordered, 0.10),
        "p90": _quantile(ordered, 0.90),
        "positive_count": sum(1 for value in values if value > 0),
        "zero_count": sum(1 for value in values if value == 0),
        "negative_count": sum(1 for value in values if value < 0),
    }


def _quantile(ordered: list[float], q: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _ordered_counts(counts: Counter[str]) -> dict[str, int]:
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _table_counts(counts: dict[str, Any]) -> str:
    rows = ["| key | value |", "| --- | ---: |"]
    for key, value in counts.items():
        rows.append(f"| `{key}` | `{value}` |")
    return "\n".join(rows)


def _summary_lines(summary: dict[str, Any]) -> str:
    return "\n".join(f"- `{key}`: `{value}`" for key, value in summary.items())


def _mode_summary_table(by_mode: dict[str, dict[str, Any]]) -> str:
    rows = ["| mode | count | mean | median | min | max | positive |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for mode in MODES:
        item = by_mode[mode]
        rows.append(
            f"| `{mode}` | `{item.get('count')}` | `{item.get('mean')}` | `{item.get('median')}` | "
            f"`{item.get('min')}` | `{item.get('max')}` | `{item.get('positive_count')}` |"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--json_out", required=True)
    parser.add_argument("--md_out", required=True)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.97)
    args = parser.parse_args(argv)
    audit = audit_dataset(Path(args.dataset), near_duplicate_threshold=args.near_duplicate_threshold)
    write_json(Path(args.json_out), audit)
    write_markdown(audit, Path(args.md_out))
    print(json.dumps({"examples": audit["total_examples"], "json_out": args.json_out, "md_out": args.md_out}, indent=2))


if __name__ == "__main__":
    main()
