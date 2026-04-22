"""Prompt template rendering for model backends."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

PROMPT_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def shared_canonical_task() -> str:
    """Return the backend-independent task/protocol block."""
    return (PROMPT_DIR / "shared_canonical_task.txt").read_text(encoding="utf-8")


def render_template(name: str, **kwargs: Any) -> str:
    template_path = PROMPT_DIR / name
    template = Template(template_path.read_text(encoding="utf-8"))
    safe_kwargs = {key: str(value) for key, value in kwargs.items()}
    safe_kwargs.setdefault("shared_canonical_task", shared_canonical_task())
    return template.safe_substitute(safe_kwargs)
