"""Task definitions for the AutoResearch-style CIFAR-10 benchmark."""

from __future__ import annotations

import ast
import difflib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from benchmarks.autoresearch_cifar10.initial_templates import template_path_for_task_mode

METADATA_PATH = Path(__file__).resolve().parent / "metadata" / "instance_config.json"

TASK_MODE_DESCRIPTIONS = {
    "lr-sensitive": "Instances where small learning-rate or local optimization-scale changes dominate the next gain.",
    "regularization-sensitive": "Instances where robustness, overfitting control, or label-noise handling dominate.",
    "optimizer-sensitive": "Instances where optimizer family or gradient-dynamics choices dominate.",
    "data-skew-sensitive": "Instances where class imbalance, coverage, or skew-aware data handling dominate.",
    "capacity-sensitive": "Instances where model depth, width, or architectural capacity dominate.",
    "schedule-sensitive": "Instances where warmup, decay, or long-horizon budget allocation dominate.",
}

LATENT_MODE_REGISTRY: dict[str, dict[str, Any]] = {
    "lr-sensitive": {
        "description": "Clean balanced full-CIFAR regime with a tiny fixed-step budget where learning-rate scale dominates early progress.",
        "train_subset_size": 50000,
        "val_subset_size": 10000,
        "label_noise_rate": 0.0,
        "imbalance_ratio": 1.0,
        "max_train_steps": 128,
        "seed": 61,
    },
    "regularization-sensitive": {
        "description": "Short-horizon full-CIFAR training with synthetic label noise, making regularization choices the main lever.",
        "train_subset_size": 50000,
        "val_subset_size": 10000,
        "label_noise_rate": 0.25,
        "imbalance_ratio": 1.0,
        "max_train_steps": 128,
        "seed": 67,
    },
    "optimizer-sensitive": {
        "description": "Balanced regime where optimizer family and gradient dynamics dominate more than local hyperparameter tweaks.",
        "train_subset_size": 50000,
        "val_subset_size": 10000,
        "label_noise_rate": 0.0,
        "imbalance_ratio": 1.0,
        "max_train_steps": 128,
        "seed": 69,
    },
    "data-skew-sensitive": {
        "description": "Long-tail regime under the same compute budget, emphasizing class coverage and skew-aware training choices.",
        "train_subset_size": 50000,
        "val_subset_size": 10000,
        "label_noise_rate": 0.0,
        "imbalance_ratio": 0.12,
        "max_train_steps": 128,
        "seed": 71,
    },
    "capacity-sensitive": {
        "description": "Clean regime with a longer horizon where architecture capacity is the main solver-relevant bottleneck.",
        "train_subset_size": 50000,
        "val_subset_size": 10000,
        "label_noise_rate": 0.0,
        "imbalance_ratio": 1.0,
        "max_train_steps": 512,
        "seed": 73,
    },
    "schedule-sensitive": {
        "description": "Clean regime with a longer horizon where scheduling and budget allocation dominate the next verified gains.",
        "train_subset_size": 50000,
        "val_subset_size": 10000,
        "label_noise_rate": 0.0,
        "imbalance_ratio": 1.0,
        "max_train_steps": 512,
        "seed": 79,
    },
}

ALL_FAMILIES = list(LATENT_MODE_REGISTRY)
TASK_MODE_SET = set(ALL_FAMILIES)

ACTION_MODE_ALIASES = {
    "layout": "architecture/capacity changes",
    "indexing": "optimizer-family changes",
    "topk": "learning-rate scale changes",
    "caching": "regularization changes",
    "summaries": "schedule and budget-allocation changes",
    "micro": "small batching or local loop tweaks",
}

REQUIRED_BINDINGS = {
    "SEED",
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
    "BATCH_SIZE",
    "NUM_WORKERS",
    "CIFAR10Net",
    "build_optimizer",
    "build_scheduler",
    "main",
}

BANNED_IMPORT_ROOTS = {"subprocess", "socket", "requests", "pathlib"}


def load_instance_config() -> dict[str, Any]:
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def validate_task_mode(mode: str) -> str:
    if mode not in LATENT_MODE_REGISTRY:
        raise ValueError(f"Unknown AutoResearch task mode {mode!r}; expected one of {sorted(LATENT_MODE_REGISTRY)}")
    return mode


def single_family_instance_overrides(
    family: str,
    *,
    seed: int | None = None,
    train_subset_size: int | None = None,
    val_subset_size: int | None = None,
    label_noise_rate: float | None = None,
    imbalance_ratio: float | None = None,
    max_train_steps: int | None = None,
) -> dict[str, Any]:
    validate_task_mode(family)
    spec = deepcopy(LATENT_MODE_REGISTRY[family])
    if seed is not None:
        spec["seed"] = int(seed)
    if train_subset_size is not None:
        spec["train_subset_size"] = int(train_subset_size)
    if val_subset_size is not None:
        spec["val_subset_size"] = int(val_subset_size)
    if label_noise_rate is not None:
        spec["label_noise_rate"] = float(label_noise_rate)
    if imbalance_ratio is not None:
        spec["imbalance_ratio"] = float(imbalance_ratio)
    if max_train_steps is not None:
        spec["max_train_steps"] = int(max_train_steps)
    return {"families": [family], **spec}


def task_mode_template_path(mode: str) -> Path:
    return template_path_for_task_mode(validate_task_mode(mode))


def apply_instance_overrides(config: dict[str, Any], profile_id: str, instance_overrides: dict[str, Any] | None) -> dict[str, Any]:
    effective = deepcopy(config)
    profile = effective["profiles"][profile_id]
    if not instance_overrides:
        return effective
    for key, value in instance_overrides.items():
        profile[key] = deepcopy(value)
    if "families" in profile:
        for family in profile["families"]:
            validate_task_mode(str(family))
    return effective


def task_mode_from_instance_overrides(instance_overrides: dict[str, Any] | None) -> str | None:
    if not instance_overrides:
        return None
    families = instance_overrides.get("families")
    if isinstance(families, list) and len(families) == 1:
        return validate_task_mode(str(families[0]))
    return None


def profile_summary(profile_id: str, instance_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    config = load_instance_config()
    effective = apply_instance_overrides(config, profile_id, instance_overrides)
    profile = effective["profiles"][profile_id]
    task_mode_true = task_mode_from_instance_overrides(instance_overrides)
    template_path = str(task_mode_template_path(task_mode_true)) if task_mode_true else None
    return {
        "profile_id": profile_id,
        "task_mode_true": task_mode_true,
        "families": profile.get("families", []),
        "train_subset_size": int(profile.get("train_subset_size", 0)),
        "val_subset_size": int(profile.get("val_subset_size", 0)),
        "label_noise_rate": float(profile.get("label_noise_rate", 0.0)),
        "imbalance_ratio": float(profile.get("imbalance_ratio", 1.0)),
        "max_train_steps": int(profile.get("max_train_steps", 0)),
        "seed": int(profile.get("seed", 0)),
        "task_mode_descriptions": TASK_MODE_DESCRIPTIONS,
        "action_mode_aliases": ACTION_MODE_ALIASES,
        "initial_template_path": template_path,
    }


def runtime_env(profile_id: str, instance_overrides: dict[str, Any] | None = None) -> dict[str, str]:
    summary = profile_summary(profile_id, instance_overrides)
    data_dir = Path(__file__).resolve().parent / "data"
    return {
        "AUTOSEARCH_DATA_SEED": str(summary["seed"]),
        "AUTOSEARCH_TRAIN_SUBSET": str(summary["train_subset_size"]),
        "AUTOSEARCH_VAL_SUBSET": str(summary["val_subset_size"]),
        "AUTOSEARCH_LABEL_NOISE": str(summary["label_noise_rate"]),
        "AUTOSEARCH_IMBALANCE_RATIO": str(summary["imbalance_ratio"]),
        "AUTOSEARCH_MAX_STEPS": str(summary["max_train_steps"]),
        "AUTOSEARCH_LATENT_MODE": str(summary["task_mode_true"] or "mixed"),
        "AUTOSEARCH_DATA_DIR": str(data_dir),
    }


def validate_solution_source(source_text: str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        return {"passed": False, "errors": [f"syntax_error:{exc.msg}:{exc.lineno}:{exc.offset}"]}

    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    found.add(target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)

    missing = sorted(REQUIRED_BINDINGS - found)
    if missing:
        errors.append(f"missing_bindings:{','.join(missing)}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in BANNED_IMPORT_ROOTS:
                    errors.append(f"banned_import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if module in BANNED_IMPORT_ROOTS:
                errors.append(f"banned_import:{node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval", "open"}:
            errors.append(f"banned_call:{node.func.id}")

    return {"passed": not errors, "errors": errors}


def classify_edit_mode(pre_source: str, post_source: str) -> tuple[str, list[str], dict[str, Any]]:
    if pre_source == post_source:
        return "micro", [], {"reason": "no_source_change", "scores": {"micro": 1.0}}

    added, removed = _changed_lines(pre_source, post_source)
    changed_names = _changed_bindings(pre_source, post_source)
    scores = {mode: 0.0 for mode in ACTION_MODE_ALIASES}
    evidence: dict[str, list[str]] = {mode: [] for mode in ACTION_MODE_ALIASES}

    def add(mode: str, amount: float, note: str) -> None:
        scores[mode] += amount
        evidence[mode].append(note)

    if changed_names & {"DEPTH", "BASE_CHANNELS", "CHANNEL_MULT", "USE_BATCHNORM", "FC_HIDDEN", "CIFAR10Net"}:
        add("layout", 4.0, f"architecture bindings changed: {sorted(changed_names & {'DEPTH', 'BASE_CHANNELS', 'CHANNEL_MULT', 'USE_BATCHNORM', 'FC_HIDDEN', 'CIFAR10Net'})}")
    if changed_names & {"OPTIMIZER", "MOMENTUM", "ADAM_BETAS", "build_optimizer"}:
        add("indexing", 4.0, f"optimizer bindings changed: {sorted(changed_names & {'OPTIMIZER', 'MOMENTUM', 'ADAM_BETAS', 'build_optimizer'})}")
    if changed_names & {"LEARNING_RATE"}:
        add("topk", 4.0, "learning rate changed")
    if changed_names & {"WEIGHT_DECAY", "DROPOUT_RATE"}:
        add("caching", 4.0, f"regularization bindings changed: {sorted(changed_names & {'WEIGHT_DECAY', 'DROPOUT_RATE'})}")
    if changed_names & {"USE_LR_SCHEDULE", "WARMUP_EPOCHS", "LR_DECAY_FACTOR", "LR_DECAY_EPOCHS", "build_scheduler"}:
        add("summaries", 4.0, f"schedule bindings changed: {sorted(changed_names & {'USE_LR_SCHEDULE', 'WARMUP_EPOCHS', 'LR_DECAY_FACTOR', 'LR_DECAY_EPOCHS', 'build_scheduler'})}")
    if changed_names & {"BATCH_SIZE", "NUM_WORKERS", "main"}:
        add("micro", 2.0, f"data-loading or loop bindings changed: {sorted(changed_names & {'BATCH_SIZE', 'NUM_WORKERS', 'main'})}")

    lower_added = "\n".join(added).lower()
    if "clip_grad" in lower_added or "nan" in lower_added:
        add("indexing", 1.5, "gradient stability helper added")
    if all(value == 0.0 for value in scores.values()):
        add("micro", 1.0, "no benchmark-specific structural evidence")

    priority = list(ACTION_MODE_ALIASES)
    primary = max(scores, key=lambda mode: (scores[mode], -priority.index(mode)))
    secondary = [mode for mode in priority if mode != primary and scores[mode] > 0.0]
    details = {
        "scores": scores,
        "evidence": {mode: rows for mode, rows in evidence.items() if rows},
        "changed_bindings": sorted(changed_names),
        "added_line_count": len(added),
        "removed_line_count": len(removed),
        "action_mode_aliases": ACTION_MODE_ALIASES,
    }
    return primary, secondary, details


def _changed_lines(pre_source: str, post_source: str) -> tuple[list[str], list[str]]:
    added: list[str] = []
    removed: list[str] = []
    for line in difflib.ndiff(pre_source.splitlines(), post_source.splitlines()):
        if line.startswith("+ "):
            added.append(line[2:])
        elif line.startswith("- "):
            removed.append(line[2:])
    return added, removed


def _binding_sources(source: str) -> dict[str, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    lines = source.splitlines()
    bindings: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            end = getattr(node, "end_lineno", node.lineno)
            chunk = "\n".join(lines[node.lineno - 1 : end])
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = chunk
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            end = getattr(node, "end_lineno", node.lineno)
            bindings[node.target.id] = "\n".join(lines[node.lineno - 1 : end])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            end = getattr(node, "end_lineno", node.lineno)
            bindings[node.name] = "\n".join(lines[node.lineno - 1 : end])
    return bindings


def _changed_bindings(pre_source: str, post_source: str) -> set[str]:
    pre = _binding_sources(pre_source)
    post = _binding_sources(post_source)
    names = set(pre) | set(post)
    return {name for name in names if pre.get(name) != post.get(name)}
