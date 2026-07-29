"""Build a safety-classified command manifest for agent-facing workflows."""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from agent_index_config import REQUIRED_MAKE_TARGETS, SCRIPT_DIRS, SCRIPT_SUPPORT_FILES
from build_knowledge_index import command_targets


SAFE_LOCAL = "safe-local"
SAFE_OPTIONAL_TOOL = "safe-local-optional-tool"
FIGURE_REGEN = "safe-figure-regeneration"
READ_ONLY_ANALYSIS = "read-only-analysis"
LIVE_LOCAL = "live-local"
LIVE_CLUSTER = "live-cluster"
CLUSTER_SETUP = "cluster-setup"
ARTIFACT_BUILDER = "artifact-builder"
MIXED_CLI = "mixed-cli"
SUPPORT_CONFIG = "support-config"

SAFETY_ORDER = {
    SAFE_LOCAL: 0,
    SAFE_OPTIONAL_TOOL: 1,
    FIGURE_REGEN: 2,
    READ_ONLY_ANALYSIS: 3,
    ARTIFACT_BUILDER: 4,
    SUPPORT_CONFIG: 5,
    MIXED_CLI: 6,
    CLUSTER_SETUP: 7,
    LIVE_LOCAL: 8,
    LIVE_CLUSTER: 9,
}

MAKE_TARGET_SAFETY = {
    "indexes": (SAFE_LOCAL, "python"),
    "readiness": (SAFE_LOCAL, "python"),
    "compile": (SAFE_LOCAL, "python"),
    "test": (SAFE_LOCAL, "uv, pytest"),
    "check": (SAFE_LOCAL, "python, uv, pytest"),
    "paper-build": (SAFE_OPTIONAL_TOOL, "pdflatex, bibtex"),
    "paper-figures-autoresearch": (FIGURE_REGEN, "uv, checked-in AutoResearch evidence"),
}


@dataclass(frozen=True)
class CommandRecord:
    surface: str
    command: str
    source: str
    kind: str
    safety_class: str
    prerequisites: str
    summary: str
    default_safe: bool


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def python_docstring(path: Path) -> str:
    try:
        module = ast.parse(read_text(path))
    except SyntaxError:
        return ""
    doc = ast.get_docstring(module) or ""
    return re.sub(r"\s+", " ", doc).strip()


def shell_summary(path: Path) -> str:
    lines: list[str] = []
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("#!") or not stripped:
            continue
        if stripped.startswith("#SBATCH"):
            continue
        if stripped.startswith("#"):
            lines.append(stripped.lstrip("#").strip())
            continue
        break
    return " ".join(lines).strip()


def script_summary(path: Path) -> str:
    if path.suffix == ".py":
        return python_docstring(path) or "Python command entrypoint."
    if path.suffix in {".sh", ".sbatch"}:
        return shell_summary(path) or "Shell command entrypoint."
    return "Command entrypoint."


def parse_project_scripts(root: Path) -> list[tuple[str, str]]:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return []
    scripts: list[tuple[str, str]] = []
    in_section = False
    for line in read_text(pyproject).splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == "[project.scripts]"
            continue
        if not in_section or not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)\s*=\s*\"([^\"]+)\"", stripped)
        if match:
            scripts.append((match.group(1), match.group(2)))
    return scripts


def classify_script(rel: str, text: str) -> tuple[str, str]:
    path = Path(rel)
    name = path.name
    lower_name = name.lower()
    lower_text = text.lower()

    if name == "agent_index_config.py":
        return SUPPORT_CONFIG, "none"
    if name.startswith(("build_", "validate_")):
        return SAFE_LOCAL, "python"
    if name == "check_paper_build.py":
        return SAFE_OPTIONAL_TOOL, "pdflatex, bibtex"
    if name.startswith(("plot_", "reproduce_")):
        return FIGURE_REGEN, "checked-in evidence"
    if name.startswith(("analyze_", "compare_", "compute_")):
        return READ_ONLY_ANALYSIS, "checked-in evidence or existing runs"
    if name == "make_neurips2026_artifact.py":
        return ARTIFACT_BUILDER, "checked-in files, dist output review"
    if name.startswith("generate_autoresearch_campaign_tasks"):
        return CLUSTER_SETUP, "campaign config, output review"
    if name.startswith("bootstrap_"):
        return CLUSTER_SETUP, "cluster shell environment"
    if name.endswith((".sbatch", ".sh")) and (
        "sbatch" in lower_text or "slurm" in lower_name or "array_task" in lower_name
    ):
        return LIVE_CLUSTER, "Slurm, model access, compute allocation"
    if name.startswith("run_"):
        return LIVE_LOCAL, "model access, isolated worktree, output root"
    if "claude" in lower_text or "agent-workflow" in lower_text:
        return LIVE_LOCAL, "model access, isolated worktree"
    return READ_ONLY_ANALYSIS, "inspect script before running"


def script_records(root: Path) -> list[CommandRecord]:
    records: list[CommandRecord] = []
    for script_dir in SCRIPT_DIRS:
        parent = root / script_dir
        if not parent.exists():
            continue
        for path in sorted(parent.iterdir()):
            if not path.is_file() or path.name in SCRIPT_SUPPORT_FILES:
                continue
            rel = path.relative_to(root).as_posix()
            text = read_text(path)
            safety, prerequisites = classify_script(rel, text)
            records.append(
                CommandRecord(
                    surface=script_dir.as_posix(),
                    command=f"python {rel}" if path.suffix == ".py" else rel,
                    source=rel,
                    kind=path.suffix.lstrip(".") or "file",
                    safety_class=safety,
                    prerequisites=prerequisites,
                    summary=script_summary(path),
                    default_safe=safety in {SAFE_LOCAL, SAFE_OPTIONAL_TOOL, FIGURE_REGEN, READ_ONLY_ANALYSIS},
                )
            )
    return records


def make_records(root: Path) -> list[CommandRecord]:
    records: list[CommandRecord] = []
    for target in command_targets(root):
        safety, prerequisites = MAKE_TARGET_SAFETY.get(
            target.target,
            (READ_ONLY_ANALYSIS, "inspect Makefile target"),
        )
        records.append(
            CommandRecord(
                surface="Makefile",
                command=f"make {target.target}",
                source="Makefile",
                kind="make-target",
                safety_class=safety,
                prerequisites=prerequisites,
                summary=target.description,
                default_safe=safety in {SAFE_LOCAL, SAFE_OPTIONAL_TOOL, FIGURE_REGEN, READ_ONLY_ANALYSIS},
            )
        )
    return records


def project_script_records(root: Path) -> list[CommandRecord]:
    return [
        CommandRecord(
            surface="pyproject",
            command=f"uv run {name}",
            source="pyproject.toml",
            kind="console-script",
            safety_class=MIXED_CLI,
            prerequisites="subcommand-specific; run --help or doctor before live workflows",
            summary=f"Console entrypoint `{target}`.",
            default_safe=False,
        )
        for name, target in parse_project_scripts(root)
    ]


def build_manifest(root: Path) -> dict[str, object]:
    commands = make_records(root) + project_script_records(root) + script_records(root)
    commands = sorted(
        commands,
        key=lambda record: (
            SAFETY_ORDER.get(record.safety_class, 99),
            record.surface,
            record.command,
        ),
    )
    by_safety: dict[str, int] = {}
    by_surface: dict[str, int] = {}
    for command in commands:
        by_safety[command.safety_class] = by_safety.get(command.safety_class, 0) + 1
        by_surface[command.surface] = by_surface.get(command.surface, 0) + 1

    required_make = {f"make {target}" for target in REQUIRED_MAKE_TARGETS}
    found_make = {command.command for command in commands if command.surface == "Makefile"}
    return {
        "root": ".",
        "command_count": len(commands),
        "default_safe_count": sum(1 for command in commands if command.default_safe),
        "safety_classes": dict(sorted(by_safety.items())),
        "surfaces": dict(sorted(by_surface.items())),
        "missing_required_make_targets": sorted(required_make - found_make),
        "commands": [asdict(command) for command in commands],
    }


def table_escape(value: object) -> str:
    text = "" if value is None else str(value)
    if not text:
        return "-"
    return text.replace("|", "\\|").replace("\n", " ")


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(table_escape(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def render_markdown(manifest: dict[str, object]) -> str:
    commands = manifest["commands"]
    lines: list[str] = [
        "# Command Manifest",
        "",
        "Generated by `python scripts/build_command_manifest.py --output docs/audits/command-manifest.md`.",
        "This manifest classifies repository command entrypoints by safety so agents can prefer offline checks and avoid live, provider-backed, or cluster jobs unless explicitly requested.",
        "",
        "## Summary",
        "",
        f"- Commands indexed: `{manifest['command_count']}`",
        f"- Default-safe commands: `{manifest['default_safe_count']}`",
        f"- Missing required Make targets: `{len(manifest['missing_required_make_targets'])}`",
        "",
        "## Safety Classes",
        "",
        markdown_table(
            ["Safety Class", "Commands"],
            [[f"`{name}`", count] for name, count in manifest["safety_classes"].items()],
        ),
        "",
        "## Surfaces",
        "",
        markdown_table(
            ["Surface", "Commands"],
            [[f"`{name}`", count] for name, count in manifest["surfaces"].items()],
        ),
        "",
        "## Commands",
        "",
        markdown_table(
            [
                "Command",
                "Surface",
                "Safety",
                "Default Safe",
                "Prerequisites",
                "Summary",
            ],
            [
                [
                    f"`{command['command']}`",
                    command["surface"],
                    f"`{command['safety_class']}`",
                    "yes" if command["default_safe"] else "no",
                    command["prerequisites"],
                    command["summary"],
                ]
                for command in commands
            ],
        ),
        "",
        "## Policy",
        "",
        "- Default-safe commands may be run during local audits when their prerequisites are installed.",
        "- `mixed-cli`, `live-local`, `live-cluster`, and `cluster-setup` commands require explicit user intent and environment review.",
        "- Use `make check` as the default structural gate and `make paper-build` only when TeX Live is available.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument("--output", help="Write output to this file instead of stdout.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest = build_manifest(root)
    if args.format == "json":
        rendered = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_markdown(manifest)

    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
