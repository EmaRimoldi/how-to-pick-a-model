"""Calibrate baseline headroom before reviewer-grade 2x2 runs.

The calibration is deliberately non-agentic. It tests a small panel of healthy
but mildly mis-tuned baseline candidates plus controlled edits from distinct
strategy categories. The goal is to decide whether a task/baseline exposes
multi-modal headroom before spending LLM budget on architecture comparisons.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from agent_workflow.utils.log_parser import parse_all_metrics


HYPERPARAM_KEYS = {
    "DEPTH",
    "BASE_CHANNELS",
    "CHANNEL_MULT",
    "USE_BATCHNORM",
    "DROPOUT_RATE",
    "FC_HIDDEN",
    "OPTIMIZER",
    "LEARNING_RATE",
    "WEIGHT_DECAY",
    "MOMENTUM",
    "ADAM_BETAS",
    "USE_LR_SCHEDULE",
    "WARMUP_EPOCHS",
    "LR_DECAY_FACTOR",
    "LR_DECAY_EPOCHS",
    "BATCH_SIZE",
    "NUM_WORKERS",
}


@dataclass(frozen=True)
class ChangeSpec:
    id: str
    category: str
    description: str
    changes: dict[str, object]


@dataclass(frozen=True)
class TrialSpec:
    id: str
    baseline_id: str
    category: str
    description: str
    changes: dict[str, object]
    baseline_changes: dict[str, object]
    edit_changes: dict[str, object] = field(default_factory=dict)
    is_baseline: bool = False


@dataclass
class TrialResult:
    id: str
    baseline_id: str
    category: str
    description: str
    changes: dict[str, object]
    baseline_changes: dict[str, object]
    edit_changes: dict[str, object]
    is_baseline: bool
    status: str
    returncode: Optional[int]
    val_bpb: Optional[float]
    total_seconds: Optional[float]
    training_seconds: Optional[float]
    total_steps: Optional[int]
    evaluator_mode: Optional[str]
    train_max_steps: Optional[int]
    trial_dir: str
    stdout_path: str
    stderr_path: str
    error: Optional[str] = None
    improvement: Optional[float] = None
    success: Optional[bool] = None


@dataclass
class BaselineSummary:
    baseline_id: str
    baseline_val_bpb: Optional[float]
    completed_edits: int
    successful_edits: int
    success_rate: Optional[float]
    winning_categories: list[str]
    category_best_val_bpb: dict[str, float]
    category_best_trial: dict[str, str]
    category_success_counts: dict[str, int]
    category_completed_counts: dict[str, int]
    best_edit_val_bpb: Optional[float]
    best_edit_trial: Optional[str]
    best_improvement: Optional[float]
    passes_gate: bool
    proposed_q_star: Optional[float]
    gate_reasons: list[str]


def default_baselines(include_current_control: bool = False) -> list[ChangeSpec]:
    """Return healthy but mildly mis-tuned baseline candidates."""
    baselines = [
        ChangeSpec(
            id="lr_low_no_schedule",
            category="baseline",
            description="Lower LR and disable cosine schedule.",
            changes={"LEARNING_RATE": 5e-4, "USE_LR_SCHEDULE": False},
        ),
        ChangeSpec(
            id="lr_very_low_no_schedule",
            category="baseline",
            description="More conservative LR and no cosine schedule.",
            changes={"LEARNING_RATE": 3e-4, "USE_LR_SCHEDULE": False},
        ),
        ChangeSpec(
            id="narrow_lr_low",
            category="baseline",
            description="Narrower model plus conservative LR and no schedule.",
            changes={"BASE_CHANNELS": 24, "LEARNING_RATE": 5e-4, "USE_LR_SCHEDULE": False},
        ),
        ChangeSpec(
            id="no_batchnorm_lr_low",
            category="baseline",
            description="Remove batchnorm and use conservative LR/no schedule.",
            changes={"USE_BATCHNORM": False, "LEARNING_RATE": 5e-4, "USE_LR_SCHEDULE": False},
        ),
        ChangeSpec(
            id="overregularized_lr_low",
            category="baseline",
            description="Mildly over-regularized baseline with conservative LR/no schedule.",
            changes={
                "DROPOUT_RATE": 0.1,
                "WEIGHT_DECAY": 5e-3,
                "LEARNING_RATE": 5e-4,
                "USE_LR_SCHEDULE": False,
            },
        ),
    ]
    if include_current_control:
        return [
            ChangeSpec(
                id="current_control",
                category="baseline",
                description="Current repository baseline; diagnostic control, not a headroom candidate.",
                changes={},
            )
        ] + baselines
    return baselines


def extended_baselines(include_current_control: bool = False) -> list[ChangeSpec]:
    """Return a broader screen for autonomous follow-up exploration."""
    baselines = default_baselines(include_current_control=include_current_control)
    baselines.extend(
        [
            ChangeSpec(
                id="shallow_lr_low",
                category="baseline",
                description="Shallower model with conservative LR and no schedule.",
                changes={"DEPTH": 2, "LEARNING_RATE": 5e-4, "USE_LR_SCHEDULE": False},
            ),
            ChangeSpec(
                id="small_fc_lr_low",
                category="baseline",
                description="Smaller classifier head with conservative LR/no schedule.",
                changes={"FC_HIDDEN": 64, "LEARNING_RATE": 5e-4, "USE_LR_SCHEDULE": False},
            ),
            ChangeSpec(
                id="sgd_baseline",
                category="baseline",
                description="SGD baseline that may expose optimizer and scheduler headroom.",
                changes={
                    "OPTIMIZER": "sgd",
                    "LEARNING_RATE": 5e-2,
                    "MOMENTUM": 0.9,
                    "USE_LR_SCHEDULE": False,
                },
            ),
            ChangeSpec(
                id="weak_regularization_no_schedule",
                category="baseline",
                description="Remove weight decay and schedule while keeping architecture healthy.",
                changes={"WEIGHT_DECAY": 0.0, "LEARNING_RATE": 5e-4, "USE_LR_SCHEDULE": False},
            ),
            ChangeSpec(
                id="mild_dropout_no_schedule",
                category="baseline",
                description="Add mild dropout with conservative LR/no schedule.",
                changes={"DROPOUT_RATE": 0.2, "LEARNING_RATE": 5e-4, "USE_LR_SCHEDULE": False},
            ),
        ]
    )
    return baselines


def default_edit_panel() -> list[ChangeSpec]:
    """Return a controlled strategy panel spanning several intervention modes."""
    return [
        ChangeSpec(
            id="lr_1p5e3",
            category="optimizer_lr",
            description="Set LR to the previously observed fast-improvement region.",
            changes={"LEARNING_RATE": 1.5e-3},
        ),
        ChangeSpec(
            id="adamw_lr_1e3",
            category="optimizer_lr",
            description="Switch to AdamW with the original LR.",
            changes={"OPTIMIZER": "adamw", "LEARNING_RATE": 1e-3},
        ),
        ChangeSpec(
            id="cosine_schedule_on",
            category="scheduler",
            description="Enable cosine schedule.",
            changes={"USE_LR_SCHEDULE": True},
        ),
        ChangeSpec(
            id="cosine_schedule_off",
            category="scheduler",
            description="Disable cosine schedule.",
            changes={"USE_LR_SCHEDULE": False},
        ),
        ChangeSpec(
            id="bn_on_width32",
            category="normalization_capacity",
            description="Restore batchnorm and 32 base channels.",
            changes={"USE_BATCHNORM": True, "BASE_CHANNELS": 32},
        ),
        ChangeSpec(
            id="width40",
            category="normalization_capacity",
            description="Increase base channels to 40.",
            changes={"BASE_CHANNELS": 40},
        ),
        ChangeSpec(
            id="low_wd_no_dropout",
            category="regularization",
            description="Use low weight decay and no dropout.",
            changes={"WEIGHT_DECAY": 1e-4, "DROPOUT_RATE": 0.0},
        ),
        ChangeSpec(
            id="moderate_wd_dropout",
            category="regularization",
            description="Use moderate weight decay plus dropout.",
            changes={"WEIGHT_DECAY": 5e-4, "DROPOUT_RATE": 0.1},
        ),
        ChangeSpec(
            id="batch64",
            category="data_batch",
            description="Use smaller batches.",
            changes={"BATCH_SIZE": 64},
        ),
        ChangeSpec(
            id="batch256",
            category="data_batch",
            description="Use larger batches.",
            changes={"BATCH_SIZE": 256},
        ),
    ]


def extended_edit_panel() -> list[ChangeSpec]:
    """Return a broader controlled edit panel for follow-up screens."""
    edits = default_edit_panel()
    edits.extend(
        [
            ChangeSpec(
                id="lr_1e3_schedule_on",
                category="optimizer_scheduler",
                description="Restore LR 1e-3 and cosine schedule together.",
                changes={"LEARNING_RATE": 1e-3, "USE_LR_SCHEDULE": True},
            ),
            ChangeSpec(
                id="lr_2e3",
                category="optimizer_lr",
                description="Use a more aggressive Adam/AdamW LR.",
                changes={"LEARNING_RATE": 2e-3},
            ),
            ChangeSpec(
                id="sgd_5e2",
                category="optimizer_lr",
                description="Switch to SGD with LR 5e-2 and momentum.",
                changes={"OPTIMIZER": "sgd", "LEARNING_RATE": 5e-2, "MOMENTUM": 0.9},
            ),
            ChangeSpec(
                id="depth3_width32",
                category="normalization_capacity",
                description="Restore depth 3 and base width 32.",
                changes={"DEPTH": 3, "BASE_CHANNELS": 32},
            ),
            ChangeSpec(
                id="depth4_width24",
                category="normalization_capacity",
                description="Increase depth while keeping width moderate.",
                changes={"DEPTH": 4, "BASE_CHANNELS": 24},
            ),
            ChangeSpec(
                id="fc128",
                category="normalization_capacity",
                description="Restore classifier hidden size 128.",
                changes={"FC_HIDDEN": 128},
            ),
            ChangeSpec(
                id="weight_decay_zero",
                category="regularization",
                description="Remove weight decay.",
                changes={"WEIGHT_DECAY": 0.0},
            ),
            ChangeSpec(
                id="weight_decay_1e3",
                category="regularization",
                description="Use weight decay 1e-3.",
                changes={"WEIGHT_DECAY": 1e-3},
            ),
            ChangeSpec(
                id="dropout_0p2",
                category="regularization",
                description="Use dropout 0.2.",
                changes={"DROPOUT_RATE": 0.2},
            ),
        ]
    )
    return edits


def load_change_specs(path: Path) -> list[ChangeSpec]:
    """Load ChangeSpec entries from a JSON file."""
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON spec file: {path}") from exc
    if isinstance(payload, dict):
        raw_specs = payload.get("specs")
    else:
        raw_specs = payload
    if not isinstance(raw_specs, list):
        raise ValueError(f"Expected a list of spec objects in {path}")
    specs: list[ChangeSpec] = []
    for raw in raw_specs:
        if not isinstance(raw, dict):
            raise ValueError(f"Spec entries must be objects in {path}")
        try:
            specs.append(
                ChangeSpec(
                    id=str(raw["id"]),
                    category=str(raw.get("category", "custom")),
                    description=str(raw.get("description", raw["id"])),
                    changes=dict(raw["changes"]),
                )
            )
        except KeyError as exc:
            raise ValueError(f"Spec entry missing required key {exc} in {path}") from exc
    return specs


def extract_constant_values(source: str, keys: Iterable[str] = HYPERPARAM_KEYS) -> dict[str, object]:
    values: dict[str, object] = {}
    for key in keys:
        match = re.search(rf"^{re.escape(key)}\s*=\s*(.+)$", source, re.MULTILINE)
        if not match:
            continue
        rhs = match.group(1).strip()
        try:
            values[key] = ast.literal_eval(rhs)
        except (SyntaxError, ValueError):
            values[key] = rhs
    return values


def _format_python_literal(value: object) -> str:
    if isinstance(value, float):
        return repr(value)
    return repr(value)


def apply_constant_changes(source: str, changes: dict[str, object]) -> str:
    """Apply top-level constant changes to train.py source."""
    updated = source
    for key, value in changes.items():
        if key not in HYPERPARAM_KEYS:
            raise ValueError(f"Unsupported train.py hyperparameter: {key}")
        replacement = f"{key} = {_format_python_literal(value)}"
        updated, count = re.subn(
            rf"^{re.escape(key)}\s*=.*$",
            replacement,
            updated,
            count=1,
            flags=re.MULTILINE,
        )
        if count != 1:
            raise ValueError(f"Could not find top-level constant in train.py: {key}")
    return updated


def _merged_values(
    base_values: dict[str, object],
    baseline_changes: dict[str, object],
    edit_changes: Optional[dict[str, object]] = None,
) -> dict[str, object]:
    merged = dict(base_values)
    merged.update(baseline_changes)
    if edit_changes:
        merged.update(edit_changes)
    return merged


def _is_noop_edit(
    base_values: dict[str, object],
    baseline_changes: dict[str, object],
    edit_changes: dict[str, object],
) -> bool:
    before = _merged_values(base_values, baseline_changes)
    return all(before.get(key) == value for key, value in edit_changes.items())


def _select_specs(specs: list[ChangeSpec], requested_ids: Optional[set[str]]) -> list[ChangeSpec]:
    if not requested_ids:
        return specs
    selected = [spec for spec in specs if spec.id in requested_ids]
    missing = sorted(requested_ids - {spec.id for spec in selected})
    if missing:
        raise ValueError(f"Unknown calibration spec id(s): {', '.join(missing)}")
    return selected


def build_calibration_plan(
    train_source: str,
    *,
    baselines: Optional[list[ChangeSpec]] = None,
    edits: Optional[list[ChangeSpec]] = None,
    baseline_ids: Optional[set[str]] = None,
    edit_ids: Optional[set[str]] = None,
    include_current_control: bool = False,
) -> list[TrialSpec]:
    """Build the baseline + controlled-edit trial plan."""
    base_values = extract_constant_values(train_source)
    baseline_specs = _select_specs(
        baselines or default_baselines(include_current_control=include_current_control),
        baseline_ids,
    )
    edit_specs = _select_specs(edits or default_edit_panel(), edit_ids)

    plan: list[TrialSpec] = []
    for baseline in baseline_specs:
        baseline_changes = dict(baseline.changes)
        plan.append(
            TrialSpec(
                id=f"{baseline.id}__baseline",
                baseline_id=baseline.id,
                category="baseline",
                description=baseline.description,
                changes=baseline_changes,
                baseline_changes=baseline_changes,
                is_baseline=True,
            )
        )
        for edit in edit_specs:
            if _is_noop_edit(base_values, baseline_changes, edit.changes):
                continue
            combined = dict(baseline_changes)
            combined.update(edit.changes)
            plan.append(
                TrialSpec(
                    id=f"{baseline.id}__{edit.category}__{edit.id}",
                    baseline_id=baseline.id,
                    category=edit.category,
                    description=edit.description,
                    changes=combined,
                    baseline_changes=baseline_changes,
                    edit_changes=dict(edit.changes),
                )
            )
    return plan


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_out_dir(repo_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return repo_root / "runs" / f"baseline_headroom_calibration_{stamp}"


def _prepare_trial_dir(
    *,
    trial_dir: Path,
    autoresearch_dir: Path,
    train_source: str,
    spec: TrialSpec,
) -> None:
    trial_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(autoresearch_dir / "prepare.py", trial_dir / "prepare.py")
    (trial_dir / "train.py").write_text(
        apply_constant_changes(train_source, spec.changes)
    )
    data_src = autoresearch_dir / "data"
    data_dst = trial_dir / "data"
    if data_src.exists() and not data_dst.exists():
        try:
            data_dst.symlink_to(data_src, target_is_directory=True)
        except OSError:
            shutil.copytree(data_src, data_dst)
    (trial_dir / "spec.json").write_text(json.dumps(asdict(spec), indent=2))


def _load_cached_result(trial_dir: Path, spec: TrialSpec) -> Optional[TrialResult]:
    metrics_path = trial_dir / "metrics.json"
    if not metrics_path.exists():
        return None
    try:
        payload = json.loads(metrics_path.read_text())
    except json.JSONDecodeError:
        return None
    if payload.get("id") != spec.id:
        return None
    return TrialResult(**payload)


def run_trial(
    *,
    spec: TrialSpec,
    autoresearch_dir: Path,
    train_source: str,
    trials_dir: Path,
    train_max_steps: int,
    train_time_budget_seconds: int,
    timeout_seconds: int,
    force: bool = False,
) -> TrialResult:
    trial_dir = trials_dir / spec.id
    stdout_path = trial_dir / "stdout.txt"
    stderr_path = trial_dir / "stderr.txt"

    if not force:
        cached = _load_cached_result(trial_dir, spec)
        if cached is not None:
            return cached

    _prepare_trial_dir(
        trial_dir=trial_dir,
        autoresearch_dir=autoresearch_dir,
        train_source=train_source,
        spec=spec,
    )

    env = os.environ.copy()
    env["AUTOSEARCH_MAX_STEPS"] = str(train_max_steps)
    env["AUTOSEARCH_TIME_BUDGET"] = str(train_time_budget_seconds)

    started = time.monotonic()
    status = "crash"
    returncode: Optional[int] = None
    error: Optional[str] = None
    try:
        completed = subprocess.run(
            [sys.executable, "train.py"],
            cwd=trial_dir,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        returncode = completed.returncode
        stdout_path.write_text(completed.stdout)
        stderr_path.write_text(completed.stderr)
        status = "success" if completed.returncode == 0 else "crash"
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        status = "timeout"
        error = f"timeout after {elapsed:.1f}s"
        stdout_path.write_text(exc.stdout or "")
        stderr_path.write_text(exc.stderr or "")

    metrics = parse_all_metrics(stdout_path)
    if metrics.get("val_bpb") is None and status == "success":
        status = "crash"

    result = TrialResult(
        id=spec.id,
        baseline_id=spec.baseline_id,
        category=spec.category,
        description=spec.description,
        changes=dict(spec.changes),
        baseline_changes=dict(spec.baseline_changes),
        edit_changes=dict(spec.edit_changes),
        is_baseline=spec.is_baseline,
        status=status,
        returncode=returncode,
        val_bpb=metrics.get("val_bpb"),
        total_seconds=metrics.get("total_seconds"),
        training_seconds=metrics.get("training_seconds"),
        total_steps=metrics.get("total_steps"),
        evaluator_mode=metrics.get("evaluator_mode"),
        train_max_steps=metrics.get("train_max_steps"),
        trial_dir=str(trial_dir),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        error=error,
    )
    (trial_dir / "metrics.json").write_text(json.dumps(asdict(result), indent=2))
    return result


def attach_improvements(
    results: list[TrialResult],
    *,
    min_delta: float,
) -> list[TrialResult]:
    baseline_values = {
        result.baseline_id: result.val_bpb
        for result in results
        if result.is_baseline and result.val_bpb is not None
    }
    for result in results:
        baseline_val = baseline_values.get(result.baseline_id)
        if result.is_baseline or baseline_val is None or result.val_bpb is None:
            result.improvement = None
            result.success = None
            continue
        improvement = baseline_val - result.val_bpb
        result.improvement = improvement
        result.success = improvement >= min_delta
    return results


def summarize_baselines(
    results: list[TrialResult],
    *,
    min_delta: float = 0.005,
    min_categories: int = 3,
    min_success_rate: float = 0.10,
    max_success_rate: float = 0.30,
) -> list[BaselineSummary]:
    by_baseline: dict[str, list[TrialResult]] = {}
    for result in results:
        by_baseline.setdefault(result.baseline_id, []).append(result)

    summaries: list[BaselineSummary] = []
    for baseline_id, rows in sorted(by_baseline.items()):
        baseline_row = next((row for row in rows if row.is_baseline), None)
        baseline_val = baseline_row.val_bpb if baseline_row else None
        edits = [row for row in rows if not row.is_baseline]
        completed_edits = [row for row in edits if row.val_bpb is not None]
        successful_edits = [row for row in completed_edits if row.success]
        success_rate = (
            len(successful_edits) / len(completed_edits) if completed_edits else None
        )

        category_best_val: dict[str, float] = {}
        category_best_trial: dict[str, str] = {}
        category_success_counts: dict[str, int] = {}
        category_completed_counts: dict[str, int] = {}
        for row in completed_edits:
            category_completed_counts[row.category] = (
                category_completed_counts.get(row.category, 0) + 1
            )
            if row.success:
                category_success_counts[row.category] = (
                    category_success_counts.get(row.category, 0) + 1
                )
            current_best = category_best_val.get(row.category)
            if current_best is None or row.val_bpb < current_best:
                category_best_val[row.category] = row.val_bpb
                category_best_trial[row.category] = row.id

        winning_categories = []
        if baseline_val is not None:
            winning_categories = sorted(
                category
                for category, best_val in category_best_val.items()
                if best_val <= baseline_val - min_delta
            )

        best_edit = min(
            (row for row in completed_edits if row.val_bpb is not None),
            key=lambda row: row.val_bpb if row.val_bpb is not None else math.inf,
            default=None,
        )
        best_improvement = None
        if best_edit is not None and baseline_val is not None and best_edit.val_bpb is not None:
            best_improvement = baseline_val - best_edit.val_bpb

        proposed_q_star = None
        if len(winning_categories) >= min_categories:
            winning_best_vals = sorted(category_best_val[cat] for cat in winning_categories)
            proposed_q_star = winning_best_vals[min_categories - 1]

        gate_reasons: list[str] = []
        if baseline_val is None:
            gate_reasons.append("baseline did not complete")
        if len(winning_categories) < min_categories:
            gate_reasons.append(
                f"needs >= {min_categories} winning categories; observed {len(winning_categories)}"
            )
        if success_rate is None:
            gate_reasons.append("no completed edit trials")
        elif success_rate < min_success_rate:
            gate_reasons.append(
                f"success rate {success_rate:.3f} is below {min_success_rate:.3f}"
            )
        elif success_rate > max_success_rate:
            gate_reasons.append(
                f"success rate {success_rate:.3f} is above {max_success_rate:.3f}"
            )
        passes_gate = not gate_reasons

        summaries.append(
            BaselineSummary(
                baseline_id=baseline_id,
                baseline_val_bpb=baseline_val,
                completed_edits=len(completed_edits),
                successful_edits=len(successful_edits),
                success_rate=success_rate,
                winning_categories=winning_categories,
                category_best_val_bpb=category_best_val,
                category_best_trial=category_best_trial,
                category_success_counts=category_success_counts,
                category_completed_counts=category_completed_counts,
                best_edit_val_bpb=best_edit.val_bpb if best_edit else None,
                best_edit_trial=best_edit.id if best_edit else None,
                best_improvement=best_improvement,
                passes_gate=passes_gate,
                proposed_q_star=proposed_q_star,
                gate_reasons=gate_reasons,
            )
        )
    return summaries


def choose_recommendation(
    summaries: list[BaselineSummary],
    *,
    min_success_rate: float,
    max_success_rate: float,
) -> Optional[BaselineSummary]:
    if not summaries:
        return None
    success_mid = (min_success_rate + max_success_rate) / 2.0

    def sort_key(summary: BaselineSummary) -> tuple:
        success_rate = summary.success_rate if summary.success_rate is not None else -1.0
        best_improvement = summary.best_improvement or -math.inf
        return (
            1 if summary.passes_gate else 0,
            len(summary.winning_categories),
            -abs(success_rate - success_mid),
            best_improvement,
        )

    return max(summaries, key=sort_key)


def _fmt_float(value: Optional[float], digits: int = 6) -> str:
    if value is None:
        return "NA"
    return f"{value:.{digits}f}"


def _fmt_rate(value: Optional[float]) -> str:
    if value is None:
        return "NA"
    return f"{value:.1%}"


def write_tsv(path: Path, results: list[TrialResult]) -> None:
    columns = [
        "id",
        "baseline_id",
        "category",
        "status",
        "val_bpb",
        "improvement",
        "success",
        "total_seconds",
        "total_steps",
        "description",
    ]
    lines = ["\t".join(columns)]
    for row in results:
        values = {
            "id": row.id,
            "baseline_id": row.baseline_id,
            "category": row.category,
            "status": row.status,
            "val_bpb": "" if row.val_bpb is None else f"{row.val_bpb:.6f}",
            "improvement": "" if row.improvement is None else f"{row.improvement:.6f}",
            "success": "" if row.success is None else str(row.success).lower(),
            "total_seconds": "" if row.total_seconds is None else f"{row.total_seconds:.3f}",
            "total_steps": "" if row.total_steps is None else str(row.total_steps),
            "description": row.description,
        }
        lines.append("\t".join(values[column] for column in columns))
    path.write_text("\n".join(lines) + "\n")


def write_markdown_report(
    path: Path,
    *,
    results: list[TrialResult],
    summaries: list[BaselineSummary],
    recommendation: Optional[BaselineSummary],
    train_max_steps: int,
    min_delta: float,
    min_categories: int,
    min_success_rate: float,
    max_success_rate: float,
    dry_run: bool = False,
) -> None:
    lines = [
        "# Baseline Headroom Calibration Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Protocol",
        "",
        f"- Fixed-step evaluator: `AUTOSEARCH_MAX_STEPS = {train_max_steps}`",
        f"- Improvement threshold: baseline val_bpb minus `{min_delta:.6f}`",
        f"- Category gate: at least `{min_categories}` winning categories",
        f"- Success-rate gate: `{min_success_rate:.0%}` to `{max_success_rate:.0%}` of completed edit trials",
        f"- Dry run only: `{str(dry_run).lower()}`",
        "",
        "## Recommendation",
        "",
    ]
    if recommendation is None:
        lines.append("No baseline candidates were evaluated.")
    elif recommendation.passes_gate:
        lines.extend(
            [
                f"Recommended baseline: `{recommendation.baseline_id}`",
                "",
                f"Proposed `q*`: `{_fmt_float(recommendation.proposed_q_star)}`",
                "",
                "This candidate passed the calibration gate. Use this `q*` only for the",
                "next confirmatory design if it was selected before running the 2x2.",
            ]
        )
    else:
        lines.extend(
            [
                "No candidate passed the calibration gate.",
                "",
                f"Closest candidate: `{recommendation.baseline_id}`",
                "",
                "Reasons:",
            ]
        )
        lines.extend(f"- {reason}" for reason in recommendation.gate_reasons)

    lines.extend(
        [
            "",
            "## Baseline Summary",
            "",
            "| baseline | baseline val_bpb | edits | success rate | winning categories | best edit | best improvement | q* | gate |",
            "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for summary in summaries:
        lines.append(
            "| {baseline} | {base} | {succ}/{completed} | {rate} | {cats} | {best} | {imp} | {qstar} | {gate} |".format(
                baseline=summary.baseline_id,
                base=_fmt_float(summary.baseline_val_bpb),
                succ=summary.successful_edits,
                completed=summary.completed_edits,
                rate=_fmt_rate(summary.success_rate),
                cats=len(summary.winning_categories),
                best=summary.best_edit_trial or "NA",
                imp=_fmt_float(summary.best_improvement),
                qstar=_fmt_float(summary.proposed_q_star),
                gate="pass" if summary.passes_gate else "fail",
            )
        )

    lines.extend(["", "## Category Bests", ""])
    for summary in summaries:
        lines.extend(
            [
                f"### {summary.baseline_id}",
                "",
                "| category | successes | best val_bpb | best trial |",
                "| --- | ---: | ---: | --- |",
            ]
        )
        for category in sorted(summary.category_completed_counts):
            successes = summary.category_success_counts.get(category, 0)
            completed = summary.category_completed_counts.get(category, 0)
            lines.append(
                "| {category} | {succ}/{completed} | {best} | {trial} |".format(
                    category=category,
                    succ=successes,
                    completed=completed,
                    best=_fmt_float(summary.category_best_val_bpb.get(category)),
                    trial=summary.category_best_trial.get(category, "NA"),
                )
            )
        if summary.gate_reasons:
            lines.extend(["", "Gate reasons:"])
            lines.extend(f"- {reason}" for reason in summary.gate_reasons)
        lines.append("")

    lines.extend(
        [
            "## Trial Table",
            "",
            "| trial | baseline | category | status | val_bpb | improvement | success | steps | seconds |",
            "| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for row in results:
        lines.append(
            "| {trial} | {baseline} | {category} | {status} | {val} | {imp} | {success} | {steps} | {seconds} |".format(
                trial=row.id,
                baseline=row.baseline_id,
                category=row.category,
                status=row.status,
                val=_fmt_float(row.val_bpb),
                imp=_fmt_float(row.improvement),
                success="NA" if row.success is None else str(row.success).lower(),
                steps="NA" if row.total_steps is None else str(row.total_steps),
                seconds=_fmt_float(row.total_seconds, digits=3),
            )
        )

    path.write_text("\n".join(lines) + "\n")


def _parse_id_list(raw: Optional[str]) -> Optional[set[str]]:
    if not raw:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


def _write_payload(
    out_dir: Path,
    *,
    plan: list[TrialSpec],
    results: list[TrialResult],
    summaries: list[BaselineSummary],
    recommendation: Optional[BaselineSummary],
    args: argparse.Namespace,
    dry_run: bool,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "baseline_headroom_plan.json").write_text(
        json.dumps([asdict(spec) for spec in plan], indent=2)
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "args": vars(args),
        "dry_run": dry_run,
        "plan_count": len(plan),
        "results": [asdict(result) for result in results],
        "summaries": [asdict(summary) for summary in summaries],
        "recommendation": asdict(recommendation) if recommendation else None,
    }
    (out_dir / "baseline_headroom_results.json").write_text(json.dumps(payload, indent=2))
    write_tsv(out_dir / "baseline_headroom_trials.tsv", results)
    write_markdown_report(
        out_dir / "baseline_headroom_report.md",
        results=results,
        summaries=summaries,
        recommendation=recommendation,
        train_max_steps=args.train_max_steps,
        min_delta=args.min_delta,
        min_categories=args.min_categories,
        min_success_rate=args.min_success_rate,
        max_success_rate=args.max_success_rate,
        dry_run=dry_run,
    )


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run controlled baseline-headroom calibration for AutoResearch."
    )
    parser.add_argument("--out-dir", type=str, default=None)
    parser.add_argument("--autoresearch-dir", type=str, default=None)
    parser.add_argument("--train-max-steps", type=int, default=1170)
    parser.add_argument("--train-time-budget", type=int, default=300)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--min-delta", type=float, default=0.005)
    parser.add_argument("--min-categories", type=int, default=3)
    parser.add_argument("--min-success-rate", type=float, default=0.10)
    parser.add_argument("--max-success-rate", type=float, default=0.30)
    parser.add_argument("--baseline-ids", type=str, default=None, help="Comma-separated baseline IDs.")
    parser.add_argument("--edit-ids", type=str, default=None, help="Comma-separated edit IDs.")
    parser.add_argument("--baselines-json", type=str, default=None, help="JSON list of custom baseline specs.")
    parser.add_argument("--edits-json", type=str, default=None, help="JSON list of custom edit specs.")
    parser.add_argument("--extended-panel", action="store_true", help="Use the broader built-in follow-up panel.")
    parser.add_argument("--include-current-control", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-run trials even if cached metrics exist.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    autoresearch_dir = Path(args.autoresearch_dir) if args.autoresearch_dir else repo_root / "autoresearch"
    autoresearch_dir = autoresearch_dir.resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else _default_out_dir(repo_root)
    train_path = autoresearch_dir / "train.py"
    train_source = train_path.read_text()

    if args.baselines_json:
        baselines = load_change_specs(Path(args.baselines_json))
    elif args.extended_panel:
        baselines = extended_baselines(include_current_control=args.include_current_control)
    else:
        baselines = default_baselines(include_current_control=args.include_current_control)

    if args.edits_json:
        edits = load_change_specs(Path(args.edits_json))
    elif args.extended_panel:
        edits = extended_edit_panel()
    else:
        edits = default_edit_panel()

    plan = build_calibration_plan(
        train_source,
        baselines=baselines,
        edits=edits,
        baseline_ids=_parse_id_list(args.baseline_ids),
        edit_ids=_parse_id_list(args.edit_ids),
        include_current_control=False,
    )
    print(f"[calibration] Output directory: {out_dir}")
    print(f"[calibration] Planned trials: {len(plan)}")
    print(f"[calibration] Fixed steps: {args.train_max_steps}")

    results: list[TrialResult] = []
    if not args.dry_run:
        trials_dir = out_dir / "trials"
        for index, spec in enumerate(plan, start=1):
            print(
                f"[calibration] {index}/{len(plan)} {spec.id} "
                f"({spec.category})",
                flush=True,
            )
            result = run_trial(
                spec=spec,
                autoresearch_dir=autoresearch_dir,
                train_source=train_source,
                trials_dir=trials_dir,
                train_max_steps=args.train_max_steps,
                train_time_budget_seconds=args.train_time_budget,
                timeout_seconds=args.timeout,
                force=args.force,
            )
            results.append(result)
            val = "NA" if result.val_bpb is None else f"{result.val_bpb:.6f}"
            print(f"[calibration]   status={result.status} val_bpb={val}")

    results = attach_improvements(results, min_delta=args.min_delta)
    summaries = summarize_baselines(
        results,
        min_delta=args.min_delta,
        min_categories=args.min_categories,
        min_success_rate=args.min_success_rate,
        max_success_rate=args.max_success_rate,
    )
    recommendation = choose_recommendation(
        summaries,
        min_success_rate=args.min_success_rate,
        max_success_rate=args.max_success_rate,
    )
    _write_payload(
        out_dir,
        plan=plan,
        results=results,
        summaries=summaries,
        recommendation=recommendation,
        args=args,
        dry_run=args.dry_run,
    )

    if recommendation is None:
        print("[calibration] No completed summaries.")
    elif recommendation.passes_gate:
        print(
            "[calibration] PASS "
            f"baseline={recommendation.baseline_id} "
            f"q*={recommendation.proposed_q_star:.6f}"
        )
    else:
        print(f"[calibration] NO PASS closest={recommendation.baseline_id}")
        for reason in recommendation.gate_reasons:
            print(f"[calibration]   {reason}")
    print(f"[calibration] Wrote {out_dir / 'baseline_headroom_report.md'}")


if __name__ == "__main__":
    main()
