"""Build a manifest of experiment bundles and their reproducibility assets."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from build_knowledge_index import parse_experiment_table


ASSET_DIRS = (
    "configs",
    "data",
    "raw",
    "results",
    "figures",
    "scripts",
    "logs",
    "analysis",
    "runs",
    "reports",
    "source",
)
CONFIG_SUFFIXES = {".yaml", ".yml", ".json", ".toml"}
DATA_SUFFIXES = {".json", ".jsonl", ".csv", ".tsv", ".txt", ".parquet", ".pkl", ".pickle"}
FIGURE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".svg"}
SCRIPT_SUFFIXES = {".py", ".sh", ".sbatch"}
SUMMARY_NAMES = {
    "summary.json",
    "summary.csv",
    "summary.md",
    "results.json",
    "results.csv",
    "metrics.json",
    "analysis.json",
}
EXCLUDED_PARTS = {".git", ".venv", ".pytest_cache", "__pycache__"}


@dataclass(frozen=True)
class ExperimentManifestRecord:
    benchmark: str
    path: str
    status: str
    evidence_tier: str
    reproducibility_class: str
    readme_title: str
    evidence: str
    total_files: int
    asset_dirs: str
    configs: int
    data_files: int
    result_files: int
    figure_files: int
    scripts: int
    raw_files: int
    run_files: int
    summary_files: int
    key_files: list[str]


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def iter_bundle_files(bundle_dir: Path) -> list[Path]:
    if not bundle_dir.exists():
        return []
    return sorted(
        path
        for path in bundle_dir.rglob("*")
        if path.is_file() and not should_skip(path.relative_to(bundle_dir))
    )


def rel_to_root(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def count_by_predicate(paths: list[Path], predicate) -> int:
    return sum(1 for path in paths if predicate(path))


def is_config_file(path: Path) -> bool:
    name = path.name.lower()
    return (
        "configs" in path.parts
        or name.startswith("config")
        or (path.suffix.lower() in CONFIG_SUFFIXES and "config" in name)
    )


def is_data_file(path: Path) -> bool:
    if "data" in path.parts or "raw" in path.parts:
        return True
    if any(part in path.parts for part in {"configs", "results", "runs", "logs"}):
        return False
    return path.suffix.lower() in DATA_SUFFIXES


def is_result_file(path: Path) -> bool:
    return "results" in path.parts or path.name.lower() in SUMMARY_NAMES


def is_script_file(path: Path) -> bool:
    return "scripts" in path.parts or path.suffix.lower() in SCRIPT_SUFFIXES


def asset_dirs(bundle_dir: Path) -> list[str]:
    if not bundle_dir.exists():
        return []
    found: set[str] = set()
    for path in bundle_dir.rglob("*"):
        if path.is_dir() and path.name in ASSET_DIRS:
            found.add(path.relative_to(bundle_dir).as_posix())
    return sorted(found)


def key_files(root: Path, bundle_dir: Path, files: list[Path]) -> list[str]:
    readme = bundle_dir / "README.md"

    def priority(path: Path) -> tuple[int, str]:
        rel = path.relative_to(bundle_dir)
        parts = set(rel.parts)
        name = path.name.lower()
        suffix = path.suffix.lower()
        rel_text = rel.as_posix()
        if path == readme:
            return (0, rel_text)
        if "accounting" in parts or "derived" in parts:
            return (1, rel_text)
        if "manifests" in parts:
            return (2, rel_text)
        if "source" in parts or "config_snapshot" in parts:
            return (3, rel_text)
        if name in SUMMARY_NAMES or "summary" in name:
            if "worker_confirmation" in parts or "raw" in parts:
                return (8, rel_text)
            return (4, rel_text)
        if is_config_file(rel):
            return (5, rel_text)
        if suffix in FIGURE_SUFFIXES and "archive" not in parts:
            return (6, rel_text)
        if is_script_file(rel):
            return (7, rel_text)
        if suffix in FIGURE_SUFFIXES:
            return (9, rel_text)
        return (99, rel_text)

    candidates = [path for path in files if priority(path)[0] < 99]
    if readme.exists() and readme not in candidates:
        candidates.append(readme)
    candidates = sorted(candidates, key=priority)

    deduped: list[str] = []
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(rel_to_root(root, path))
        if len(deduped) >= 12:
            break
    return deduped


def reproducibility_class(status: str, record_counts: dict[str, int], tier: str) -> str:
    normalized = status.lower()
    if "archive" in normalized or "historical" in normalized:
        return "historical-or-archive"
    if "scaffold" in normalized or "runnable scaffold" in normalized:
        return "scaffold"
    if "incomplete" in normalized or "partial" in normalized or "gap" in normalized:
        return "partial-evidence"
    if "completed" in normalized:
        has_result_asset = record_counts["result_files"] + record_counts["figure_files"] > 0
        if has_result_asset and tier != "not tiered":
            return "paper-supporting-evidence"
        return "completed-needs-tier-or-assets"
    return "inspect-readme"


def build_manifest(root: Path) -> dict[str, object]:
    bundles = parse_experiment_table(root)
    records: list[ExperimentManifestRecord] = []
    missing_paths: list[str] = []
    missing_readmes: list[str] = []

    for bundle in bundles:
        rel_path = Path(bundle.path.rstrip("/"))
        bundle_dir = root / rel_path
        files = iter_bundle_files(bundle_dir)
        if not bundle_dir.exists():
            missing_paths.append(bundle.path)
        if not (bundle_dir / "README.md").exists():
            missing_readmes.append(bundle.path)

        rel_files = [path.relative_to(bundle_dir) for path in files] if bundle_dir.exists() else []
        counts = {
            "configs": count_by_predicate(rel_files, is_config_file),
            "data_files": count_by_predicate(rel_files, is_data_file),
            "result_files": count_by_predicate(rel_files, is_result_file),
            "figure_files": count_by_predicate(rel_files, lambda path: path.suffix.lower() in FIGURE_SUFFIXES),
            "scripts": count_by_predicate(rel_files, is_script_file),
            "raw_files": count_by_predicate(rel_files, lambda path: "raw" in path.parts),
            "run_files": count_by_predicate(rel_files, lambda path: "runs" in path.parts or "logs" in path.parts),
            "summary_files": count_by_predicate(rel_files, lambda path: path.name.lower() in SUMMARY_NAMES or "summary" in path.name.lower()),
        }

        records.append(
            ExperimentManifestRecord(
                benchmark=bundle.benchmark,
                path=bundle.path,
                status=bundle.status,
                evidence_tier=bundle.evidence_tier,
                reproducibility_class=reproducibility_class(bundle.status, counts, bundle.evidence_tier),
                readme_title=bundle.readme_title,
                evidence=bundle.evidence,
                total_files=len(files),
                asset_dirs=", ".join(asset_dirs(bundle_dir)),
                configs=counts["configs"],
                data_files=counts["data_files"],
                result_files=counts["result_files"],
                figure_files=counts["figure_files"],
                scripts=counts["scripts"],
                raw_files=counts["raw_files"],
                run_files=counts["run_files"],
                summary_files=counts["summary_files"],
                key_files=key_files(root, bundle_dir, files),
            )
        )

    classes = Counter(record.reproducibility_class for record in records)
    tiers = Counter(record.evidence_tier for record in records)
    return {
        "root": ".",
        "bundle_count": len(records),
        "missing_paths": missing_paths,
        "missing_readmes": missing_readmes,
        "reproducibility_classes": dict(sorted(classes.items())),
        "evidence_tiers": dict(sorted(tiers.items())),
        "bundles": [asdict(record) for record in records],
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
    bundles = manifest["bundles"]
    lines: list[str] = [
        "# Experiment Manifest",
        "",
        "Generated by `python scripts/build_experiment_manifest.py --output docs/audits/experiment-manifest.md`.",
        "This manifest audits the experiment bundles listed in `experiments/README.md` and summarizes the reproducibility assets each bundle contains.",
        "",
        "## Summary",
        "",
        f"- Bundles indexed: `{manifest['bundle_count']}`",
        f"- Missing bundle paths: `{len(manifest['missing_paths'])}`",
        f"- Missing README files: `{len(manifest['missing_readmes'])}`",
        "",
        "## Reproducibility Classes",
        "",
        markdown_table(
            ["Class", "Bundles"],
            [[f"`{name}`", count] for name, count in manifest["reproducibility_classes"].items()],
        ),
        "",
        "## Evidence Tiers",
        "",
        markdown_table(
            ["Tier", "Bundles"],
            [[f"`{name}`", count] for name, count in manifest["evidence_tiers"].items()],
        ),
        "",
        "## Bundle Assets",
        "",
        markdown_table(
            [
                "Bundle",
                "Status",
                "Tier",
                "Class",
                "Files",
                "Configs",
                "Data",
                "Results",
                "Figures",
                "Scripts",
                "Raw",
                "Runs",
                "Summaries",
            ],
            [
                [
                    f"`{bundle['path']}`",
                    bundle["status"],
                    bundle["evidence_tier"],
                    f"`{bundle['reproducibility_class']}`",
                    bundle["total_files"],
                    bundle["configs"],
                    bundle["data_files"],
                    bundle["result_files"],
                    bundle["figure_files"],
                    bundle["scripts"],
                    bundle["raw_files"],
                    bundle["run_files"],
                    bundle["summary_files"],
                ]
                for bundle in bundles
            ],
        ),
        "",
        "## Key Files",
        "",
    ]
    for bundle in bundles:
        lines.append(f"### `{bundle['path']}`")
        lines.append("")
        lines.append(f"- Title: {bundle['readme_title'] or 'missing'}")
        lines.append(f"- Evidence: {bundle['evidence']}")
        lines.append(f"- Asset directories: `{bundle['asset_dirs'] or 'none'}`")
        if bundle["key_files"]:
            lines.extend(f"- `{path}`" for path in bundle["key_files"])
        else:
            lines.append("- No key files detected beyond the bundle table entry.")
        lines.append("")
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
