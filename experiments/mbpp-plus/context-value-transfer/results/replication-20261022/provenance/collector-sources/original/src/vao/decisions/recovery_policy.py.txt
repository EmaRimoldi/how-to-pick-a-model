"""Small frozen ridge probability baselines for selecting a recovery action."""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from .context_value import ARMS, observable_features


TASK_FEATURES = ("log_prompt_characters", "log_prompt_lines")
STATE_FEATURES = TASK_FEATURES + ("log_code_characters", "log_ast_nodes", "syntax_valid",
    "base_failure_fraction", "name_error", "syntax_error", "type_error", "timeout", "format_error")


def features(prompt: str, checkpoint: dict) -> dict:
    """No evaluation-only score or test-task identity is an input feature."""
    visible = checkpoint["feedback"]
    observed = observable_features(checkpoint["solution"], visible)
    attempted = visible.get("attempted", 0) or 0
    failed = visible.get("failed", attempted) or 0
    return {"log_prompt_characters": math.log1p(len(prompt)), "log_prompt_lines": math.log1p(len(prompt.splitlines())),
        "log_code_characters": math.log1p(len(checkpoint["solution"])),
        "log_ast_nodes": math.log1p(observed["ast_nodes"]), "syntax_valid": float(observed["syntax_valid"]),
        "base_failure_fraction": failed / attempted if attempted else 1.0,
        **{k: float(observed[k]) for k in ("name_error", "syntax_error", "type_error", "timeout")},
        "format_error": float(visible["status"] == "format_error")}


def fit_policy(checkpoints: list[dict], branches: list[dict], prompts: dict[str, str], config: dict,
               *, views: dict[str, tuple[str, ...]] | None = None) -> dict:
    """Fit declared shrinkage baselines on development outcomes only, one parent per task."""
    keys = [model + "." + arm for model in config["target_models"] for arm in ARMS]
    by_cp = {c["checkpoint_id"]: c for c in checkpoints}
    if len({c["task_id"] for c in checkpoints}) < config["minimum_development_failed_tasks"]:
        raise ValueError("Insufficient diverse development failures for a fitted policy")
    groups = defaultdict(list)
    for row in branches:
        if row["arm"] in ARMS:
            groups[row["model_name"] + "." + row["arm"]].append(row)
    priors, costs, fitted = {}, {}, {}
    for key in keys:
        rows = groups[key]
        if len(rows) != len(checkpoints) * config["branch_repeats"]:
            raise ValueError("Development cells are incomplete")
        priors[key] = (1 + sum(r["passed"] for r in rows)) / (2 + len(rows))
        costs[key] = float(np.mean([r["incremental_cost_usd"] for r in rows]))
    for view, names in (views or {"task": TASK_FEATURES, "state": STATE_FEATURES}).items():
        raw = np.array([[features(prompts[c["task_id"]], c)[n] for n in names] for c in checkpoints])
        mu, scale = raw.mean(axis=0), raw.std(axis=0)
        scale[scale < 1e-8] = 1.0
        coefficients = {}
        for key in keys:
            rows = groups[key]
            x = np.array([[(features(prompts[r["task_id"]], by_cp[r["checkpoint_id"]])[n] - mu[i]) / scale[i]
                           for i, n in enumerate(names)] for r in rows])
            y = np.array([float(r["passed"]) - priors[key] for r in rows])
            coefficients[key] = np.linalg.solve(x.T @ x + config["ridge_penalty"] * np.eye(len(names)), x.T @ y).tolist()
        fitted[view] = {"features": list(names), "mean": mu.tolist(), "scale": scale.tolist(), "coefficients": coefficients}
    best = max(keys, key=lambda k: config["solution_value_usd"] * priors[k] - costs[k])
    return {"schema": "recovery-ridge-v1", "training_task_ids": sorted(c["task_id"] for c in checkpoints),
            "priors": priors, "mean_action_cost_usd": costs, "best_fixed_action": best, "fits": fitted,
            "ridge_penalty": config["ridge_penalty"], "solution_value_usd": config["solution_value_usd"]}


def predict(policy: dict, prompt: str, checkpoint: dict, view: str) -> dict:
    """Predict from frozen weights; clipping is fixed and never tuned on evaluation tasks."""
    if view == "global":
        return dict(policy["priors"])
    fit = policy["fits"][view]
    observed = features(prompt, checkpoint)
    x = [(observed[n] - fit["mean"][i]) / fit["scale"][i] for i, n in enumerate(fit["features"])]
    return {key: float(np.clip(policy["priors"][key] + np.dot(x, weights), 0.01, 0.99))
            for key, weights in fit["coefficients"].items()}
