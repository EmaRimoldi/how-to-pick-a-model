from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts.maintenance.agent_index_config import (
    AGENT_DOC_ROOT_FILES,
    CORE_EXPERIMENT_BUNDLES,
    CORE_CODE_MODULES,
    CANONICAL_TEX,
    GENERATED_AUDITS,
    LOCAL_PATH_PATTERNS,
    REQUIRED_ACTIONS,
    MAINTENANCE_COMMAND,
    MAINTENANCE_RUNNER,
)


ROOT = Path(__file__).resolve().parents[2]


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
    index = _run_json("scripts/maintenance/build_knowledge_index.py")

    assert index["root"] == "."
    assert all(index["canonical_docs"].values())
    assert {path.as_posix() for path in CANONICAL_TEX} <= {obj["path"] for obj in index["formal_objects"]}
    assert CORE_EXPERIMENT_BUNDLES <= {bundle["path"] for bundle in index["experiment_bundles"]}
    assert all("agent_index_config.py" not in entry["path"] for entry in index["scripts"])
    assert any(entry["path"] == "scripts/maintenance/build_command_manifest.py" for entry in index["scripts"])
    assert any(entry["path"] == "scripts/maintenance/build_experiment_manifest.py" for entry in index["scripts"])

    module_paths = {module["path"] for module in index["code_modules"]}
    assert CORE_CODE_MODULES <= module_paths

    for module in index["code_modules"]:
        assert module["summary"]
        assert module["surface"]

    figures = {figure["path"]: figure for figure in index["paper_figures"]}
    assert figures[
        "docs/paper/neurips-submission/figures/autoresearch/first_hit_ecdf_by_mode.png"
    ]["provenance"] == "archived experiment figure"
    assert figures[
        "docs/paper/neurips-submission/figures/autoresearch/first_hit_ecdf_by_mode.png"
    ]["source"] == "provenance/verified-cleanup-2026-10-25"
    assert all(ref["present"] for ref in index["active_paper_references"])
    assert {
        ref["resolved_path"] for ref in index["active_paper_references"] if ref["kind"] == "figure"
    } <= set(figures)
    main_refs = [
        ref for ref in index["active_paper_references"]
        if ref["source_tex"] == "docs/paper/neurips-submission/main.tex" and ref["kind"] == "figure"
    ]
    assert len(main_refs) == 5
    assert {
        ref["resolved_path"] for ref in main_refs
    } == {
        "docs/paper/neurips-submission/figures/strategy_routing/four_term_accounting.pdf",
        "docs/paper/neurips-submission/figures/strategy_routing/confirmatory_speedup.pdf",
        "docs/paper/neurips-submission/figures/strategy_routing/strategy_specialization.pdf",
        "docs/paper/neurips-submission/figures/strategy_routing/information_speed_curve.pdf",
        "docs/paper/neurips-submission/figures/strategy_routing/router_allocations.pdf",
    }
    assert any(
        ref["source_tex"] == "docs/paper/neurips-submission/arxiv.tex"
        and ref["kind"] == "bibliography"
        and ref["resolved_path"] == "docs/paper/neurips-submission/references.bib"
        for ref in index["active_paper_references"]
    )

    targets = {target["target"]: target for target in index["command_targets"]}
    assert set(REQUIRED_ACTIONS) <= set(targets)
    assert set(targets["check"]["dependencies"].split()) == {"indexes", "readiness", "compile", "test"}
    assert all(targets[target]["description"] for target in REQUIRED_ACTIONS)

    for bundle in index["experiment_bundles"]:
        assert bundle["readme_title"]
        assert bundle["evidence_tier"]
        if "completed" in bundle["status"]:
            assert bundle["evidence_tier"] != "not tiered"

    for entry in index["scripts"]:
        assert entry["summary"] != "No top-level summary found."
        assert not entry["summary"].startswith("SBATCH")


def test_generated_markdown_indexes_are_up_to_date(tmp_path: Path) -> None:
    generators = {
        "knowledge": "scripts/maintenance/build_knowledge_index.py",
        "inventory": "scripts/maintenance/build_repo_inventory.py",
        "experiment_manifest": "scripts/maintenance/build_experiment_manifest.py",
        "command_manifest": "scripts/maintenance/build_command_manifest.py",
    }
    for key, script in generators.items():
        generated = _render_markdown(script, tmp_path / GENERATED_AUDITS[key].name)
        assert str(ROOT) not in generated
        assert "/Users/" not in generated
        assert generated == (ROOT / GENERATED_AUDITS[key]).read_text(encoding="utf-8")


def test_command_manifest_classifies_safety_boundaries() -> None:
    manifest = _run_json("scripts/maintenance/build_command_manifest.py")
    commands = {command["command"]: command for command in manifest["commands"]}

    assert manifest["root"] == "."
    assert manifest["command_count"] == len(commands)
    assert manifest["missing_required_actions"] == []
    assert manifest["safety_classes"]["safe-local"] >= 5
    assert manifest["safety_classes"]["live-local"] >= 1
    assert manifest["safety_classes"]["cluster-setup"] >= 1

    assert commands[f"{MAINTENANCE_COMMAND} check"]["safety_class"] == "safe-local"
    assert commands[f"{MAINTENANCE_COMMAND} check"]["default_safe"]
    assert commands[f"{MAINTENANCE_COMMAND} paper-build"]["safety_class"] == "safe-local-optional-tool"
    assert commands[f"{MAINTENANCE_COMMAND} paper-build"]["default_safe"]
    assert "uv run agent-workflow" not in commands
    assert "make paper-figures-autoresearch" not in commands
    stdin = commands['python scripts/repair_stdin_pilot.py']
    assert stdin['safety_class'] == 'mixed-cli' and not stdin['default_safe']

    live_commands = [
        command for command in manifest["commands"]
        if command["safety_class"] in {"live-local", "live-cluster", "cluster-setup", "mixed-cli"}
    ]
    assert live_commands
    assert all(not command["default_safe"] for command in live_commands)



def test_command_validation_rejects_default_safe_provider_launchers(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts" / "maintenance"))
    from validate_agent_readiness import check_command_manifest

    manifest = _run_json("scripts/maintenance/build_command_manifest.py")
    assert check_command_manifest(manifest) == []
    collector = next(command for command in manifest["commands"]
                     if command["command"] == "python scripts/run_context_value.py")
    assert collector["safety_class"] == "live-local"
    collector["default_safe"] = True
    assert any("live command incorrectly marked default-safe" in problem
               for problem in check_command_manifest(manifest))


def test_experiment_manifest_classifies_bundle_assets() -> None:
    manifest = _run_json("scripts/maintenance/build_experiment_manifest.py")
    bundles = {bundle["path"]: bundle for bundle in manifest["bundles"]}

    assert manifest["root"] == "."
    assert manifest["bundle_count"] == len(bundles) == 8
    assert CORE_EXPERIMENT_BUNDLES <= set(bundles)
    assert manifest["missing_paths"] == []
    assert manifest["missing_readmes"] == []
    assert all(bundles[path]["reproducibility_class"] in {
        "paper-supporting-evidence", "partial-evidence"
    } for path in CORE_EXPERIMENT_BUNDLES)

    assert not any("cifar10" in path for path in bundles)

    strategy = bundles[
        "experiments/humaneval-plus/strategy-by-difficulty-grid/"
    ]
    assert strategy["reproducibility_class"] == "paper-supporting-evidence"
    assert strategy["configs"] > 0
    assert strategy["scripts"] > 0
    assert strategy["run_files"] > 0


def test_readiness_rejects_empty_core_evidence_after_bundle_consolidation(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts" / "maintenance"))
    from validate_agent_readiness import check_experiment_manifest

    manifest = _run_json("scripts/maintenance/build_experiment_manifest.py")
    assert check_experiment_manifest(manifest) == []
    strategy = next(row for row in manifest["bundles"] if row["path"].endswith("/strategy-by-difficulty-grid/"))
    strategy.update(result_files=0, figure_files=0, reproducibility_class="inspect-readme")
    problems = check_experiment_manifest(manifest)
    assert any("lacks recorded evidence" in problem and "/strategy-by-difficulty-grid/" in problem for problem in problems)
    assert any("lacks an evidence classification" in problem for problem in problems)

def test_inventory_is_identical_for_lfs_pointer_and_hydrated_object(tmp_path: Path) -> None:
    payload = b"archived campaign evidence\n" * 80
    path = tmp_path / "campaign.tar.zst.part-000"
    path.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{hashlib.sha256(payload).hexdigest()}\n"
        f"size {len(payload)}\n"
    )

    def inventory() -> dict:
        result = subprocess.run(
            [sys.executable, "scripts/maintenance/build_repo_inventory.py", "--root", str(tmp_path), "--format", "json"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout)

    pointer_inventory = inventory()
    assert pointer_inventory["total_bytes"] == len(payload)
    path.write_bytes(payload)
    assert inventory() == pointer_inventory


def test_inventory_has_no_unexpected_source_duplicates() -> None:
    inventory = _run_json("scripts/maintenance/build_repo_inventory.py")

    assert inventory["root"] == "."
    assert all(inventory["entrypoints"].values())
    assert inventory["entrypoints"][MAINTENANCE_RUNNER]
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
            assert any(path.startswith("docs/paper/neurips-submission/figures/") for path in group)
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


def test_maintenance_runner_exposes_documented_actions() -> None:
    result = subprocess.run(
        [sys.executable, MAINTENANCE_RUNNER, "--help"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    for action in REQUIRED_ACTIONS:
        assert action in result.stdout


def test_agent_readiness_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/maintenance/validate_agent_readiness.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Agent readiness: ok" in result.stdout
