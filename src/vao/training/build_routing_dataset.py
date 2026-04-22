"""Build routing-only post-training records from protocol logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vao.estimators import gains_by_mode, productive_mode_proxy, routing_regret
from vao.logging_utils import append_jsonl
from vao.profile_splits import holdout_profiles, load_profile_splits, split_for_profile
from vao.records import iter_run_dirs, load_step_records
from vao.schemas import RoutingRecord, StepRecord
from vao.taxonomy import MODES
from vao.visibility import build_visible_history


def build_records(
    roots: list[Path],
    target: str = "soft_productive_mode_distribution",
    *,
    profile_splits: dict[str, list[str]] | None = None,
    exclude_profiles: set[str] | None = None,
    exclude_holdout: bool = False,
) -> list[RoutingRecord]:
    records: list[RoutingRecord] = []
    excluded = set(exclude_profiles or set())
    if exclude_holdout and profile_splits:
        excluded |= holdout_profiles(profile_splits)
    for root in roots:
        for run_dir in iter_run_dirs(root):
            step_records = load_step_records(run_dir)
            for index, step in enumerate(step_records):
                if step.profile_id in excluded:
                    continue
                gains = gains_by_mode(step)
                fallback = "hard_argmax" if target == "hard_argmax" else "uniform"
                pstar = productive_mode_proxy(gains, fallback=fallback)
                top_mode = max(MODES, key=lambda mode: pstar[mode])
                parent_source = _parent_source_for_step(run_dir, step)
                profile_split = split_for_profile(step.profile_id, profile_splits or {})
                input_record = {
                    "profile_summary": _profile_summary_from_step(step),
                    "profile_split": profile_split,
                    "current_solution_source": parent_source,
                    "current_solution_hash": step.parent_solution_hash,
                    "visible_history": build_visible_history(step_records[:index], step.visibility_regime),
                    "recent_decision_history": [
                        {
                            "step": prior.step,
                            "selected_mode": prior.selected_mode,
                            "mode_probs": prior.mode_probs,
                        }
                        for prior in step_records[max(0, index - 5) : index]
                    ],
                    "full_history_summary": f"{index} prior visible steps",
                }
                records.append(
                    RoutingRecord(
                        run_id=step.run_id,
                        profile_id=step.profile_id,
                        profile_split=profile_split,
                        model_id=step.model_id,
                        step=step.step,
                        input=input_record,
                        productive_mode_top1=top_mode,
                        productive_mode_distribution=pstar,
                        verified_gain_per_mode=gains,
                        original_mode_probs=step.mode_probs,
                        original_top1_regret=routing_regret(gains, step.selected_mode),
                        source_step_record_path=str(run_dir / "steps" / f"step_{step.step:04d}" / "step_record.json"),
                    )
                )
    return records


def write_split(records: list[RoutingRecord], train_out: Path, dev_out: Path) -> None:
    train_out.unlink(missing_ok=True)
    dev_out.unlink(missing_ok=True)
    for index, record in enumerate(records):
        out = dev_out if index % 5 == 0 else train_out
        append_jsonl(out, record)


def write_all(records: list[RoutingRecord], out: Path) -> None:
    out.unlink(missing_ok=True)
    for record in records:
        append_jsonl(out, record)


def _parent_source_for_step(run_dir: Path, step: StepRecord) -> str:
    path = run_dir / "steps" / f"step_{step.step:04d}" / "branches" / "layout" / "parent_solution.py"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _profile_summary_from_step(step: StepRecord) -> dict[str, Any]:
    return {
        "profile_id": step.profile_id,
        "run_id": step.run_id,
        "model_id": step.model_id,
        "visibility_regime": step.visibility_regime,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--target", default="soft_productive_mode_distribution")
    parser.add_argument("--profiles_config", default="configs/profiles.yaml")
    parser.add_argument("--exclude_holdout", action="store_true")
    parser.add_argument("--exclude_profiles", nargs="*", default=[])
    parser.add_argument("--train_out", required=False)
    parser.add_argument("--dev_out", required=False)
    parser.add_argument("--out", required=False)
    args = parser.parse_args(argv)
    profile_splits = load_profile_splits(Path(args.profiles_config))
    records = build_records(
        [Path(item) for item in args.runs],
        target=args.target,
        profile_splits=profile_splits,
        exclude_profiles=set(args.exclude_profiles),
        exclude_holdout=args.exclude_holdout,
    )
    if args.out:
        write_all(records, Path(args.out))
    if args.train_out and args.dev_out:
        write_split(records, Path(args.train_out), Path(args.dev_out))
    print(json.dumps({"records": len(records)}, indent=2))


if __name__ == "__main__":
    main()
