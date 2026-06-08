"""Download leakage-safe SWE-bench metadata for orchestration experiments."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vao.swebench_orchestration.schemas import SWEInstancePublic

DEFAULT_DATASET = "princeton-nlp/SWE-Bench_Verified"
GOLD_FIELDS = {
    "patch",
    "test_patch",
    "resolved_by",
    "solution",
    "gold_patch",
}


def _load_dataset(dataset_name: str, split: str) -> Any:
    try:
        from datasets import load_dataset
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency `datasets`. Install project dependencies or run "
            "`.venv/bin/python -m pip install datasets pyarrow`."
        ) from exc
    return load_dataset(dataset_name, split=split)


def _json_default(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return str(value)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=_json_default) + "\n")


def _infer_mode(row: dict[str, Any]) -> str:
    repo = str(row.get("repo") or "").lower()
    problem = str(row.get("problem_statement") or "").lower()
    hints = str(row.get("hints_text") or "").lower()
    text = f"{problem}\n{hints}"
    if any(key in text for key in ("importerror", "dependency", "version", "configuration", "config")):
        return "dependency_config"
    if any(key in text for key in ("nan", "precision", "numeric", "sympy", "equation", "symbolic")) or "sympy" in repo:
        return "numeric_symbolic"
    if any(key in text for key in ("api", "attributeerror", "typeerror", "behavior", "semantics")):
        return "semantic_api"
    if any(key in text for key in ("multiple files", "refactor", "across", "integration")):
        return "multi_file"
    if any(key in text for key in ("test", "failing", "traceback", "assert")):
        return "test_localizable"
    return "repo_family"


def _public_record(row: dict[str, Any], *, include_hints: bool) -> dict[str, Any]:
    public = SWEInstancePublic(
        instance_id=str(row.get("instance_id")),
        repo=str(row.get("repo")),
        base_commit=row.get("base_commit"),
        problem_statement=str(row.get("problem_statement") or ""),
        hints_text=row.get("hints_text") if include_hints else None,
        created_at=row.get("created_at"),
        version=row.get("version"),
        declared_mode=_infer_mode(row),
        public_fields={
            "FAIL_TO_PASS_count": len(row.get("FAIL_TO_PASS") or []),
            "PASS_TO_PASS_count": len(row.get("PASS_TO_PASS") or []),
            "hints_text_available": bool(row.get("hints_text")),
            "hints_text_included": include_hints,
        },
    )
    return public.model_dump()


def _private_record(row: dict[str, Any], *, include_gold_patches: bool) -> dict[str, Any]:
    kept = dict(row)
    if not include_gold_patches:
        for field in GOLD_FIELDS:
            kept.pop(field, None)
    kept["declared_mode"] = _infer_mode(row)
    return kept


def _select_rows(dataset: Any, *, limit: int, seed: int, repos: set[str] | None) -> list[dict[str, Any]]:
    rows = [dict(item) for item in dataset]
    if repos:
        rows = [row for row in rows if str(row.get("repo")) in repos]
    rng = random.Random(seed)
    rng.shuffle(rows)
    if limit > 0:
        rows = rows[:limit]
    rows.sort(key=lambda row: str(row.get("instance_id")))
    return rows


def download_slice(
    *,
    dataset_name: str,
    split: str,
    output_dir: Path,
    limit: int,
    seed: int,
    repos: set[str] | None,
    include_gold_patches: bool,
    include_hints: bool,
) -> dict[str, Any]:
    dataset = _load_dataset(dataset_name, split)
    rows = _select_rows(dataset, limit=limit, seed=seed, repos=repos)
    public_rows = [_public_record(row, include_hints=include_hints) for row in rows]
    private_rows = [_private_record(row, include_gold_patches=include_gold_patches) for row in rows]

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "instances_public.jsonl", public_rows)
    _write_jsonl(output_dir / "instances_private_metadata.jsonl", private_rows)
    manifest = {
        "dataset_name": dataset_name,
        "split": split,
        "limit": limit,
        "seed": seed,
        "repos": sorted(repos) if repos else None,
        "include_gold_patches": include_gold_patches,
        "include_hints_in_public": include_hints,
        "row_count": len(rows),
        "instance_ids": [row["instance_id"] for row in public_rows],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            "public": str(output_dir / "instances_public.jsonl"),
            "private_metadata": str(output_dir / "instances_private_metadata.jsonl"),
        },
    }
    (output_dir / "download_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET)
    parser.add_argument("--split", default="test")
    parser.add_argument("--output-dir", default="swebench/studies/open_source_orchestration/data/dev_slice")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260605)
    parser.add_argument("--repos", default=None, help="Comma-separated repo filter, e.g. django/django,sympy/sympy")
    parser.add_argument("--include-gold-patches", action="store_true")
    parser.add_argument("--include-hints", action="store_true", help="Include SWE-bench hints_text in prompt-safe public records")
    args = parser.parse_args(argv)

    repos = {item.strip() for item in args.repos.split(",") if item.strip()} if args.repos else None
    manifest = download_slice(
        dataset_name=args.dataset_name,
        split=args.split,
        output_dir=Path(args.output_dir),
        limit=args.limit,
        seed=args.seed,
        repos=repos,
        include_gold_patches=args.include_gold_patches,
        include_hints=args.include_hints,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
