"""Build a deterministic repository inventory for agents and reviewers."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from agent_index_config import (
    CANONICAL_ENTRYPOINTS,
    EXCLUDED_DIRS,
    GENERATED_AUDIT_PATHS,
    PAPER_SOURCES,
    SCRIPT_DIRS,
    SCRIPT_SUPPORT_FILES,
)

SELECTED_DUPLICATE_SUFFIXES = {".md", ".tex", ".py", ".pdf", ".png"}


@dataclass(frozen=True)
class FileRecord:
    path: str
    suffix: str
    size: int


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_file() and rel not in GENERATED_AUDIT_PATHS and not should_skip(rel):
            yield path


def file_records(root: Path) -> list[FileRecord]:
    records: list[FileRecord] = []
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        suffix = path.suffix.lower() or "<none>"
        records.append(FileRecord(rel, suffix, path.stat().st_size))
    return records


def top_level_sizes(records: list[FileRecord]) -> list[tuple[str, int, int]]:
    sizes: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        top = record.path.split("/", 1)[0]
        sizes[top] += record.size
        counts[top] += 1
    return sorted(
        ((name, counts[name], size) for name, size in sizes.items()),
        key=lambda item: (-item[2], item[0]),
    )


def experiment_readmes(root: Path) -> list[str]:
    base = root / "experiments"
    if not base.exists():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in base.rglob("README.md")
        if not should_skip(path.relative_to(root))
    )


def scripts(root: Path) -> list[str]:
    paths: list[str] = []
    for script_dir in SCRIPT_DIRS:
        for path in sorted((root / script_dir).glob("*")):
            if (
                path.is_file()
                and path.name not in SCRIPT_SUPPORT_FILES
                and not should_skip(path.relative_to(root))
            ):
                paths.append(path.relative_to(root).as_posix())
    return sorted(paths)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def duplicate_groups(root: Path, records: list[FileRecord]) -> list[list[str]]:
    by_size: dict[tuple[str, int], list[str]] = defaultdict(list)
    for record in records:
        if record.suffix in SELECTED_DUPLICATE_SUFFIXES:
            by_size[(record.suffix, record.size)].append(record.path)

    groups: list[list[str]] = []
    for paths in by_size.values():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[str]] = defaultdict(list)
        for rel in paths:
            by_hash[sha256(root / rel)].append(rel)
        groups.extend(sorted(group) for group in by_hash.values() if len(group) > 1)
    return sorted(groups, key=lambda group: (Path(group[0]).suffix, group[0]))


def duplicate_category(group: list[str]) -> str:
    suffixes = {Path(path).suffix for path in group}
    if suffixes == {".py"} and all(Path(path).name == "__init__.py" for path in group):
        return "package initializers"
    if suffixes & {".pdf", ".png"}:
        has_paper = any(path.startswith("paper/neurips-submission/figures/") for path in group)
        has_experiment = any(path.startswith("experiments/") for path in group)
        if has_paper and has_experiment:
            return "paper-ready figure copy"
    return "unexpected"


def duplicate_summary(groups: list[list[str]]) -> list[dict[str, int | str]]:
    counts = Counter(duplicate_category(group) for group in groups)
    return [
        {
            "category": category,
            "groups": counts[category],
            "extra_files": sum(
                len(group) - 1 for group in groups if duplicate_category(group) == category
            ),
        }
        for category in sorted(counts)
    ]


def build_inventory(root: Path) -> dict:
    records = file_records(root)
    suffix_counts = Counter(record.suffix for record in records)
    suffix_sizes = Counter()
    for record in records:
        suffix_sizes[record.suffix] += record.size

    duplicates = duplicate_groups(root, records)

    return {
        "root": ".",
        "total_files": len(records),
        "total_bytes": sum(record.size for record in records),
        "entrypoints": {
            path: (root / path).exists()
            for path in CANONICAL_ENTRYPOINTS
        },
        "paper_sources": {
            path: (root / path).exists()
            for path in PAPER_SOURCES
        },
        "top_level": [
            {"path": name, "files": count, "bytes": size}
            for name, count, size in top_level_sizes(records)
        ],
        "extensions": [
            {
                "extension": suffix,
                "files": suffix_counts[suffix],
                "bytes": suffix_sizes[suffix],
            }
            for suffix in sorted(suffix_counts, key=lambda s: (-suffix_counts[s], s))
        ],
        "experiment_readmes": experiment_readmes(root),
        "scripts": scripts(root),
        "duplicate_groups": duplicates,
        "duplicate_summary": duplicate_summary(duplicates),
    }


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "K", "M", "G"):
        if value < 1024 or unit == "G":
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}G"


def yes_no(value: bool) -> str:
    return "yes" if value else "missing"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def render_markdown(inventory: dict) -> str:
    lines: list[str] = [
        "# Repository Inventory",
        "",
        "Generated by `python scripts/build_repo_inventory.py --output docs/audits/repo-inventory.md`.",
        "The output is deterministic and excludes local caches, virtualenvs, `tmp/`, `runs/`, and generated audit markdowns.",
        "",
        "## Summary",
        "",
        f"- Root: `{inventory['root']}`",
        f"- Files indexed: `{inventory['total_files']}`",
        f"- Bytes indexed: `{human_size(inventory['total_bytes'])}`",
        "",
        "## Canonical Entrypoints",
        "",
        markdown_table(
            ["Path", "Present"],
            [[f"`{path}`", yes_no(present)] for path, present in inventory["entrypoints"].items()],
        ),
        "",
        "## Paper Sources",
        "",
        markdown_table(
            ["Path", "Present"],
            [[f"`{path}`", yes_no(present)] for path, present in inventory["paper_sources"].items()],
        ),
        "",
        "## Top-Level Areas",
        "",
        markdown_table(
            ["Path", "Files", "Size"],
            [
                [f"`{item['path']}`", str(item["files"]), human_size(item["bytes"])]
                for item in inventory["top_level"]
            ],
        ),
        "",
        "## File Types",
        "",
        markdown_table(
            ["Extension", "Files", "Size"],
            [
                [f"`{item['extension']}`", str(item["files"]), human_size(item["bytes"])]
                for item in inventory["extensions"][:30]
            ],
        ),
        "",
        "## Experiment Readmes",
        "",
    ]
    lines.extend(f"- `{path}`" for path in inventory["experiment_readmes"])
    lines.extend(["", "## Script Entrypoints", ""])
    lines.extend(f"- `{path}`" for path in inventory["scripts"])

    duplicates = inventory["duplicate_groups"]
    lines.extend(
        [
            "",
            "## Exact Duplicates In Selected Types",
            "",
            f"- Groups: `{len(duplicates)}`",
            f"- Extra files: `{sum(len(group) - 1 for group in duplicates)}`",
            "",
            "The readiness gate treats document/source duplicates as failures. The",
            "remaining allowed duplicates are paper-ready figure copies under",
            "`paper/neurips-submission/figures/` whose experiment outputs remain",
            "canonical.",
            "",
            markdown_table(
                ["Category", "Groups", "Extra Files"],
                [
                    [
                        item["category"],
                        str(item["groups"]),
                        str(item["extra_files"]),
                    ]
                    for item in inventory["duplicate_summary"]
                ],
            ),
        ]
    )
    if duplicates:
        lines.append("")
        for group in duplicates[:25]:
            lines.append("- Group:")
            lines.extend(f"  - `{path}`" for path in group)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root. Defaults to current directory.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        help="Write output to this file instead of stdout.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    inventory = build_inventory(root)
    if args.format == "json":
        rendered = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_markdown(inventory)

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
