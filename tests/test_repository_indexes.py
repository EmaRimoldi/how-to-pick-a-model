from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.agent_index_config import (
    AGENT_DOC_ROOT_FILES,
    GENERATED_AUDITS,
    LOCAL_PATH_PATTERNS,
    REQUIRED_MAKE_TARGETS,
)


ROOT = Path(__file__).resolve().parents[1]


def _run_json(script: str) -> dict:
    result = subprocess.run(
        [sys.executable, script, "--format", "json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _render_markdown(script: str, output: Path) -> str:
    subprocess.run(
        [sys.executable, script, "--output", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return output.read_text(encoding="utf-8")


def test_knowledge_index_is_complete_and_descriptive() -> None:
    index = _run_json("scripts/build_knowledge_index.py")

    assert index["root"] == "."
    assert all(index["canonical_docs"].values())
    assert len(index["formal_objects"]) >= 90
    assert len(index["experiment_bundles"]) >= 20
    assert len(index["scripts"]) >= 30
    assert len(index["code_modules"]) >= 70
    assert len(index["paper_figures"]) >= 100
    assert len(index["active_paper_references"]) >= 15
    assert all("agent_index_config.py" not in entry["path"] for entry in index["scripts"])
    assert any(entry["path"] == "scripts/build_command_manifest.py" for entry in index["scripts"])
    assert any(entry["path"] == "scripts/build_experiment_manifest.py" for entry in index["scripts"])
    assert any(entry["path"] == "scripts/build_paper_archive_manifest.py" for entry in index["scripts"])

    module_paths = {module["path"] for module in index["code_modules"]}
    for expected in (
        "src/agent_workflow/cli.py",
        "src/agent_workflow/communication/blackboard.py",
        "src/vao/schemas.py",
        "src/load_traces.py",
        "autoresearch/analysis/autoresearch_cifar10_model_routing.py",
        "autoresearch/benchmark/cifar10/task_spec.py",
    ):
        assert expected in module_paths

    for module in index["code_modules"]:
        assert module["summary"]
        assert module["surface"]

    figures = {figure["path"]: figure for figure in index["paper_figures"]}
    assert figures[
        "paper/neurips-submission/figures/autoresearch/first_hit_ecdf_by_mode.png"
    ]["provenance"] == "exact experiment copy"
    assert figures[
        "paper/neurips-submission/figures/candidates/candidate_pareto_frontier.png"
    ]["source"] == "src/plot_humaneval_candidates.py"
    assert figures[
        "paper/neurips-submission/figures/autoresearch_n20_confirmation/quality_vs_certified_resource.png"
    ]["source"].startswith("experiments/")

    assert all(ref["present"] for ref in index["active_paper_references"])
    main_refs = [
        ref for ref in index["active_paper_references"]
        if ref["source_tex"] == "paper/neurips-submission/main.tex" and ref["kind"] == "figure"
    ]
    assert len(main_refs) == 5
    assert {
        ref["resolved_path"] for ref in main_refs
    } == {
        "paper/neurips-submission/figures/strategy_routing/four_term_accounting.pdf",
        "paper/neurips-submission/figures/strategy_routing/confirmatory_speedup.pdf",
        "paper/neurips-submission/figures/strategy_routing/strategy_specialization.pdf",
        "paper/neurips-submission/figures/strategy_routing/information_speed_curve.pdf",
        "paper/neurips-submission/figures/strategy_routing/router_allocations.pdf",
    }
    assert any(
        ref["source_tex"] == "paper/neurips-submission/arxiv.tex"
        and ref["kind"] == "bibliography"
        and ref["resolved_path"] == "paper/neurips-submission/references.bib"
        for ref in index["active_paper_references"]
    )

    targets = {target["target"]: target for target in index["command_targets"]}
    assert set(REQUIRED_MAKE_TARGETS) <= set(targets)
    assert set(targets["check"]["dependencies"].split()) == {"indexes", "readiness", "compile", "test"}
    assert all(targets[target]["description"] for target in REQUIRED_MAKE_TARGETS)

    for bundle in index["experiment_bundles"]:
        assert bundle["readme_title"]
        assert bundle["evidence_tier"]
        if "completed" in bundle["status"]:
            assert bundle["evidence_tier"] != "not tiered"

    for entry in index["scripts"]:
        assert entry["summary"] != "No top-level summary found."
        assert not entry["summary"].startswith("SBATCH")


def test_generated_markdown_indexes_are_up_to_date(tmp_path: Path) -> None:
    generated_knowledge = _render_markdown(
        "scripts/build_knowledge_index.py",
        tmp_path / "knowledge-index.md",
    )
    generated_inventory = _render_markdown(
        "scripts/build_repo_inventory.py",
        tmp_path / "repo-inventory.md",
    )
    generated_archive_manifest = _render_markdown(
        "scripts/build_paper_archive_manifest.py",
        tmp_path / "paper-archive-manifest.md",
    )
    generated_experiment_manifest = _render_markdown(
        "scripts/build_experiment_manifest.py",
        tmp_path / "experiment-manifest.md",
    )
    generated_command_manifest = _render_markdown(
        "scripts/build_command_manifest.py",
        tmp_path / "command-manifest.md",
    )

    assert str(ROOT) not in generated_knowledge
    assert str(ROOT) not in generated_inventory
    assert str(ROOT) not in generated_archive_manifest
    assert str(ROOT) not in generated_experiment_manifest
    assert str(ROOT) not in generated_command_manifest
    assert "/Users/" not in generated_knowledge
    assert "/Users/" not in generated_inventory
    assert "/Users/" not in generated_archive_manifest
    assert "/Users/" not in generated_experiment_manifest
    assert "/Users/" not in generated_command_manifest
    assert generated_knowledge == (
        ROOT / GENERATED_AUDITS["knowledge"]
    ).read_text(encoding="utf-8")
    assert generated_inventory == (
        ROOT / GENERATED_AUDITS["inventory"]
    ).read_text(encoding="utf-8")
    assert generated_archive_manifest == (
        ROOT / GENERATED_AUDITS["paper_archive"]
    ).read_text(encoding="utf-8")
    assert generated_experiment_manifest == (
        ROOT / GENERATED_AUDITS["experiment_manifest"]
    ).read_text(encoding="utf-8")
    assert generated_command_manifest == (
        ROOT / GENERATED_AUDITS["command_manifest"]
    ).read_text(encoding="utf-8")


def test_command_manifest_classifies_safety_boundaries() -> None:
    manifest = _run_json("scripts/build_command_manifest.py")
    commands = {command["command"]: command for command in manifest["commands"]}

    assert manifest["root"] == "."
    assert manifest["command_count"] >= 30
    assert manifest["missing_required_make_targets"] == []
    assert manifest["safety_classes"]["safe-local"] >= 5
    assert manifest["safety_classes"]["live-cluster"] >= 1

    assert commands["make check"]["safety_class"] == "safe-local"
    assert commands["make check"]["default_safe"]
    assert commands["make paper-build"]["safety_class"] == "safe-local-optional-tool"
    assert commands["make paper-build"]["default_safe"]
    assert commands["uv run agent-workflow"]["safety_class"] == "mixed-cli"
    assert not commands["uv run agent-workflow"]["default_safe"]

    live_commands = [
        command for command in manifest["commands"]
        if command["safety_class"] in {"live-local", "live-cluster", "cluster-setup", "mixed-cli"}
    ]
    assert live_commands
    assert all(not command["default_safe"] for command in live_commands)


def test_experiment_manifest_classifies_bundle_assets() -> None:
    manifest = _run_json("scripts/build_experiment_manifest.py")
    bundles = {bundle["path"]: bundle for bundle in manifest["bundles"]}

    assert manifest["root"] == "."
    assert manifest["bundle_count"] >= 20
    assert manifest["missing_paths"] == []
    assert manifest["missing_readmes"] == []
    assert manifest["reproducibility_classes"]["paper-supporting-evidence"] >= 6

    autoresearch = bundles[
        "experiments/autoresearch-cifar10/three-worker-model-routing/"
    ]
    assert autoresearch["reproducibility_class"] in {
        "partial-evidence",
        "paper-supporting-evidence",
    }
    assert autoresearch["result_files"] > 0
    assert autoresearch["raw_files"] > 0
    assert any(path.endswith("README.md") for path in autoresearch["key_files"])

    strategy = bundles[
        "experiments/humaneval-plus/strategy-by-difficulty-grid/"
    ]
    assert strategy["reproducibility_class"] == "paper-supporting-evidence"
    assert strategy["configs"] > 0
    assert strategy["scripts"] > 0
    assert strategy["run_files"] > 0

    scaffold = bundles[
        "experiments/swebench-verified/neutral-100-meta-design-scaffold/"
    ]
    assert scaffold["reproducibility_class"] == "scaffold"


def test_paper_archive_manifest_classifies_all_archive_files() -> None:
    manifest = _run_json("scripts/build_paper_archive_manifest.py")
    coverage = manifest["policy_coverage"]
    records = {record["path"]: record for record in manifest["files"]}

    assert manifest["archive_root"] == "paper/neurips-submission/archive"
    assert coverage["classified"] == coverage["files"]
    assert coverage["unclassified"] == []
    assert len(records) >= 10

    assert records[
        "paper/neurips-submission/archive/theory_anchor.tex"
    ]["disposition"] == "canonical-anchor"
    assert records[
        "paper/neurips-submission/archive/next_steps.tex"
    ]["disposition"] == "keep-independent"
    removed_snapshots = {
        "paper/neurips-submission/archive/final_paper_local.tex",
        "paper/neurips-submission/archive/main_1.tex",
        "paper/neurips-submission/archive/main_3.tex",
        "paper/neurips-submission/archive/main_3_local.tex",
        "paper/neurips-submission/archive/main_local.tex",
    }
    assert removed_snapshots.isdisjoint(records)


def test_inventory_has_no_unexpected_source_duplicates() -> None:
    inventory = _run_json("scripts/build_repo_inventory.py")

    assert inventory["root"] == "."
    assert all(inventory["entrypoints"].values())
    assert inventory["entrypoints"]["Makefile"]
    assert all(inventory["paper_sources"].values())
    assert all("agent_index_config.py" not in path for path in inventory["scripts"])
    assert all(item["category"] != "unexpected" for item in inventory["duplicate_summary"])

    for group in inventory["duplicate_groups"]:
        suffixes = {Path(path).suffix for path in group}
        assert ".md" not in suffixes
        assert ".tex" not in suffixes

        if suffixes == {".py"}:
            assert all(Path(path).name == "__init__.py" for path in group)

        if suffixes & {".pdf", ".png"}:
            assert any(path.startswith("paper/neurips-submission/figures/") for path in group)
            assert any(path.startswith("experiments/") for path in group)


def test_agent_facing_docs_do_not_reference_local_user_paths() -> None:
    docs = [ROOT / path for path in AGENT_DOC_ROOT_FILES]
    docs.extend(
        path
        for path in (ROOT / "docs").rglob("*.md")
        if "archive" not in path.relative_to(ROOT).parts
    )

    offenders = []
    for path in docs:
        text = path.read_text(encoding="utf-8")
        if any(pattern in text for pattern in LOCAL_PATH_PATTERNS):
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []


def test_makefile_exposes_agent_shortcuts() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in REQUIRED_MAKE_TARGETS:
        assert f"{target}:" in makefile


def test_agent_readiness_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_agent_readiness.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Agent readiness: ok" in result.stdout
