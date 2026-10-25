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
    "docs/decision-protocol.md",
    "docs/paper-evidence-map.md",
    "docs/paper-revision-playbook.md",
    "docs/reproducibility.md",
    "docs/engineering/architecture.md",
    "docs/engineering/layout.md",
    "docs/audits/branch-consolidation.md",
    "docs/audits/theory-consolidation.md",
    "docs/audits/knowledge-index.md",
    "docs/audits/repo-inventory.md",
    "docs/audits/experiment-manifest.md",
    "docs/audits/command-manifest.md",
    "experiments/README.md",
    "src/README.md",
    "scripts/README.md",
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
]

CORE_EXPERIMENT_BUNDLES = {
    "experiments/humaneval-plus/qwen-model-size-frontier/",
    "experiments/humaneval-plus/retry-allocation-router/",
    "experiments/humaneval-plus/strategy-by-difficulty-grid/",
    "experiments/humaneval-plus/llm-router-context-search/",
}

CORE_CODE_MODULES = {
    "src/vao/schemas.py",
    "src/vao/decisions/pilot.py",
    "src/vao/decisions/context_value.py",
    "src/vao/decisions/recovery.py",
    "src/vao/decisions/recovery_policy.py",
    "src/vao/decisions/recovery_import.py",
    "src/vao/decisions/openrouter.py",
    "src/vao/decisions/verification.py",
    "src/vao/humaneval/load_traces.py",
}

PAPER_ROOT = Path("paper/neurips-submission")
CANONICAL_TEX = [
    PAPER_ROOT / "main.tex",
    PAPER_ROOT / "arxiv.tex",
    PAPER_ROOT / "archive" / "theory_anchor.tex",
]
PAPER_SOURCES = [path.as_posix() for path in CANONICAL_TEX]

GENERATED_AUDITS = {
    "knowledge": Path("docs/audits/knowledge-index.md"),
    "inventory": Path("docs/audits/repo-inventory.md"),
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
    Path("scripts/maintenance"),
    Path("scripts/cluster"),
)
SCRIPT_SUPPORT_FILES = {
    "README.md",
    "agent_index_config.py",
    "requirements.txt",
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
        "docs/decision-protocol.md",
        "docs/paper-evidence-map.md",
        "docs/paper-revision-playbook.md",
        "docs/reproducibility.md",
        "docs/engineering/architecture.md",
        "docs/engineering/layout.md",
        "docs/audits/branch-consolidation.md",
        "docs/history-merge.md",
        "docs/audits/experiment-cleanup.md",
        "experiments/humaneval-plus/README.md",
        "experiments/humaneval-plus/qwen-model-size-frontier/README.md",
        "experiments/humaneval-plus/retry-allocation-router/README.md",
        "experiments/humaneval-plus/context-value/provenance/continuation-pilot/README.md",
        "docs/audits/experiment-manifest.md",
        "docs/audits/command-manifest.md",
        "paper/README.md",
        "paper/neurips-submission/README.md",
        "src/README.md",
        "scripts/README.md",
    ]
]
