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
    GENERATED_AUDITS,
    LOCAL_PATH_PATTERNS,
    MARKDOWN_LINK_DOCS,
    REQUIRED_MAKE_TARGETS,
)

FORMAL_LABEL_RE = re.compile(r"^(ass|def|lem|thm|prop|cor|rem|claim):")
PAPER_SOURCE_ALIASES = {
    "main.tex": [Path("paper/neurips-submission/main.tex")],
    "arxiv.tex": [Path("paper/neurips-submission/arxiv.tex")],
    "theory_anchor.tex": [Path("paper/neurips-submission/archive/theory_anchor.tex")],
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
            has_paper = any(path.startswith("paper/neurips-submission/figures/") for path in group)
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
    if len(modules) < 70:
        problems.append("knowledge index found fewer than 70 code modules")
    for module in modules:
        if not module["summary"] or module["summary"] == "Package marker or namespace module.":
            problems.append(f"code module lacks useful summary `{module['path']}`")
    return problems


def check_paper_figures(knowledge: dict) -> list[str]:
    problems: list[str] = []
    figures = knowledge.get("paper_figures", [])
    if len(figures) < 100:
        problems.append("knowledge index found fewer than 100 paper figures")
    exact_count = sum(1 for figure in figures if figure["provenance"] == "exact experiment copy")
    if exact_count < 25:
        problems.append("paper figure provenance found fewer than 25 exact experiment copies")
    for figure in figures:
        if figure["provenance"] in {"exact experiment copy", "same-name experiment artifact", "generated paper figure"}:
            if not figure["source"]:
                problems.append(f"paper figure lacks provenance source `{figure['path']}`")
    return problems


def check_active_paper_references(knowledge: dict) -> list[str]:
    problems: list[str] = []
    refs = knowledge.get("active_paper_references", [])
    if len(refs) < 15:
        problems.append("knowledge index found fewer than 15 active paper references")
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


def check_paper_archive_manifest(manifest: dict) -> list[str]:
    problems: list[str] = []
    coverage = manifest.get("policy_coverage", {})
    files = int(coverage.get("files", 0))
    classified = int(coverage.get("classified", 0))
    unclassified = coverage.get("unclassified", [])

    if manifest.get("archive_root") != "paper/neurips-submission/archive":
        problems.append("paper archive manifest has the wrong archive root")
    if files == 0:
        problems.append("paper archive manifest found no files")
    if classified != files:
        problems.append("paper archive manifest has unclassified files: " + ", ".join(unclassified))

    records = {record["path"]: record for record in manifest.get("files", [])}
    expected = {
        "paper/neurips-submission/archive/theory_anchor.tex": "canonical-anchor",
        "paper/neurips-submission/archive/next_steps.tex": "keep-independent",
        "paper/neurips-submission/archive/Beneventano_Poggio.tex": "keep-provenance",
    }
    for path, disposition in expected.items():
        record = records.get(path)
        if not record:
            problems.append(f"paper archive manifest is missing `{path}`")
            continue
        if record["disposition"] != disposition:
            problems.append(f"paper archive manifest has wrong disposition for `{path}`")

    for record in records.values():
        if record["suffix"] in {".tex", ".bib"} and not record["nearest_text_neighbor"]:
            problems.append(f"paper archive text source lacks nearest-neighbor similarity `{record['path']}`")
    return problems


def check_experiment_manifest(manifest: dict) -> list[str]:
    problems: list[str] = []
    bundles = manifest.get("bundles", [])
    if manifest.get("root") != ".":
        problems.append("experiment manifest root must be '.'")
    if len(bundles) < 20:
        problems.append("experiment manifest found fewer than 20 bundles")
    if manifest.get("missing_paths"):
        problems.append("experiment manifest has missing paths: " + ", ".join(manifest["missing_paths"]))
    if manifest.get("missing_readmes"):
        problems.append(
            "experiment manifest has missing README files: " + ", ".join(manifest["missing_readmes"])
        )

    class_counts = manifest.get("reproducibility_classes", {})
    if int(class_counts.get("paper-supporting-evidence", 0)) < 6:
        problems.append("experiment manifest found fewer than 6 paper-supporting bundles")

    for bundle in bundles:
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
    if len(commands) < 30:
        problems.append("command manifest found fewer than 30 commands")
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

    cli = by_command.get("uv run agent-workflow")
    if not cli:
        problems.append("command manifest missing `uv run agent-workflow`")
    elif cli["safety_class"] != "mixed-cli" or cli["default_safe"]:
        problems.append("command manifest must classify `uv run agent-workflow` as non-default mixed CLI")

    live_classes = {"live-local", "live-cluster", "cluster-setup", "mixed-cli"}
    if not any(command["safety_class"] == "live-cluster" for command in commands):
        problems.append("command manifest found no live-cluster commands")
    for command in commands:
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
        elif token.startswith(("paper/", "docs/", "experiments/", "scripts/", "src/", "autoresearch/")):
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

    knowledge = load_json(root, "scripts/build_knowledge_index.py")
    inventory = load_json(root, "scripts/build_repo_inventory.py")
    paper_archive = load_json(root, "scripts/build_paper_archive_manifest.py")
    experiment_manifest = load_json(root, "scripts/build_experiment_manifest.py")
    command_manifest = load_json(root, "scripts/build_command_manifest.py")
    archive_coverage = paper_archive["policy_coverage"]

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
    metrics["paper_archive_files"] = str(archive_coverage["files"])
    metrics["paper_archive_policy"] = f"{archive_coverage['classified']}/{archive_coverage['files']}"
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

    if len(knowledge["formal_objects"]) < 90:
        messages.append("knowledge index found fewer than 90 formal objects")
    if len(knowledge["experiment_bundles"]) < 20:
        messages.append("knowledge index found fewer than 20 experiment bundles")
    if len(knowledge["scripts"]) < 30:
        messages.append("knowledge index found fewer than 30 scripts")

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

    paper_archive_problems = check_paper_archive_manifest(paper_archive)
    messages.extend(paper_archive_problems)

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

    with tempfile.TemporaryDirectory(prefix="agent-readiness-") as tmp:
        tmp_path = Path(tmp)
        generated_knowledge = render_markdown(
            root,
            "scripts/build_knowledge_index.py",
            tmp_path / "knowledge-index.md",
        )
        generated_inventory = render_markdown(
            root,
            "scripts/build_repo_inventory.py",
            tmp_path / "repo-inventory.md",
        )
        generated_paper_archive = render_markdown(
            root,
            "scripts/build_paper_archive_manifest.py",
            tmp_path / "paper-archive-manifest.md",
        )
        generated_experiment_manifest = render_markdown(
            root,
            "scripts/build_experiment_manifest.py",
            tmp_path / "experiment-manifest.md",
        )
        generated_command_manifest = render_markdown(
            root,
            "scripts/build_command_manifest.py",
            tmp_path / "command-manifest.md",
        )

    if any(pattern in generated_knowledge for pattern in LOCAL_PATH_PATTERNS):
        messages.append("generated knowledge index contains a local path")
    if any(pattern in generated_inventory for pattern in LOCAL_PATH_PATTERNS):
        messages.append("generated repo inventory contains a local path")
    if any(pattern in generated_paper_archive for pattern in LOCAL_PATH_PATTERNS):
        messages.append("generated paper archive manifest contains a local path")
    if any(pattern in generated_experiment_manifest for pattern in LOCAL_PATH_PATTERNS):
        messages.append("generated experiment manifest contains a local path")
    if any(pattern in generated_command_manifest for pattern in LOCAL_PATH_PATTERNS):
        messages.append("generated command manifest contains a local path")

    if write:
        (root / GENERATED_AUDITS["knowledge"]).write_text(generated_knowledge, encoding="utf-8")
        (root / GENERATED_AUDITS["inventory"]).write_text(generated_inventory, encoding="utf-8")
        (root / GENERATED_AUDITS["paper_archive"]).write_text(
            generated_paper_archive,
            encoding="utf-8",
        )
        (root / GENERATED_AUDITS["experiment_manifest"]).write_text(
            generated_experiment_manifest,
            encoding="utf-8",
        )
        (root / GENERATED_AUDITS["command_manifest"]).write_text(
            generated_command_manifest,
            encoding="utf-8",
        )
    else:
        tracked_knowledge = (root / GENERATED_AUDITS["knowledge"]).read_text(encoding="utf-8")
        tracked_inventory = (root / GENERATED_AUDITS["inventory"]).read_text(encoding="utf-8")
        tracked_paper_archive = (root / GENERATED_AUDITS["paper_archive"]).read_text(
            encoding="utf-8"
        )
        tracked_experiment_manifest = (root / GENERATED_AUDITS["experiment_manifest"]).read_text(
            encoding="utf-8"
        )
        tracked_command_manifest = (root / GENERATED_AUDITS["command_manifest"]).read_text(
            encoding="utf-8"
        )
        if generated_knowledge != tracked_knowledge:
            messages.append(f"{GENERATED_AUDITS['knowledge']} is stale")
        if generated_inventory != tracked_inventory:
            messages.append(f"{GENERATED_AUDITS['inventory']} is stale")
        if generated_paper_archive != tracked_paper_archive:
            messages.append(f"{GENERATED_AUDITS['paper_archive']} is stale")
        if generated_experiment_manifest != tracked_experiment_manifest:
            messages.append(f"{GENERATED_AUDITS['experiment_manifest']} is stale")
        if generated_command_manifest != tracked_command_manifest:
            messages.append(f"{GENERATED_AUDITS['command_manifest']} is stale")

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
