"""Mode-specific initial AutoResearch templates.

These templates keep the benchmark executable while making the dominant
solver-relevant bottleneck visible in the starting ``train.py`` state.
The paper's task modes are still properties of whole task instances; these
initial states simply make the bottleneck easier to observe from the live
signal available to a router.
"""

from __future__ import annotations

from pathlib import Path

BASE_TEMPLATE_PATH = Path(__file__).resolve().parent / "solution_template.py"
GENERATED_DIR = Path(__file__).resolve().parent / "initial_states"
RECOMMENDED_PATH = Path(__file__).resolve().parent / "recommended_initializations.json"

MODE_KEYS = {
    "lr-sensitive",
    "regularization-sensitive",
    "optimizer-sensitive",
    "data-skew-sensitive",
    "capacity-sensitive",
    "schedule-sensitive",
}

_DEFAULT_TEMPLATE_REPLACEMENTS: dict[str, dict[str, str]] = {
    "lr-sensitive": {
        "LEARNING_RATE = 5e-4": "LEARNING_RATE = 5e-5",
        "# --- Optimizer hyperparameters ----------------------------------------------": "# Mode seed: lr-sensitive\n# --- Optimizer hyperparameters ----------------------------------------------",
    },
    "regularization-sensitive": {
        "WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 0.0",
        "# --- Architecture hyperparameters -------------------------------------------": "# Mode seed: regularization-sensitive\n# --- Architecture hyperparameters -------------------------------------------",
    },
    "optimizer-sensitive": {
        'OPTIMIZER = "adam"': 'OPTIMIZER = "sgd"',
        "LEARNING_RATE = 5e-4": "LEARNING_RATE = 2e-2",
        "MOMENTUM = 0.9": "MOMENTUM = 0.0",
        "# --- Optimizer hyperparameters ----------------------------------------------": "# Mode seed: optimizer-sensitive\n# --- Optimizer hyperparameters ----------------------------------------------",
    },
    "data-skew-sensitive": {
        "BATCH_SIZE = 64": "BATCH_SIZE = 128",
        "WEIGHT_DECAY = 1e-4": "WEIGHT_DECAY = 0.0",
        "# --- Batch / data hyperparameters -------------------------------------------": "# Mode seed: data-skew-sensitive\n# --- Batch / data hyperparameters -------------------------------------------",
    },
    "capacity-sensitive": {
        "DEPTH = 2": "DEPTH = 1",
        "BASE_CHANNELS = 12": "BASE_CHANNELS = 8",
        "FC_HIDDEN = 48": "FC_HIDDEN = 16",
        "# --- Architecture hyperparameters -------------------------------------------": "# Mode seed: capacity-sensitive\n# --- Architecture hyperparameters -------------------------------------------",
    },
    "schedule-sensitive": {
        "LEARNING_RATE = 5e-4": "LEARNING_RATE = 1e-3",
        "WARMUP_EPOCHS = 2": "WARMUP_EPOCHS = 0",
        "# --- LR schedule hyperparameters --------------------------------------------": "# Mode seed: schedule-sensitive\n# --- LR schedule hyperparameters --------------------------------------------",
    },
}


def _load_recommendations() -> dict[str, dict[str, str]]:
    if not RECOMMENDED_PATH.exists():
        return _DEFAULT_TEMPLATE_REPLACEMENTS
    import json

    payload = json.loads(RECOMMENDED_PATH.read_text(encoding="utf-8"))
    replacements = {mode: dict(spec["replacements"]) for mode, spec in payload.items() if mode in MODE_KEYS}
    for mode in MODE_KEYS:
        replacements.setdefault(mode, dict(_DEFAULT_TEMPLATE_REPLACEMENTS.get(mode, {})))
    return replacements


_TEMPLATE_REPLACEMENTS = _load_recommendations()


def render_template_for_task_mode(task_mode: str) -> str:
    if task_mode not in MODE_KEYS:
        raise ValueError(f"unknown_task_mode:{task_mode}")
    text = BASE_TEMPLATE_PATH.read_text(encoding="utf-8")
    for old, new in _TEMPLATE_REPLACEMENTS.get(task_mode, {}).items():
        if old not in text:
            raise ValueError(f"template_anchor_missing:{task_mode}:{old}")
        text = text.replace(old, new, 1)
    marker = f"# Mode seed: {task_mode}\n"
    if marker not in text:
        anchor = "# ---"
        if anchor in text:
            text = text.replace(anchor, marker + anchor, 1)
    return text


def template_path_for_task_mode(task_mode: str) -> Path:
    if task_mode not in MODE_KEYS:
        raise ValueError(f"unknown_task_mode:{task_mode}")
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    path = GENERATED_DIR / f"{task_mode}.py"
    rendered = render_template_for_task_mode(task_mode)
    if not path.exists() or path.read_text(encoding="utf-8") != rendered:
        path.write_text(rendered, encoding="utf-8")
    return path
