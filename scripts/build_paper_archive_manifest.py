"""Build a manifest for paper archive sources and retained provenance files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


ARCHIVE_ROOT = Path("paper/neurips-submission/archive")
TEXT_SUFFIXES = {".tex", ".bib"}

ARCHIVE_POLICIES = {
    "Achille & Soatto.pdf": {
        "role": "external theory reference",
        "disposition": "keep-reference",
        "superseded_by": "",
        "notes": "Reference PDF for the theoretical framing; not active manuscript source.",
    },
    "BP.pdf": {
        "role": "external proper-time reference",
        "disposition": "keep-reference",
        "superseded_by": "",
        "notes": "Reference PDF retained for the proper-time genealogy.",
    },
    "Beneventano_Poggio.tex": {
        "role": "mechanical theory extraction",
        "disposition": "keep-provenance",
        "superseded_by": "archive/theory_anchor.tex for promoted claims",
        "notes": "Use for source genealogy, not as active prose.",
    },
    "final_paper.tex": {
        "role": "historical integrated draft",
        "disposition": "superseded-provenance",
        "superseded_by": "main.tex, arxiv.tex, archive/theory_anchor.tex",
        "notes": "Mine only when reconciling missing concepts.",
    },
    "final_paper_local.tex": {
        "role": "local snapshot of historical integrated draft",
        "disposition": "review-before-delete",
        "superseded_by": "final_paper.tex and archive/theory_anchor.tex",
        "notes": "Retained only because local snapshots can contain unpushed edits.",
    },
    "main.pdf": {
        "role": "historical compiled manuscript snapshot",
        "disposition": "keep-provenance",
        "superseded_by": "main.tex build output",
        "notes": "Do not cite as evidence source; rebuild active sources with make paper-build.",
    },
    "main_1.tex": {
        "role": "historical compact draft",
        "disposition": "superseded-provenance",
        "superseded_by": "main.tex and archive/theory_anchor.tex",
        "notes": "Use only for draft genealogy.",
    },
    "main_3.tex": {
        "role": "historical theory-heavy draft",
        "disposition": "superseded-provenance",
        "superseded_by": "archive/theory_anchor.tex",
        "notes": "Main source for prior theory consolidation checks.",
    },
    "main_3_local.tex": {
        "role": "local snapshot of historical theory-heavy draft",
        "disposition": "review-before-delete",
        "superseded_by": "main_3.tex and archive/theory_anchor.tex",
        "notes": "Retained only for possible local-only deltas.",
    },
    "main_local.tex": {
        "role": "local snapshot of compact draft",
        "disposition": "review-before-delete",
        "superseded_by": "main.tex",
        "notes": "Retained only for possible local-only deltas.",
    },
    "neurips_old.tex": {
        "role": "old NeurIPS draft",
        "disposition": "superseded-provenance",
        "superseded_by": "main.tex",
        "notes": "Do not use as active source unless investigating historical wording.",
    },
    "next_steps.tex": {
        "role": "independent planning document",
        "disposition": "keep-independent",
        "superseded_by": "",
        "notes": "Keep separate from the manuscript; do not auto-merge.",
    },
    "references.bib": {
        "role": "archived bibliography",
        "disposition": "keep-provenance",
        "superseded_by": "references.bib",
        "notes": "Historical bibliography used by archive drafts; active bibliography is one level up.",
    },
    "submitted-manuscript.pdf": {
        "role": "immutable submitted manuscript snapshot",
        "disposition": "keep-reference",
        "superseded_by": "",
        "notes": "Submitted artifact preserved for audit and reviewer-context comparison.",
    },
    "theory_anchor.tex": {
        "role": "canonical theory archive anchor",
        "disposition": "canonical-anchor",
        "superseded_by": "",
        "notes": "Maximal validated theory source for promoting formal claims.",
    },
}


@dataclass(frozen=True)
class ArchiveRecord:
    path: str
    suffix: str
    size_bytes: int
    lines: int | None
    sha256: str
    title: str
    role: str
    disposition: str
    superseded_by: str
    notes: str
    nearest_text_neighbor: str
    text_similarity: float | None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def balanced_brace_value(text: str, start: int) -> str:
    depth = 1
    chars: list[str] = []
    for char in text[start:]:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                break
        chars.append(char)
    return "".join(chars)


def clean_latex(value: str) -> str:
    value = re.sub(r"%.*", " ", value)
    value = re.sub(r"\\\\", " ", value)
    value = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", value)
    value = value.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", value).strip()


def tex_title(path: Path) -> str:
    if path.suffix.lower() != ".tex":
        return ""
    text = read_text(path)
    match = re.search(r"\\title\s*\{", text)
    if not match:
        return ""
    return clean_latex(balanced_brace_value(text, match.end()))


def normalized_shingles(path: Path) -> set[str]:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return set()
    text = read_text(path)
    text = re.sub(r"%.*", " ", text)
    tokens = re.findall(r"[a-zA-Z0-9_:+-]+", text.lower())
    if not tokens:
        return set()
    if len(tokens) < 5:
        return set(tokens)
    return {" ".join(tokens[index : index + 5]) for index in range(len(tokens) - 4)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def similarity_maps(paths: list[Path]) -> tuple[dict[str, tuple[str, float]], list[dict[str, object]]]:
    shingles = {path.name: normalized_shingles(path) for path in paths}
    nearest: dict[str, tuple[str, float]] = {}
    pairs: list[dict[str, object]] = []

    names = sorted(shingles)
    for index, name in enumerate(names):
        best_name = ""
        best_score = 0.0
        for other in names:
            if other == name:
                continue
            score = jaccard(shingles[name], shingles[other])
            if score > best_score:
                best_name = other
                best_score = score
        if best_name:
            nearest[name] = (best_name, best_score)

        for other in names[index + 1 :]:
            score = jaccard(shingles[name], shingles[other])
            pairs.append({"a": name, "b": other, "similarity": round(score, 4)})

    pairs.sort(key=lambda item: (-float(item["similarity"]), str(item["a"]), str(item["b"])))
    return nearest, pairs[:12]


def build_manifest(root: Path) -> dict[str, object]:
    archive_dir = root / ARCHIVE_ROOT
    files = sorted(path for path in archive_dir.iterdir() if path.is_file())
    text_files = [path for path in files if path.suffix.lower() in TEXT_SUFFIXES]
    nearest, similar_pairs = similarity_maps(text_files)

    records: list[ArchiveRecord] = []
    unclassified: list[str] = []
    for path in files:
        policy = ARCHIVE_POLICIES.get(path.name)
        if policy is None:
            unclassified.append(path.name)
            policy = {
                "role": "unclassified",
                "disposition": "unclassified",
                "superseded_by": "",
                "notes": "Add an explicit archive policy for this file.",
            }

        text = read_text(path) if path.suffix.lower() in TEXT_SUFFIXES else ""
        neighbor_name, score = nearest.get(path.name, ("", 0.0))
        records.append(
            ArchiveRecord(
                path=(ARCHIVE_ROOT / path.name).as_posix(),
                suffix=path.suffix.lower() or "<none>",
                size_bytes=path.stat().st_size,
                lines=len(text.splitlines()) if text else None,
                sha256=sha256(path),
                title=tex_title(path),
                role=str(policy["role"]),
                disposition=str(policy["disposition"]),
                superseded_by=str(policy["superseded_by"]),
                notes=str(policy["notes"]),
                nearest_text_neighbor=(
                    (ARCHIVE_ROOT / neighbor_name).as_posix() if neighbor_name else ""
                ),
                text_similarity=round(score, 4) if neighbor_name else None,
            )
        )

    dispositions = Counter(record.disposition for record in records)
    return {
        "root": ".",
        "archive_root": ARCHIVE_ROOT.as_posix(),
        "policy_coverage": {
            "files": len(records),
            "classified": len(records) - len(unclassified),
            "unclassified": unclassified,
        },
        "dispositions": dict(sorted(dispositions.items())),
        "files": [asdict(record) for record in records],
        "similar_text_pairs": similar_pairs,
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
    lines.extend("| " + " | ".join(table_escape(item) for item in row) + " |" for row in rows)
    return "\n".join(lines)


def render_markdown(manifest: dict[str, object]) -> str:
    coverage = manifest["policy_coverage"]
    files = manifest["files"]
    dispositions = manifest["dispositions"]
    text_files = [record for record in files if record["suffix"] in TEXT_SUFFIXES]

    lines: list[str] = [
        "# Paper Archive Manifest",
        "",
        "Generated by `python scripts/build_paper_archive_manifest.py --output docs/audits/paper-archive-manifest.md`.",
        "This file classifies every root-level file under `paper/neurips-submission/archive/` so agents can distinguish active anchors, retained references, and superseded drafts.",
        "",
        "## Summary",
        "",
        f"- Archive root: `{manifest['archive_root']}`",
        f"- Files classified: `{coverage['classified']}/{coverage['files']}`",
        f"- Text sources compared: `{len(text_files)}`",
        "",
        "## Disposition Counts",
        "",
        markdown_table(
            ["Disposition", "Files"],
            [[f"`{name}`", count] for name, count in dispositions.items()],
        ),
        "",
        "## File Policy",
        "",
        markdown_table(
            [
                "File",
                "Type",
                "Lines",
                "Size",
                "Role",
                "Disposition",
                "Superseded By",
                "Nearest Text Neighbor",
                "Similarity",
            ],
            [
                [
                    f"`{record['path']}`",
                    f"`{record['suffix']}`",
                    record["lines"],
                    human_size(int(record["size_bytes"])),
                    record["role"],
                    f"`{record['disposition']}`",
                    record["superseded_by"],
                    f"`{record['nearest_text_neighbor']}`"
                    if record["nearest_text_neighbor"]
                    else "",
                    f"{float(record['text_similarity']):.2%}"
                    if record["text_similarity"] is not None
                    else "",
                ]
                for record in files
            ],
        ),
        "",
        "## Notes",
        "",
    ]
    for record in files:
        lines.append(f"- `{record['path']}`: {record['notes']}")

    similar_pairs = manifest["similar_text_pairs"]
    if similar_pairs:
        lines.extend(["", "## Closest Text Pairs", ""])
        lines.append(
            markdown_table(
                ["A", "B", "Similarity"],
                [
                    [
                        f"`{ARCHIVE_ROOT / str(pair['a'])}`",
                        f"`{ARCHIVE_ROOT / str(pair['b'])}`",
                        f"{float(pair['similarity']):.2%}",
                    ]
                    for pair in similar_pairs
                ],
            )
        )

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
