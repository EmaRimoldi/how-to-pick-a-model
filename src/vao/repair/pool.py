"""Build and qualify a published development pool without executing upstream setup."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .cli import qualify, source_manifest
from .environment import RepairTask, audit_run, canonical


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Invalid pool source: {relative}")
    return path


def read_pool(root: Path) -> list[tuple[str, RepairTask, dict]]:
    """Verify inert excerpts/licenses and build task objects, never import source."""
    pool = json.loads((root / "pool.json").read_text())
    if pool["schema_version"] != 1 or pool["status"] != "development_only":
        raise ValueError("Expected a development pool")
    rows, ids = [], set()
    for item in pool["tasks"]:
        slug = item["id"]
        if slug in ids or not slug or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in slug):
            raise ValueError("Invalid or duplicate task ID")
        ids.add(slug)
        if item["split"] != "development":
            raise ValueError("Inspected tasks must remain development data")
        sources = item["provenance"]["sources"]
        for info in sources.values():
            if "excerpt" in info:
                path = local_file(root, info["excerpt"])
                if sha256(path) != info["excerpt_sha256"]:
                    raise ValueError(f"Excerpt hash mismatch: {slug}")
            if "local_path" in info and sha256(local_file(root, info["local_path"])) != info["sha256"]:
                raise ValueError(f"License hash mismatch: {slug}")
        files = {}
        for role in ("buggy", "fixed"):
            body = local_file(root, sources[role]["excerpt"]).read_text()
            files[role] = {"solution.py": item["prefix"] + body + "\n\n" + item["wrappers"][role]}
        public_inputs = {canonical([c["args"], c.get("kwargs", {})]) for c in item["public_cases"]}
        evaluator_inputs = {canonical([c["args"], c.get("kwargs", {})]) for c in item["evaluator_cases"]}
        if public_inputs & evaluator_inputs:
            raise ValueError(f"Public/evaluator inputs overlap: {slug}")
        if files["buggy"] == files["fixed"]:
            raise ValueError(f"Identical initial/reference source: {slug}")
        task = RepairTask.from_dicts({
            "schema_version": 1, "task_id": "development/bugsinpy-adapted/" + slug,
            "instruction": item["instruction"], "entrypoint": {"module": "solution", "function": "solve"},
            "files": files["buggy"], "public_cases": item["public_cases"],
            "provenance": item["provenance"],
        }, {"cases": item["evaluator_cases"]})
        task.validate_artifact(files["fixed"])
        rows.append((slug, task, files["fixed"]))
    if not rows:
        raise ValueError("Empty development pool")
    return rows


def audit_sources(root: Path, cache: Path) -> dict:
    """Check downloaded full-file bytes and exact extraction ranges, offline."""
    read_pool(root)
    pool = json.loads((root / "pool.json").read_text())
    checked = 0
    for item in pool["tasks"]:
        provenance = item["provenance"]
        for role, info in provenance["sources"].items():
            path = local_file(cache, provenance["benchmark_id"] + "/" + role + ".txt")
            if sha256(path) != info["sha256"]:
                raise ValueError(f"Upstream source mismatch: {item['id']}/{role}")
            if "excerpt" in info:
                lines = path.read_text().splitlines(keepends=True)
                slices = []
                for segment in info["segments"]:
                    text = "".join(lines[segment["start_line"] - 1:segment["end_line"]])
                    if hashlib.sha256(text.encode()).hexdigest() != segment["sha256"]:
                        raise ValueError("Upstream segment mismatch")
                    slices.append(text)
                if "\n\n".join(slices) != local_file(root, info["excerpt"]).read_text():
                    raise ValueError("Extraction differs from upstream")
            checked += 1
    return {"full_files_verified": checked, "excerpts_match_upstream": True,
            "pool_sha256": sha256(root / "pool.json"), "api_calls": 0}


def write_json(path: Path, value: dict) -> None:
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build_pool(root: Path, output: Path) -> list[Path]:
    rows = read_pool(root)
    output.mkdir(parents=True, exist_ok=False)
    bundles = []
    for slug, task, reference in rows:
        bundle = output / slug
        bundle.mkdir()
        write_json(bundle / "task.json", task.public)
        write_json(bundle / "evaluator.json", json.loads(task.evaluator_json))
        write_json(bundle / "reference.json", reference)
        bundles.append(bundle)
    return bundles


def qualify_pool(root: Path, output: Path) -> dict:
    """Keep all technical failures; seal a report only after every task finishes."""
    pool_hash = sha256(root / "pool.json")
    read_pool(root)
    output.mkdir(parents=True, exist_ok=False)
    bundles = build_pool(root, output / "bundles")
    runtime = source_manifest(bundles[0])
    checks = []
    for bundle in bundles:
        run = output / "runs" / bundle.name
        result = qualify(bundle, run)
        # Qualification deliberately ignores variable timing in repeated outcomes.
        observations = {}
        for path in sorted((run / "objects").glob("*.json")):
            obj = json.loads(path.read_text())
            if obj.get("kind") == "evaluation":
                observations.setdefault(obj["artifact"], {})[obj["channel"]] = obj["result"]
        task = RepairTask.load(bundle)
        # Resolve artifact labels from saved files, not assumptions about hash format.
        artifacts = {}
        for path in (run / "objects").glob("*.json"):
            obj = json.loads(path.read_text())
            if obj.get("kind") == "artifact":
                artifacts[path.stem] = "initial" if obj["files"] == task.public["files"] else "reference"
        compact = {}
        for artifact, channels in observations.items():
            compact[artifacts[artifact]] = {
                channel: {"passed_cases": r["passed_cases"], "total_cases": r["total_cases"],
                          "cases": r["cases"]} for channel, r in channels.items()}
        checks.append({"id": bundle.name, "task_hash": result["task_hash"],
                       "engineering_qualified": result["engineering_qualified"],
                       "checks": result["checks"], "outcomes": compact,
                       "completion_sha256": sha256(run / "completion.json"), "audit": audit_run(run)})
        print(json.dumps({"task": bundle.name, "engineering_qualified": result["engineering_qualified"]}), flush=True)
    if sha256(root / "pool.json") != pool_hash or source_manifest(bundles[0]) != runtime:
        raise ValueError("Pool or runtime changed during qualification")
    read_pool(root)
    report = {"schema_version": 1, "status": "offline_development_qualification",
              "created_utc": datetime.now(timezone.utc).isoformat(), "pool_sha256": pool_hash,
              "runtime": runtime, "selected": len(checks),
              "qualified": sum(r["engineering_qualified"] for r in checks), "tasks": checks,
              "api_calls": 0, "api_spend_usd": "0", "model_results": False, "evaluation_ready": False,
              "limitations": ["Adapted function-level bugs, not official BugsInPy scores.",
                              "Both finite suites are published development data; not exhaustive correctness.",
                              "No model difficulty, recoverability, generalization or action-value evidence."]}
    write_json(output / "qualification.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "build", "audit-sources", "qualify"), nargs="?", default="plan")
    parser.add_argument("--pool", type=Path, default=Path("experiments/python-repair/checkpoint-environment/development"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-cache", type=Path)
    args = parser.parse_args()
    if args.action == "plan":
        result = {"tasks": len(read_pool(args.pool)), "api_calls": 0, "mode": "plan_only", "split": "development"}
    elif args.action == "audit-sources":
        if not args.source_cache:
            parser.error("audit-sources requires --source-cache")
        result = audit_sources(args.pool, args.source_cache)
    else:
        if not args.output:
            parser.error("build/qualify require a fresh --output directory")
        if args.action == "build":
            result = {"bundles": [str(p) for p in build_pool(args.pool, args.output)], "api_calls": 0}
        else:
            report = qualify_pool(args.pool, args.output)
            result = {k: report[k] for k in ("selected", "qualified", "api_calls", "api_spend_usd")}
    print(json.dumps(result, indent=2))
    return int("qualified" in result and result["qualified"] != result["selected"])


if __name__ == "__main__":
    raise SystemExit(main())
