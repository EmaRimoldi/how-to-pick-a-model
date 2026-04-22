"""Prompt template rendering for model backends."""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any

PROMPT_DIR = Path(__file__).resolve().parent


def render_template(name: str, **kwargs: Any) -> str:
    if name != "single_step_program.txt":
        raise ValueError(f"unsupported prompt template {name!r}; active model prompt is single_step_program.txt")
    template_path = PROMPT_DIR / name
    template = Template(template_path.read_text(encoding="utf-8"))
    safe_kwargs = {key: str(value) for key, value in kwargs.items()}
    return template.safe_substitute(safe_kwargs)
