"""Prompt template rendering for model backends."""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any

PROMPT_DIR = Path(__file__).resolve().parent
AUTORESEARCH_PROMPT_DIR = Path(__file__).resolve().parents[3] / "autoresearch" / "prompts"


def render_template(name: str, **kwargs: Any) -> str:
    template_path = PROMPT_DIR / name
    if not template_path.exists() and name.startswith("autoresearch_"):
        template_path = AUTORESEARCH_PROMPT_DIR / name
    if not template_path.exists():
        raise ValueError(f"unsupported prompt template {name!r}")
    template = Template(template_path.read_text(encoding="utf-8"))
    safe_kwargs = {key: str(value) for key, value in kwargs.items()}
    return template.safe_substitute(safe_kwargs)
