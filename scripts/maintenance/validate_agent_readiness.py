"""Validate that the repository is ready for LLM-agent navigation."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

from agent_index_config import (
    AGENT_DOC_ROOT_FILES,
    CORE_EXPERIMENT_BUNDLES,
    CORE_CODE_MODULES,
    CANONICAL_TEX,
    GENERATED_AUDITS,
    LOCAL_PATH_PATTERNS,
    MARKDOWN_LINK_DOCS,
    REQUIRED_MAKE_TARGETS,
)

FORMAL_LABEL_RE = re.compile(r"^(ass|def|lem|thm|prop|cor|rem|claim):")
PAPER_SOURCE_ALIASES = {
    "main.tex": [Path("docs/paper/neurips-submission/main.tex")],
    "arxiv.tex": [Path("docs/paper/neurips-submission/arxiv.tex")],
    "theory_anchor.tex": [Path("docs/paper/neurips-submission/archive/theory_anchor.tex")],
}


def run_command(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def load_json(root: Path, script: str) -> dict:
    result = run_command(root, [script, "--format", "json"])
    return json.loads(result.stdout)


def render_markdown(root: Path, script: str, output: Path) -> str:
    run_command(root, [script, "--output", str(output)])
    return output.read_text(encoding="utf-8")


def iter_agent_facing_docs(root: Path) -> Iterable[Path]:
    for path in AGENT_DOC_ROOT_FILES:
        full = root / path
        if full.exists():
            yield full
    docs_root = root / "docs"
    if docs_root.exists():
        for path in sorted(docs_root.rglob("*.md")):
            rel_parts = path.relative_to(root).parts
            if "archive" not in rel_parts:
                yield path


def check_no_local_paths(root: Path) -> list[str]:
    offenders: list[str] = []
    for path in iter_agent_facing_docs(root):
        text = path.read_text(encoding="utf-8")
        if any(pattern in text for pattern in LOCAL_PATH_PATTERNS):
            offenders.append(path.relative_to(root).as_posix())
    return offenders


def check_markdown_links(root: Path) -> list[str]:
    missing: list[str] = []
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for rel_doc in MARKDOWN_LINK_DOCS:
        doc = root / rel_doc
        if not doc.exists():
            missing.append(rel_doc.as_posix())
            continue
        for target in pattern.findall(doc.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#") or target.startswith("mailto:"):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (doc.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{doc.relative_to(root).as_posix()} -> {target}")
    return missing


def check_unexpected_duplicates(inventory: dict) -> list[str]:
    problems: list[str] = []
    for group in inventory["duplicate_groups"]:
        suffixes = {Path(path).suffix for path in group}
        if ".md" in suffixes or ".tex" in suffixes:
            problems.append("unexpected document duplicate: " + ", ".join(group))
            continue
        if suffixes == {".py"} and not all(Path(path).name == "__init__.py" for path in group):
            problems.append("unexpected Python duplicate: " + ", ".join(group))
            continue
        if suffixes & {".pdf", ".png"}:
            has_paper = any(path.startswith("docs/paper/neurips-submission/figures/") for path in group)
            has_experiment = any(path.startswith("experiments/") for path in group)
            if not (has_paper and has_experiment):
                problems.append("unexpected figure/PDF duplicate: " + ", ".join(group))
    return problems


def check_script_summaries(knowledge: dict) -> list[str]:
    problems: list[str] = []
    for entry in knowledge["scripts"]:
        summary = entry["summary"]
        if summary == "No top-level summary found." or summary.startswith("SBATCH"):
            problems.append(entry["path"])
    return problems


def check_code_modules(knowledge: dict) -> list[str]:
    problems: list[str] = []
    modules = knowledge.get("code_modules", [])
    paths = {module["path"] for module in modules}
    for path in sorted(CORE_CODE_MODULES - paths):
        problems.append(f"knowledge index is missing core code module `{path}`")
    for module in modules:
        if not module["summary"] or module["summary"] == "Package marker or namespace module.":
            problems.append(f"code module lacks useful summary `{module['path']}`")
    return problems


def check_paper_figures(knowledge: dict) -> list[str]:
    problems: list[str] = []
    figures = knowledge.get("paper_figures", [])
    indexed_paths = {figure["path"] for figure in figures}
    for ref in knowledge.get("active_paper_references", []):
        if ref["kind"] == "figure" and ref["resolved_path"] not in indexed_paths:
            problems.append(f"active paper figure is not indexed `{ref['resolved_path']}`")
    for figure in figures:
        if figure["provenance"] in {"exact experiment copy", "same-name experiment artifact", "generated paper figure"}:
            if not figure["source"]:
                problems.append(f"paper figure lacks provenance source `{figure['path']}`")
    return problems


def check_active_paper_references(knowledge: dict) -> list[str]:
    problems: list[str] = []
    refs = knowledge.get("active_paper_references", [])
    for source in ("docs/paper/neurips-submission/main.tex", "docs/paper/neurips-submission/arxiv.tex"):
        if not any(ref["source_tex"] == source for ref in refs):
            problems.append(f"knowledge index found no references for `{source}`")
    missing = [
        f"{ref['source_tex']} -> {ref['target']}"
        for ref in refs
        if not ref["present"]
    ]
    if missing:
        problems.append("active paper references missing files: " + ", ".join(missing))
    main_figures = [
        ref for ref in refs
        if ref["source_tex"].endswith("main.tex") and ref["kind"] == "figure"
    ]
    if len(main_figures) < 5:
        problems.append("main.tex should reference at least 5 paper figures")
    return problems


def check_experiment_bundles(knowledge: dict) -> list[str]:
    problems: list[str] = []
    paths = {bundle["path"] for bundle in knowledge["experiment_bundles"]}
    for path in sorted(CORE_EXPERIMENT_BUNDLES - paths):
        problems.append(f"knowledge index is missing core experiment `{path}`")
    for bundle in knowledge["experiment_bundles"]:
        if not bundle["readme_title"]:
            problems.append(f"experiment bundle lacks README title `{bundle['path']}`")
        if "completed" in bundle["status"] and bundle["evidence_tier"] == "not tiered":
            problems.append(f"completed experiment bundle lacks evidence tier `{bundle['path']}`")
    return problems


def check_command_targets(knowledge: dict) -> list[str]:
    problems: list[str] = []
    targets = {target["target"]: target for target in knowledge.get("command_targets", [])}
    missing = [target for target in REQUIRED_MAKE_TARGETS if target not in targets]
    if missing:
        problems.append("missing required Makefile targets: " + ", ".join(missing))
        return problems

    check_deps = set(targets["check"]["dependencies"].split())
    expected_deps = {"indexes", "readiness", "compile", "test"}
    if check_deps != expected_deps:
        problems.append("Makefile target `check` must depend on indexes, readiness, compile, and test")

    for target in REQUIRED_MAKE_TARGETS:
        if not targets[target]["description"] or targets[target]["description"] == "Repository command target.":
            problems.append(f"Makefile target lacks useful description `{target}`")
    return problems


def check_experiment_manifest(manifest: dict) -> list[str]:
    problems: list[str] = []
    bundles = manifest.get("bundles", [])
    if manifest.get("root") != ".":
        problems.append("experiment manifest root must be '.'")
    paths = {bundle["path"] for bundle in bundles}
    for path in sorted(CORE_EXPERIMENT_BUNDLES - paths):
        problems.append(f"experiment manifest is missing core experiment `{path}`")
    if manifest.get("missing_paths"):
        problems.append("experiment manifest has missing paths: " + ", ".join(manifest["missing_paths"]))
    if manifest.get("missing_readmes"):
        problems.append(
            "experiment manifest has missing README files: " + ", ".join(manifest["missing_readmes"])
        )

    for bundle in bundles:
        if bundle["path"] in CORE_EXPERIMENT_BUNDLES:
            if bundle["reproducibility_class"] not in {"paper-supporting-evidence", "partial-evidence"}:
                problems.append(f"core experiment lacks an evidence classification `{bundle['path']}`")
            if bundle.get("result_files", 0) + bundle.get("figure_files", 0) == 0:
                problems.append(f"core experiment lacks recorded evidence `{bundle['path']}`")
        if not bundle["readme_title"]:
            problems.append(f"experiment manifest bundle lacks README title `{bundle['path']}`")
        if not bundle["reproducibility_class"]:
            problems.append(f"experiment manifest bundle lacks reproducibility class `{bundle['path']}`")
        if "completed" in bundle["status"].lower():
            result_assets = int(bundle["result_files"]) + int(bundle["figure_files"])
            if result_assets == 0:
                problems.append(f"completed experiment bundle lacks result assets `{bundle['path']}`")
    return problems


def check_command_manifest(manifest: dict) -> list[str]:
    problems: list[str] = []
    commands = manifest.get("commands", [])
    by_command = {command["command"]: command for command in commands}

    if manifest.get("root") != ".":
        problems.append("command manifest root must be '.'")
    if manifest.get("missing_required_make_targets"):
        problems.append(
            "command manifest is missing required Make targets: "
            + ", ".join(manifest["missing_required_make_targets"])
        )

    for required in ("make check", "make indexes", "make paper-build"):
        if required not in by_command:
            problems.append(f"command manifest missing `{required}`")

    make_check = by_command.get("make check")
    if make_check and (make_check["safety_class"] != "safe-local" or not make_check["default_safe"]):
        problems.append("command manifest must classify `make check` as default-safe local")

    live_classes = {"live-local", "live-cluster", "cluster-setup", "mixed-cli"}
    for command in commands:
        if command.get("kind") == "console-script" and (
            command["safety_class"] != "mixed-cli" or command["default_safe"]
        ):
            problems.append(f"console command must be non-default mixed CLI `{command['command']}`")
        if not command["summary"]:
            problems.append(f"command manifest command lacks summary `{command['command']}`")
        if command["safety_class"] in live_classes and command["default_safe"]:
            problems.append(f"live command incorrectly marked default-safe `{command['command']}`")
    return problems


def check_paper_evidence_map(root: Path, knowledge: dict) -> list[str]:
    problems: list[str] = []
    map_path = root / "docs" / "paper-evidence-map.md"
    if not map_path.exists():
        return ["docs/paper-evidence-map.md is missing"]

    labels = {obj["label"] for obj in knowledge["formal_objects"] if obj.get("label")}
    text = map_path.read_text(encoding="utf-8")
    tokens = sorted(set(re.findall(r"`([^`]+)`", text)))

    for token in tokens:
        if FORMAL_LABEL_RE.match(token):
            if token not in labels:
                problems.append(f"paper evidence map references missing formal label `{token}`")
            continue

        candidate_paths: list[Path] = []
        if token in PAPER_SOURCE_ALIASES:
            candidate_paths = PAPER_SOURCE_ALIASES[token]
        elif token.startswith(("docs/", "experiments/", "scripts/", "src/")):
            candidate_paths = [Path(token.rstrip("/"))]

        for rel_path in candidate_paths:
            full_path = root / rel_path
            if not full_path.exists():
                problems.append(f"paper evidence map references missing path `{rel_path.as_posix()}`")
                continue
            if rel_path.parts and rel_path.parts[0] == "experiments" and full_path.is_dir():
                readme = full_path / "README.md"
                if not readme.exists():
                    problems.append(
                        f"experiment path in paper evidence map lacks README `{rel_path.as_posix()}/README.md`"
                    )

    return problems


def validate(root: Path, write: bool = False) -> tuple[bool, list[str], dict[str, str]]:
    root = root.resolve()
    messages: list[str] = []
    metrics: dict[str, str] = {}

    knowledge = load_json(root, "scripts/maintenance/build_knowledge_index.py")
    inventory = load_json(root, "scripts/maintenance/build_repo_inventory.py")
    experiment_manifest = load_json(root, "scripts/maintenance/build_experiment_manifest.py")
    command_manifest = load_json(root, "scripts/maintenance/build_command_manifest.py")

    metrics["canonical_docs"] = f"{sum(knowledge['canonical_docs'].values())}/{len(knowledge['canonical_docs'])}"
    metrics["formal_objects"] = str(len(knowledge["formal_objects"]))
    metrics["experiment_bundles"] = str(len(knowledge["experiment_bundles"]))
    metrics["script_entrypoints"] = str(len(knowledge["scripts"]))
    metrics["code_modules"] = str(len(knowledge.get("code_modules", [])))
    metrics["paper_figures"] = str(len(knowledge.get("paper_figures", [])))
    metrics["active_paper_references"] = str(len(knowledge.get("active_paper_references", [])))
    metrics["command_targets"] = str(len(knowledge.get("command_targets", [])))
    metrics["inventory_files"] = str(inventory["total_files"])
    metrics["duplicate_groups"] = str(len(inventory["duplicate_groups"]))
    metrics["experiment_manifest_bundles"] = str(experiment_manifest["bundle_count"])
    metrics["paper_supporting_experiments"] = str(
        experiment_manifest["reproducibility_classes"].get("paper-supporting-evidence", 0)
    )
    metrics["command_manifest_commands"] = str(command_manifest["command_count"])
    metrics["command_manifest_default_safe"] = str(command_manifest["default_safe_count"])

    if knowledge.get("root") != ".":
        messages.append("knowledge index root must be '.'")
    if inventory.get("root") != ".":
        messages.append("inventory root must be '.'")

    missing_canonical = [path for path, present in knowledge["canonical_docs"].items() if not present]
    if missing_canonical:
        messages.append("missing canonical docs: " + ", ".join(missing_canonical))

    missing_entrypoints = [path for path, present in inventory["entrypoints"].items() if not present]
    if missing_entrypoints:
        messages.append("missing inventory entrypoints: " + ", ".join(missing_entrypoints))

    missing_paper = [path for path, present in inventory["paper_sources"].items() if not present]
    if missing_paper:
        messages.append("missing paper sources: " + ", ".join(missing_paper))

    formal_sources = {obj["path"] for obj in knowledge["formal_objects"]}
    for source in CANONICAL_TEX:
        if source.as_posix() not in formal_sources:
            messages.append(f"knowledge index found no formal objects in `{source}`")

    script_summary_problems = check_script_summaries(knowledge)
    if script_summary_problems:
        messages.append("scripts without useful summaries: " + ", ".join(script_summary_problems))

    code_module_problems = check_code_modules(knowledge)
    messages.extend(code_module_problems)

    paper_figure_problems = check_paper_figures(knowledge)
    messages.extend(paper_figure_problems)

    active_paper_reference_problems = check_active_paper_references(knowledge)
    messages.extend(active_paper_reference_problems)

    experiment_bundle_problems = check_experiment_bundles(knowledge)
    messages.extend(experiment_bundle_problems)

    command_target_problems = check_command_targets(knowledge)
    messages.extend(command_target_problems)

    experiment_manifest_problems = check_experiment_manifest(experiment_manifest)
    messages.extend(experiment_manifest_problems)

    command_manifest_problems = check_command_manifest(command_manifest)
    messages.extend(command_manifest_problems)

    evidence_map_problems = check_paper_evidence_map(root, knowledge)
    messages.extend(evidence_map_problems)

    duplicate_problems = check_unexpected_duplicates(inventory)
    messages.extend(duplicate_problems)

    local_path_docs = check_no_local_paths(root)
    if local_path_docs:
        messages.append("agent-facing docs contain local user paths: " + ", ".join(local_path_docs))

    missing_links = check_markdown_links(root)
    if missing_links:
        messages.append("missing markdown links: " + ", ".join(missing_links))

    generators = {
        "knowledge": "scripts/maintenance/build_knowledge_index.py",
        "inventory": "scripts/maintenance/build_repo_inventory.py",
        "experiment_manifest": "scripts/maintenance/build_experiment_manifest.py",
        "command_manifest": "scripts/maintenance/build_command_manifest.py",
    }
    with tempfile.TemporaryDirectory(prefix="agent-readiness-") as tmp:
        for key, script in generators.items():
            target = GENERATED_AUDITS[key]
            generated = render_markdown(root, script, Path(tmp) / target.name)
            if any(pattern in generated for pattern in LOCAL_PATH_PATTERNS):
                messages.append(f"{target} contains a local path")
            tracked = root / target
            if write:
                tracked.write_text(generated, encoding="utf-8")
            elif generated != tracked.read_text(encoding="utf-8"):
                messages.append(f"{target} is stale")

    return not messages, messages, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate tracked audit markdowns instead of failing if they are stale.",
    )
    args = parser.parse_args()

    ok, messages, metrics = validate(Path(args.root), write=args.write)
    print("Agent readiness metrics:")
    for key in sorted(metrics):
        print(f"  {key}: {metrics[key]}")

    if ok:
        print("Agent readiness: ok")
        return 0

    print("Agent readiness: failed", file=sys.stderr)
    for message in messages:
        print(f"- {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
