"""Conservative, reproducible development-exposure guard; never certifies a holdout."""

from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
BASE = "experiments/python-repair/checkpoint-environment"
SOURCES = {
    "screening": BASE + "/development/screening.json",
    "pool": BASE + "/development/pool.json",
    "extension": BASE + "/development-extension/pool.json",
    "broader": BASE + "/development-broader/pool.json",
    "stateful": BASE + "/development-stateful/pool.json",
    "ablation_components": BASE + "/development-ablation-components/pool.json",
    "notes": BASE + "/development/exposure-notes.json",
    "ablation": BASE + "/results/spectrum-ablation-preparation-20261030/source-screen.json",
}
REGISTRY = BASE + "/development/exposure-registry.json"


def normalize(bug_id: str) -> str:
    """Case and zero padding must not let an exposed bug bypass the guard."""
    if not isinstance(bug_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*/[0-9]+", bug_id):
        raise ValueError("Expected a BugsInPy project/positive-integer ID")
    project, number = bug_id.split("/")
    if int(number) < 1:
        raise ValueError("Bug numbers must be positive")
    return project.casefold() + "/" + str(int(number))


def build(root: Path = ROOT) -> dict:
    raw = {k: (root / path).read_bytes() for k, path in SOURCES.items()}
    data = {k: json.loads(value) for k, value in raw.items()}
    evidence = defaultdict(list)

    def add(bug_id, source, level):
        item = {"source": SOURCES[source], "level": level}
        key = normalize(bug_id)
        if item not in evidence[key]:
            evidence[key].append(item)

    for row in data["screening"]["screened"]:
        add(row["id"], "screening", "patch_header_inspection")
    for row in data["screening"]["detailed_exclusions"]:
        add(row["id"], "screening", "documented_detailed_exclusion")
    for source in ("pool", "extension", "broader", "stateful", "ablation_components"):
        for row in data[source]["tasks"]:
            if row["split"] != "development":
                raise ValueError("Inspected source pool cannot be relabelled as evaluation")
            add(row["provenance"]["benchmark_id"], source, "published_development_adapter")
    for row in data["notes"]["inspections"]:
        if row["level"] not in {"metadata_inspection", "patch_inspection"}:
            raise ValueError("Unknown supplemental exposure type")
        add(row["id"], "notes", row["level"])
    for row in data["ablation"]["inspections"]:
        if row['level'] != 'patch_inspection':
            raise ValueError('Unknown ablation source-screen exposure type')
        add(row['id'], 'ablation', row['level'])
    return {
        "schema_version": 1,
        "kind": "minimum_documented_development_exposure_not_holdout_selection",
        "benchmark_revision": data["screening"]["benchmark_revision"],
        "sources": {SOURCES[k]: hashlib.sha256(value).hexdigest() for k, value in raw.items()},
        "known_exposed_ids": sorted(evidence),
        "known_exposed_bug_count": len(evidence),
        "known_exposed_projects": sorted({key.split('/')[0] for key in evidence}),
        "project_counts": dict(sorted(Counter(key.split('/')[0] for key in evidence).items())),
        "exposure_evidence": dict(sorted(evidence.items())),
        "rules": [
            "All listed bugs and their variants are development-exposed, including metadata-only inspection.",
            "A project-disjoint evaluation must exclude every listed project.",
            "Absence is not evidence of no inspection, pretraining contamination or function-family overlap.",
            "No evaluation cases are selected or certified by this registry.",
        ],
        "api_calls": 0,
    }


def assess_candidate(registry: dict, bug_id: str, *, project_disjoint: bool) -> str:
    key = normalize(bug_id)
    if key in registry["known_exposed_ids"]:
        return "reject_known_development_bug"
    if project_disjoint and key.split('/')[0] in registry["known_exposed_projects"]:
        return "reject_exposed_project"
    return "not_known_exposed_further_audit_required"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Regenerate the tracked registry from its sources")
    parser.add_argument("--candidate", help="Check one ID, without selecting an evaluation case")
    parser.add_argument("--project-disjoint", action="store_true")
    args = parser.parse_args()
    registry = build()
    path = ROOT / REGISTRY
    if args.write:
        path.write_text(json.dumps(registry, indent=2) + "\n")
    elif json.loads(path.read_text()) != registry:
        raise ValueError("Exposure registry differs from its source records; regenerate and review")
    result = {k: registry[k] for k in ("known_exposed_bug_count", "known_exposed_projects", "api_calls")}
    if args.candidate:
        result["candidate"] = normalize(args.candidate)
        result["decision"] = assess_candidate(registry, args.candidate, project_disjoint=args.project_disjoint)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
