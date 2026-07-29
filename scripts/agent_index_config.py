"""Shared configuration for agent-facing repository indexes."""

from __future__ import annotations

from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "tmp",
    "runs",
}

CANONICAL_DOCS = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/README.md",
    "docs/knowledge-map.md",
    "docs/paper-evidence-map.md",
    "docs/paper-revision-playbook.md",
    "docs/reproducibility.md",
    "docs/demo.md",
    "docs/audits/theory-consolidation.md",
    "docs/audits/knowledge-index.md",
    "docs/audits/repo-inventory.md",
    "docs/audits/paper-archive-manifest.md",
    "docs/audits/experiment-manifest.md",
    "docs/audits/command-manifest.md",
    "docs/audits/agent-readiness-completion-audit.md",
    "experiments/README.md",
    "src/README.md",
    "scripts/README.md",
    "autoresearch/README.md",
    "autoresearch/scripts/README.md",
    "paper/README.md",
    "paper/neurips-submission/README.md",
]

COMMAND_ENTRYPOINTS = [
    "Makefile",
]
CANONICAL_ENTRYPOINTS = CANONICAL_DOCS + COMMAND_ENTRYPOINTS
REQUIRED_MAKE_TARGETS = [
    "indexes",
    "readiness",
    "compile",
    "test",
    "check",
    "paper-build",
    "paper-figures-autoresearch",
]

PAPER_ROOT = Path("paper/neurips-submission")
CANONICAL_TEX = [
    PAPER_ROOT / "main.tex",
    PAPER_ROOT / "arxiv.tex",
    PAPER_ROOT / "archive" / "theory_anchor.tex",
    PAPER_ROOT / "archive" / "Beneventano_Poggio.tex",
    PAPER_ROOT / "archive" / "next_steps.tex",
]
PAPER_SOURCES = [path.as_posix() for path in CANONICAL_TEX]

GENERATED_AUDITS = {
    "knowledge": Path("docs/audits/knowledge-index.md"),
    "inventory": Path("docs/audits/repo-inventory.md"),
    "paper_archive": Path("docs/audits/paper-archive-manifest.md"),
    "experiment_manifest": Path("docs/audits/experiment-manifest.md"),
    "command_manifest": Path("docs/audits/command-manifest.md"),
}
GENERATED_AUDIT_PATHS = set(GENERATED_AUDITS.values())

LOCAL_PATH_PATTERNS = (
    "/Users/",
    "/private/var/",
)

SCRIPT_DIRS = (
    Path("scripts"),
    Path("autoresearch/scripts"),
)
SCRIPT_SUPPORT_FILES = {
    "README.md",
    "agent_index_config.py",
}

AGENT_DOC_ROOT_FILES = [
    Path("README.md"),
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
]
MARKDOWN_LINK_DOCS = [
    Path(path)
    for path in [
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "docs/README.md",
        "docs/knowledge-map.md",
        "docs/paper-evidence-map.md",
        "docs/paper-revision-playbook.md",
        "docs/reproducibility.md",
        "docs/demo.md",
        "docs/audits/paper-archive-manifest.md",
        "docs/audits/experiment-manifest.md",
        "docs/audits/command-manifest.md",
        "docs/audits/agent-readiness-completion-audit.md",
        "docs/specs/README.md",
        "paper/README.md",
        "paper/neurips-submission/README.md",
        "src/README.md",
        "scripts/README.md",
        "autoresearch/README.md",
        "autoresearch/scripts/README.md",
    ]
]
