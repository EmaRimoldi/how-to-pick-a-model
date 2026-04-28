"""Validate one run directory against the C(a) protocol invariants."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from vao.estimators import gain
from vao.logging_utils import sha256_file
from vao.records import load_step_records
from vao.schemas import BranchEvaluation, StepRecord
from vao.taxonomy import MODES, MODE_SET, normalize_mode_probs
from vao.visibility import build_visible_history


def validate_run(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        records = load_step_records(run_dir)
    except (json.JSONDecodeError, ValidationError, OSError) as exc:
        return {"run_dir": str(run_dir), "passed": False, "errors": [f"could_not_load_records: {exc}"], "warnings": []}
    if not records:
        errors.append("evaluations.jsonl has no step records")

    for index, record in enumerate(records):
        _validate_step_record(run_dir, record, index, records, errors, warnings)

    result = {
        "run_dir": str(run_dir),
        "passed": not errors,
        "step_count": len(records),
        "branch_evaluation_count": sum(len(record.branches) for record in records),
        "errors": errors,
        "warnings": warnings,
    }
    return result


def _validate_step_record(
    run_dir: Path,
    record: StepRecord,
    index: int,
    records: list[StepRecord],
    errors: list[str],
    warnings: list[str],
) -> None:
    prefix = f"step={record.step}"
    candidate_generation = str((record.parsed_model_output_json or {}).get("candidate_generation") or "batched")
    expected_branch_count = 1 if candidate_generation.startswith("single") else len(MODES)
    if len(record.branches) != expected_branch_count:
        errors.append(f"{prefix}: expected {expected_branch_count} branches, found {len(record.branches)}")
    declared_modes = [branch.declared_mode for branch in record.branches]
    if candidate_generation.startswith("single"):
        if len(declared_modes) != 1 or declared_modes[0] not in MODE_SET:
            errors.append(f"{prefix}: single-candidate step must contain exactly one canonical declared mode: {declared_modes}")
    elif set(declared_modes) != MODE_SET or len(declared_modes) != len(MODES):
        errors.append(f"{prefix}: declared modes are not exactly canonical modes: {declared_modes}")
    try:
        probs = normalize_mode_probs(record.mode_probs)
    except ValueError as exc:
        errors.append(f"{prefix}: invalid mode_probs: {exc}")
        probs = record.mode_probs
    else:
        if abs(sum(probs.values()) - 1.0) > 1e-9:
            errors.append(f"{prefix}: mode_probs do not sum to 1")

    expected_top1 = max(MODES, key=lambda mode: probs[mode])
    if record.selected_mode_top1 != expected_top1:
        errors.append(f"{prefix}: selected_mode_top1 {record.selected_mode_top1} does not match argmax(mode_probs) {expected_top1}")
    if record.selection_policy == "top1" and record.selected_mode != expected_top1:
        errors.append(f"{prefix}: selected mode {record.selected_mode} does not match argmax(mode_probs) {expected_top1}")
    expected_promoted = record.selected_mode

    batch_ids = {record.candidate_batch_id}
    proposal_batch_ids = _proposal_batch_ids(run_dir, record)
    batch_ids.update(proposal_batch_ids)
    if len(batch_ids) != 1:
        errors.append(f"{prefix}: candidate_batch_id mismatch across proposals: {sorted(batch_ids)}")

    selected_visible = [branch for branch in record.branches if branch.selected_as_visible]
    promoted = [branch for branch in record.branches if branch.promoted_as_parent]
    if record.visibility_regime == "top1_only":
        if len(selected_visible) != 1:
            errors.append(f"{prefix}: expected exactly one selected_as_visible branch, found {len(selected_visible)}")
        if len(promoted) != 1:
            errors.append(f"{prefix}: expected exactly one promoted_as_parent branch, found {len(promoted)}")
    if promoted and promoted[0].declared_mode != expected_promoted:
        errors.append(f"{prefix}: promoted branch {promoted[0].declared_mode} does not match selected_mode {expected_promoted}")
    if selected_visible and record.visibility_regime == "top1_only" and selected_visible[0].declared_mode != expected_promoted:
        errors.append(f"{prefix}: visible branch {selected_visible[0].declared_mode} does not match selected_mode {expected_promoted}")

    parent_hashes = {branch.source_parent_hash for branch in record.branches}
    if parent_hashes != {record.parent_solution_hash}:
        errors.append(f"{prefix}: branch source_parent_hash values {parent_hashes} do not match parent_solution_hash")
    file_parent_hashes = _file_parent_hashes(run_dir, record)
    if file_parent_hashes and file_parent_hashes != {record.parent_solution_hash}:
        errors.append(f"{prefix}: parent_solution.py hashes {file_parent_hashes} do not match parent_solution_hash")

    for branch in record.branches:
        _validate_branch(run_dir, record, branch, expected_promoted, errors, warnings)

    parent_loss = _expected_parent_loss(record, index, records)
    if parent_loss is not None:
        if record.parent_latent_loss is not None and _finite_delta(record.parent_latent_loss, parent_loss) > 1e-9:
            errors.append(f"{prefix}: parent_latent_loss {record.parent_latent_loss} != expected {parent_loss}")
        for branch in record.branches:
            expected_gain = gain(parent_loss, branch.latent_loss, branch.correctness, -1.0)
            if _finite_delta(branch.gain, expected_gain) > 1e-8:
                errors.append(f"{prefix}: branch {branch.declared_mode} gain {branch.gain} != expected {expected_gain}")

    if index + 1 < len(records):
        visible_history = build_visible_history(records[: index + 1], record.visibility_regime)
        last_visible = visible_history[-1]
        if record.visibility_regime == "top1_only":
            visible_modes = {branch["declared_mode"] for branch in last_visible["branches"]}
            invisible_modes = set(MODES) - {expected_promoted}
            if visible_modes != {expected_promoted}:
                errors.append(f"{prefix}: reconstructed visible history contains {visible_modes}, expected only {expected_promoted}")
            leaked = visible_modes & invisible_modes
            if leaked:
                errors.append(f"{prefix}: invisible branch modes leaked into reconstructed visible history: {sorted(leaked)}")
        snapshot = records[index + 1].parsed_model_output_json or {}
        if isinstance(snapshot, dict) and "visible_history_snapshot" in snapshot:
            _validate_visible_snapshot(snapshot["visible_history_snapshot"], record, expected_promoted, record.visibility_regime, errors)


def _validate_branch(
    run_dir: Path,
    record: StepRecord,
    branch: BranchEvaluation,
    expected_promoted: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    prefix = f"step={record.step} branch={branch.declared_mode}"
    if branch.declared_mode not in MODE_SET:
        errors.append(f"{prefix}: invalid declared_mode")
    if branch.inferred_mode not in MODE_SET:
        errors.append(f"{prefix}: invalid inferred_mode")
    if branch.declared_mode == branch.inferred_mode:
        pass
    if branch.declared_mode != expected_promoted and branch.promoted_as_parent:
        errors.append(f"{prefix}: non-top1 branch promoted")
    branch_path = Path(branch.file_path)
    if not branch_path.exists():
        errors.append(f"{prefix}: proposed solution file missing: {branch.file_path}")
    verification_path = branch_path.parent / "verification.json"
    if not verification_path.exists():
        errors.append(f"{prefix}: verification.json missing")
    proposal_path = branch_path.parent / "proposal.json"
    if not proposal_path.exists():
        errors.append(f"{prefix}: proposal.json missing")
    if branch.correctness is None or branch.latent_loss is None:
        errors.append(f"{prefix}: missing evaluation result")


def _proposal_batch_ids(run_dir: Path, record: StepRecord) -> set[str]:
    batch_ids: set[str] = set()
    for mode in MODES:
        path = run_dir / "steps" / f"step_{record.step:04d}" / "branches" / mode / "proposal.json"
        if not path.exists():
            continue
        try:
            batch_ids.add(json.loads(path.read_text(encoding="utf-8")).get("candidate_batch_id"))
        except json.JSONDecodeError:
            batch_ids.add("<invalid-json>")
    return {item for item in batch_ids if item}


def _file_parent_hashes(run_dir: Path, record: StepRecord) -> set[str]:
    hashes: set[str] = set()
    for mode in MODES:
        path = run_dir / "steps" / f"step_{record.step:04d}" / "branches" / mode / "parent_solution.py"
        if path.exists():
            hashes.add(sha256_file(path))
    return hashes


def _expected_parent_loss(record: StepRecord, index: int, records: list[StepRecord]) -> float | None:
    if record.parent_latent_loss is not None:
        return float(record.parent_latent_loss)
    if index == 0:
        return None
    previous_promoted = [branch for branch in records[index - 1].branches if branch.promoted_as_parent]
    if len(previous_promoted) == 1:
        return previous_promoted[0].latent_loss
    return None


def _validate_visible_snapshot(
    snapshot: Any,
    previous_record: StepRecord,
    expected_promoted: str,
    visibility_regime: str,
    errors: list[str],
) -> None:
    if not isinstance(snapshot, list) or not snapshot:
        errors.append(f"step={previous_record.step}: next-step visible_history_snapshot is empty or malformed")
        return
    matching = [row for row in snapshot if isinstance(row, dict) and row.get("step") == previous_record.step]
    if not matching:
        errors.append(f"step={previous_record.step}: next-step visible_history_snapshot missing previous step")
        return
    branches = matching[-1].get("branches", [])
    modes = {branch.get("declared_mode") for branch in branches if isinstance(branch, dict)}
    expected_modes = set(MODES) if visibility_regime == "all_branches" else {expected_promoted}
    if modes != expected_modes:
        errors.append(
            f"step={previous_record.step}: next-step visible_history_snapshot has modes {sorted(modes)}, expected {sorted(expected_modes)}"
        )


def _finite_delta(a: float, b: float) -> float:
    if math.isinf(a) and math.isinf(b):
        return 0.0
    if math.isnan(a) and math.isnan(b):
        return 0.0
    return abs(float(a) - float(b))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    args = parser.parse_args(argv)
    result = validate_run(Path(args.run_dir))
    print(json.dumps(result, indent=2, allow_nan=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
