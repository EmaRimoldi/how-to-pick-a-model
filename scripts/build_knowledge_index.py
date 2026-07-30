"""Build a compact knowledge index for LLM agents working in this repository."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from agent_index_config import (
    CANONICAL_DOCS,
    CANONICAL_TEX,
    PAPER_ROOT,
    REQUIRED_MAKE_TARGETS,
    SCRIPT_DIRS,
    SCRIPT_SUPPORT_FILES,
)

FORMAL_ENVS = (
    "assumption",
    "definition",
    "theorem",
    "lemma",
    "proposition",
    "corollary",
    "claim",
    "remark",
)


@dataclass(frozen=True)
class TexSource:
    path: str
    role: str
    lines: int
    formal_objects: int
    canonical: bool


@dataclass(frozen=True)
class FormalObject:
    path: str
    line: int
    kind: str
    title: str
    label: str
    snippet: str


@dataclass(frozen=True)
class ExperimentBundle:
    benchmark: str
    path: str
    status: str
    evidence_tier: str
    evidence: str
    readme_title: str


@dataclass(frozen=True)
class ScriptEntry:
    path: str
    kind: str
    summary: str


@dataclass(frozen=True)
class CommandTarget:
    target: str
    dependencies: str
    description: str
    commands: int
    required: bool


@dataclass(frozen=True)
class CodeModule:
    path: str
    surface: str
    summary: str
    public_symbols: str


@dataclass(frozen=True)
class PaperFigure:
    path: str
    collection: str
    format: str
    provenance: str
    source: str


@dataclass(frozen=True)
class ActivePaperReference:
    source_tex: str
    kind: str
    target: str
    resolved_path: str
    present: bool


MAKE_TARGET_DESCRIPTIONS = {
    "indexes": "Regenerate the agent-facing repository inventory, knowledge index, and manifests.",
    "readiness": "Validate canonical docs, evidence links, duplicate policy, and generated audit freshness.",
    "compile": "Byte-compile scripts, src, and autoresearch for syntax/import-surface sanity.",
    "test": "Run the repository test suite through uv.",
    "check": "Run indexes, readiness, compile, and tests as the full local gate.",
    "paper-build": "Compile active paper TeX sources out of tree with pdflatex and bibtex.",
    "paper-figures-autoresearch": "Regenerate compact paper-facing AutoResearch figures from processed evidence.",
}

CODE_MODULE_SCOPES = (
    ("model-routing root modules", Path("src"), 1),
    ("agent-workflow runtime", Path("src/agent_workflow"), 2),
    ("verified orchestration runtime", Path("src/vao"), 2),
    ("autoresearch analysis", Path("autoresearch/analysis"), 1),
    ("autoresearch benchmark", Path("autoresearch/benchmark/cifar10"), 1),
    ("autoresearch root helpers", Path("autoresearch"), 1),
)
CODE_MODULE_EXCLUDED_PARTS = {
    "__pycache__",
    "legacy",
    "scripts",
}
PAPER_FIGURE_ROOT = Path("paper/neurips-submission/figures")
PAPER_FIGURE_SUFFIXES = {".pdf", ".png"}
FIGURE_GENERATOR_HINTS = {
    "candidates": "src/plot_humaneval_candidates.py",
    "humaneval": "src/plot_humaneval_paper.py",
    "strategy_routing": "src/plot_strategy_results.py",
    "autoresearch": "autoresearch/scripts",
    "autoresearch_n20_confirmation": "autoresearch/scripts/reproduce_appendix_figures_n20_confirmation.py",
}
ACTIVE_PAPER_TEX = (
    Path("paper/neurips-submission/arxiv.tex"),
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def clean_latex(text: str, limit: int = 220) -> str:
    text = re.sub(r"%.*", " ", text)
    text = re.sub(r"\\label\{[^}]*\}", " ", text)
    text = re.sub(r"\\(begin|end)\{[^}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = text.replace("$", " ")
    text = text.replace("{", " ").replace("}", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def tex_role(path: Path) -> str:
    rel = path.as_posix()
    if rel.endswith("arxiv.tex"):
        return "active AutoResearch manuscript anchor"
    if rel.endswith("theory_anchor.tex"):
        return "maximal validated theory anchor"
    if "/archive/" in rel:
        return "archived draft or provenance source"
    if rel.endswith("piers_macro.tex"):
        return "macro file"
    return "paper source"


def parse_formal_objects(root: Path, path: Path) -> list[FormalObject]:
    full = root / path
    if not full.exists():
        return []
    text = read_text(full)
    env_group = "|".join(FORMAL_ENVS)
    begin_re = re.compile(
        rf"\\begin\{{(?P<kind>{env_group})\}}(?:\[(?P<title>[^\]]*)\])?",
        re.IGNORECASE,
    )
    objects: list[FormalObject] = []
    for match in begin_re.finditer(text):
        kind = match.group("kind").lower()
        end_re = re.compile(rf"\\end\{{{re.escape(kind)}\}}", re.IGNORECASE)
        end = end_re.search(text, match.end())
        body = text[match.end() : end.start() if end else min(len(text), match.end() + 1200)]
        label_match = re.search(r"\\label\{([^}]*)\}", body)
        title = (match.group("title") or "").strip()
        objects.append(
            FormalObject(
                path=path.as_posix(),
                line=line_number(text, match.start()),
                kind=kind,
                title=clean_latex(title, 90),
                label=label_match.group(1).strip() if label_match else "",
                snippet=clean_latex(body),
            )
        )
    return objects


def tex_sources(root: Path) -> tuple[list[TexSource], list[FormalObject]]:
    paths = sorted((root / PAPER_ROOT).rglob("*.tex"))
    formal_by_path: dict[str, list[FormalObject]] = {}
    all_objects: list[FormalObject] = []
    sources: list[TexSource] = []
    canonical_set = {p.as_posix() for p in CANONICAL_TEX}

    for full_path in paths:
        rel = full_path.relative_to(root)
        objects = parse_formal_objects(root, rel)
        formal_by_path[rel.as_posix()] = objects
        if rel.as_posix() in canonical_set:
            all_objects.extend(objects)
        sources.append(
            TexSource(
                path=rel.as_posix(),
                role=tex_role(rel),
                lines=len(read_text(full_path).splitlines()),
                formal_objects=len(objects),
                canonical=rel.as_posix() in canonical_set,
            )
        )
    return sources, all_objects


def markdown_heading(path: Path) -> str:
    if not path.exists():
        return ""
    for line in read_text(path).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def parse_evidence_tiers(root: Path) -> dict[str, str]:
    path = root / "docs" / "paper-evidence-map.md"
    if not path.exists():
        return {}

    tiers: dict[str, str] = {}
    current_tier = ""
    for line in read_text(path).splitlines():
        if line.startswith("### Tier "):
            current_tier = line.lstrip("# ").strip()
            continue
        if not current_tier or not line.startswith("- `experiments/"):
            continue
        match = re.search(r"`(experiments/[^`]+)`", line)
        if match:
            tiers[match.group(1).rstrip("/") + "/"] = current_tier
    return tiers


def parse_experiment_table(root: Path) -> list[ExperimentBundle]:
    path = root / "experiments" / "README.md"
    if not path.exists():
        return []
    bundles: list[ExperimentBundle] = []
    evidence_tiers = parse_evidence_tiers(root)
    link_re = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")
    for line in read_text(path).splitlines():
        if not line.startswith("|") or "---" in line or "Experiment bundle" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        link = link_re.search(cells[1])
        if not link:
            continue
        rel = (Path("experiments") / link.group(2)).as_posix().rstrip("/") + "/"
        bundles.append(
            ExperimentBundle(
                benchmark=cells[0],
                path=rel,
                status=cells[2],
                evidence_tier=evidence_tiers.get(rel, "not tiered"),
                evidence=re.sub(r"\s+", " ", cells[3]),
                readme_title=markdown_heading(root / rel / "README.md"),
            )
        )
    return bundles


def iter_script_paths(root: Path) -> Iterable[Path]:
    for script_dir in SCRIPT_DIRS:
        parent = root / script_dir
        if not parent.exists():
            continue
        for path in sorted(parent.iterdir()):
            if path.is_file() and path.name not in SCRIPT_SUPPORT_FILES:
                yield path


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


def public_symbols(path: Path) -> list[str]:
    try:
        module = ast.parse(read_text(path))
    except SyntaxError:
        return []
    symbols: list[str] = []
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            symbols.append(node.name)
    return symbols[:8]


def module_summary(path: Path) -> str:
    try:
        module = ast.parse(read_text(path))
    except SyntaxError:
        return "SyntaxError while parsing module."
    doc = ast.get_docstring(module)
    if doc:
        return re.sub(r"\s+", " ", doc).strip()
    symbols = public_symbols(path)
    if symbols:
        return "Exports: " + ", ".join(symbols)
    return "Package marker or namespace module."


def script_entries(root: Path) -> list[ScriptEntry]:
    entries: list[ScriptEntry] = []
    for path in iter_script_paths(root):
        rel = path.relative_to(root).as_posix()
        if path.suffix == ".py":
            summary = python_docstring(path)
            kind = "python"
        elif path.suffix in {".sh", ".sbatch"}:
            summary = shell_summary(path)
            kind = "shell"
        else:
            summary = ""
            kind = path.suffix.lstrip(".") or "file"
        entries.append(
            ScriptEntry(
                path=rel,
                kind=kind,
                summary=summary or "No top-level summary found.",
            )
        )
    return entries


def code_surface(path: Path) -> str:
    for name, base, max_depth in CODE_MODULE_SCOPES:
        try:
            rel = path.relative_to(base)
        except ValueError:
            continue
        if len(rel.parts) <= max_depth:
            return name
    return "code module"


def iter_code_module_paths(root: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    for _, base, max_depth in CODE_MODULE_SCOPES:
        parent = root / base
        if not parent.exists():
            continue
        for path in sorted(parent.rglob("*.py")):
            rel_from_base = path.relative_to(parent)
            if len(rel_from_base.parts) > max_depth:
                continue
            rel = path.relative_to(root)
            if path.name == "__init__.py" or any(part in CODE_MODULE_EXCLUDED_PARTS for part in rel.parts):
                continue
            if rel in seen:
                continue
            seen.add(rel)
            yield path


def code_modules(root: Path) -> list[CodeModule]:
    modules: list[CodeModule] = []
    for path in iter_code_module_paths(root):
        rel = path.relative_to(root)
        symbols = public_symbols(path)
        modules.append(
            CodeModule(
                path=rel.as_posix(),
                surface=code_surface(rel),
                summary=module_summary(path),
                public_symbols=", ".join(symbols),
            )
        )
    return modules


def paper_figure_files(root: Path) -> list[Path]:
    base = root / PAPER_FIGURE_ROOT
    if not base.exists():
        return []
    return sorted(
        path
        for path in base.rglob("*")
        if path.is_file() and path.suffix.lower() in PAPER_FIGURE_SUFFIXES
    )


def experiment_figure_files(root: Path) -> list[Path]:
    base = root / "experiments"
    if not base.exists():
        return []
    return sorted(
        path
        for path in base.rglob("*")
        if path.is_file() and path.suffix.lower() in PAPER_FIGURE_SUFFIXES
    )


def paper_figures(root: Path) -> list[PaperFigure]:
    experiment_by_hash: dict[str, list[Path]] = {}
    experiment_by_name: dict[tuple[str, str], list[Path]] = {}
    for path in experiment_figure_files(root):
        experiment_by_hash.setdefault(sha256(path), []).append(path)
        experiment_by_name.setdefault((path.name, path.suffix.lower()), []).append(path)

    figures: list[PaperFigure] = []
    for path in paper_figure_files(root):
        rel = path.relative_to(root)
        collection = path.relative_to(root / PAPER_FIGURE_ROOT).parts[0]
        exact_matches = experiment_by_hash.get(sha256(path), [])
        same_name_matches = experiment_by_name.get((path.name, path.suffix.lower()), [])
        if exact_matches:
            provenance = "exact experiment copy"
            source = exact_matches[0].relative_to(root).as_posix()
        elif same_name_matches:
            provenance = "same-name experiment artifact"
            source = same_name_matches[0].relative_to(root).as_posix()
        elif collection in FIGURE_GENERATOR_HINTS:
            provenance = "generated paper figure"
            source = FIGURE_GENERATOR_HINTS[collection]
        else:
            provenance = "paper-only asset"
            source = ""
        figures.append(
            PaperFigure(
                path=rel.as_posix(),
                collection=collection,
                format=path.suffix.lower().lstrip("."),
                provenance=provenance,
                source=source,
            )
        )
    return figures


def resolve_latex_target(root: Path, source_tex: Path, kind: str, target: str) -> Path:
    source_dir = (root / source_tex).parent
    if kind == "bibliography":
        candidate = Path(target)
        if candidate.suffix:
            return source_dir / candidate
        return source_dir / f"{target}.bib"
    candidate = Path(target)
    if candidate.suffix:
        return source_dir / candidate
    for suffix in (".tex", ".pdf", ".png"):
        with_suffix = source_dir / f"{target}{suffix}"
        if with_suffix.exists():
            return with_suffix
    return source_dir / candidate


def active_paper_references(root: Path) -> list[ActivePaperReference]:
    refs: list[ActivePaperReference] = []
    patterns = [
        ("figure", re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}")),
        ("input", re.compile(r"\\(?:input|include)\{([^}]*)\}")),
        ("bibliography", re.compile(r"\\(?:bibliography|addbibresource)\{([^}]*)\}")),
    ]
    for source_tex in ACTIVE_PAPER_TEX:
        full_source = root / source_tex
        if not full_source.exists():
            continue
        text = read_text(full_source)
        for kind, pattern in patterns:
            for match in pattern.finditer(text):
                targets = [part.strip() for part in match.group(1).split(",") if part.strip()]
                for target in targets:
                    resolved = resolve_latex_target(root, source_tex, kind, target)
                    refs.append(
                        ActivePaperReference(
                            source_tex=source_tex.as_posix(),
                            kind=kind,
                            target=target,
                            resolved_path=resolved.relative_to(root).as_posix(),
                            present=resolved.exists(),
                        )
                    )
    return refs


def command_targets(root: Path) -> list[CommandTarget]:
    makefile = root / "Makefile"
    if not makefile.exists():
        return []

    parsed: dict[str, dict[str, object]] = {}
    current: str | None = None
    target_re = re.compile(r"^(?P<target>[A-Za-z0-9_.-]+):(?P<deps>.*)$")
    for line in read_text(makefile).splitlines():
        match = target_re.match(line)
        if match:
            current = match.group("target")
            if current.startswith("."):
                current = None
                continue
            parsed[current] = {
                "dependencies": " ".join(match.group("deps").split()),
                "commands": 0,
            }
            continue
        if current and line.startswith("\t"):
            parsed[current]["commands"] = int(parsed[current]["commands"]) + 1

    required_order = {target: index for index, target in enumerate(REQUIRED_MAKE_TARGETS)}
    return [
        CommandTarget(
            target=target,
            dependencies=str(meta["dependencies"]),
            description=MAKE_TARGET_DESCRIPTIONS.get(target, "Repository command target."),
            commands=int(meta["commands"]),
            required=target in required_order,
        )
        for target, meta in sorted(parsed.items(), key=lambda item: (required_order.get(item[0], 999), item[0]))
    ]


def build_index(root: Path) -> dict:
    sources, formal_objects = tex_sources(root)
    return {
        "root": ".",
        "canonical_docs": {
            path: (root / path).exists()
            for path in CANONICAL_DOCS
        },
        "tex_sources": [asdict(source) for source in sources],
        "formal_objects": [asdict(obj) for obj in formal_objects],
        "experiment_bundles": [asdict(bundle) for bundle in parse_experiment_table(root)],
        "scripts": [asdict(entry) for entry in script_entries(root)],
        "code_modules": [asdict(module) for module in code_modules(root)],
        "paper_figures": [asdict(figure) for figure in paper_figures(root)],
        "active_paper_references": [asdict(ref) for ref in active_paper_references(root)],
        "command_targets": [asdict(target) for target in command_targets(root)],
    }


def esc(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(esc(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def render_markdown(index: dict) -> str:
    formal_objects = index["formal_objects"]
    experiments = index["experiment_bundles"]
    scripts = index["scripts"]
    modules = index["code_modules"]
    figures = index["paper_figures"]
    active_refs = index["active_paper_references"]
    targets = index["command_targets"]
    lines: list[str] = [
        "# Knowledge Index",
        "",
        "Generated by `python scripts/build_knowledge_index.py --output docs/audits/knowledge-index.md`.",
        "This is a compact retrieval map for LLM agents. It complements the human-oriented `docs/knowledge-map.md`.",
        "",
        "## Summary",
        "",
        f"- Canonical docs present: `{sum(index['canonical_docs'].values())}/{len(index['canonical_docs'])}`",
        f"- Paper TeX sources indexed: `{len(index['tex_sources'])}`",
        f"- Formal objects in canonical TeX anchors: `{len(formal_objects)}`",
        f"- Experiment bundles indexed: `{len(experiments)}`",
        f"- Script entrypoints indexed: `{len(scripts)}`",
        f"- Code modules indexed: `{len(modules)}`",
        f"- Paper figures indexed: `{len(figures)}`",
        f"- Active paper references indexed: `{len(active_refs)}`",
        f"- Command targets indexed: `{len(targets)}`",
        "",
        "## Canonical Docs",
        "",
        table(
            ["Path", "Present"],
            [[f"`{path}`", "yes" if present else "missing"] for path, present in index["canonical_docs"].items()],
        ),
        "",
        "## Paper Source Map",
        "",
        table(
            ["Path", "Role", "Lines", "Formal Objects", "Canonical"],
            [
                [
                    f"`{source['path']}`",
                    source["role"],
                    str(source["lines"]),
                    str(source["formal_objects"]),
                    "yes" if source["canonical"] else "archive",
                ]
                for source in index["tex_sources"]
            ],
        ),
        "",
        "## Formal Objects In Canonical Anchors",
        "",
    ]
    if formal_objects:
        lines.append(
            table(
                ["File:Line", "Kind", "Label", "Title", "Snippet"],
                [
                    [
                        f"`{obj['path']}:{obj['line']}`",
                        obj["kind"],
                        f"`{obj['label']}`" if obj["label"] else "",
                        obj["title"],
                        obj["snippet"],
                    ]
                    for obj in formal_objects
                ],
            )
        )
    else:
        lines.append("No formal objects found in canonical anchors.")

    lines.extend(["", "## Experiment Bundles", ""])
    lines.append(
        table(
            ["Benchmark", "Path", "Status", "Evidence Tier", "Evidence"],
            [
                [
                    bundle["benchmark"],
                    f"`{bundle['path']}`",
                    bundle["status"],
                    bundle["evidence_tier"],
                    bundle["evidence"],
                ]
                for bundle in experiments
            ],
        )
    )

    lines.extend(["", "## Script Entrypoints", ""])
    lines.append(
        table(
            ["Path", "Kind", "Summary"],
            [
                [f"`{entry['path']}`", entry["kind"], entry["summary"]]
                for entry in scripts
            ],
        )
    )

    lines.extend(["", "## Code Modules", ""])
    lines.append(
        table(
            ["Surface", "Path", "Summary", "Public Symbols"],
            [
                [
                    module["surface"],
                    f"`{module['path']}`",
                    module["summary"],
                    module["public_symbols"],
                ]
                for module in modules
            ],
        )
    )

    lines.extend(["", "## Paper Figure Provenance", ""])
    lines.append(
        table(
            ["Collection", "Path", "Format", "Provenance", "Source"],
            [
                [
                    figure["collection"],
                    f"`{figure['path']}`",
                    figure["format"],
                    figure["provenance"],
                    f"`{figure['source']}`" if figure["source"] else "",
                ]
                for figure in figures
            ],
        )
    )

    lines.extend(["", "## Active Paper References", ""])
    lines.append(
        table(
            ["Source TeX", "Kind", "Target", "Resolved Path", "Present"],
            [
                [
                    f"`{ref['source_tex']}`",
                    ref["kind"],
                    f"`{ref['target']}`",
                    f"`{ref['resolved_path']}`",
                    "yes" if ref["present"] else "missing",
                ]
                for ref in active_refs
            ],
        )
    )

    lines.extend(["", "## Command Targets", ""])
    lines.append(
        table(
            ["Target", "Dependencies", "Description", "Commands", "Required"],
            [
                [
                    f"`make {target['target']}`",
                    target["dependencies"] or "",
                    target["description"],
                    str(target["commands"]),
                    "yes" if target["required"] else "no",
                ]
                for target in targets
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Agent Use",
            "",
            "- Use this file to locate relevant material quickly; use the source file for final claims.",
            "- If a formal object appears in an archived source but not in a canonical anchor, consult `docs/audits/theory-consolidation.md` before promoting it.",
            "- If an experiment status is partial or scaffold, do not cite it as completed evidence without checking its bundle README.",
            "- Use `make check` as the default local gate after structural, documentation, or code changes.",
            "- Regenerate this file after adding, moving, or deleting paper sources, experiment bundles, scripts, or command targets.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Write output to this file instead of stdout.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    index = build_index(root)
    rendered = (
        json.dumps(index, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else render_markdown(index)
    )

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
