"""Audit terminal false positives; optionally collect offline public-only traces.

The case audit deliberately inspects evaluator outcomes after the old study is
closed. The trace adapter receives only each public task and saved JSON artifact.
All twelve JSON candidates are retained; evaluator results never select probes.
"""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from vao.repair.diagnostics import ARMS, acquire, observe, project
from vao.repair.environment import canonical
from vao.repair.verifier import RepairVerifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace-public", action="store_true", help="Execute saved JSON artifacts in OS sandboxes; no API")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent / "contract-gemma27b-20261026"
    archive = source / "evidence.zip"
    manifest = json.loads((source / "evidence-manifest.json").read_text())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != manifest["archive_sha256"]:
        raise ValueError("Archive hash mismatch")
    facts, public_candidates = [], []
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist()) != len(set(z.namelist())) or set(z.namelist()) != set(manifest["files"]):
            raise ValueError("Archive members differ")
        for name, expected in manifest["files"].items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise ValueError("Archive member hash mismatch")
        packet = json.loads(z.read("collection/manifest.json"))["freeze"]["packet"]
        rows = [json.loads(line) for line in z.read("collection/observations.jsonl").splitlines()]
        if len(rows) != 36 or len({r["attempt_id"] for r in rows}) != 36:
            raise ValueError("Expected complete original bank")
        for row in rows:
            task = packet["tasks"][row["task_index"]]
            prefix = f"collection/cells/{row['attempt_id']}/objects/"
            def obj(key):
                return json.loads(z.read(prefix + key + ".json"))
            if row["contract"] == "json_current":
                public_candidates.append((row["attempt_id"], task["public"],
                                          obj(row["artifact"])["files"] if row["artifact"] else None))
            if row["public"] is None or not obj(row["public"])["result"]["passed"] or row["full_pass"]:
                continue
            evaluator = obj(row["evaluator"])["result"]
            cases = {c["id"]: c for c in task["evaluator"]["cases"]}
            facts.append({"attempt_id": row["attempt_id"], "task": task["public"]["task_id"],
                          "contract": row["contract"], "specification": task["public"]["instruction"],
                          "failures": [{"case": cases[r["id"]], "observed": r["observed"]}
                                       for r in evaluator["cases"] if not r["passed"]]})
    result = {"post_hoc": True, "model_calls": 0, "archive_sha256": digest,
              "false_positive_outputs": len(facts), "distinct_false_positive_bugs": len({r["task"] for r in facts}),
              "records": sorted(facts, key=lambda r: r["attempt_id"])}
    if args.trace_public:
        verifier = RepairVerifier()
        result["preflight"] = verifier.preflight()
        probes = []
        for attempt_id, public, files in sorted(public_candidates):
            row = {"attempt_id": attempt_id, "task_id": public["task_id"]}
            if files is None:
                row["status"] = "no_artifact"
            else:
                state = observe(public, files, verifier)
                diagnostic = acquire(public, files, state, verifier)
                projections = {a: project(public, files, state, a, diagnostic) for a in ARMS}
                row.update(status="observed", observation=state, diagnostic=diagnostic,
                           request_sha256={a: hashlib.sha256(canonical(r).encode()).hexdigest()
                                           for a, r in projections.items()})
            probes.append(row)
        result["public_probes"] = probes
        result["probe_summary"] = {"candidates_retained": len(probes),
            "traces_available": sum(p.get("diagnostic", {}).get("available", False) for p in probes),
            "no_public_failure": sum(p.get("diagnostic", {}).get("reason") == "no_public_failure" for p in probes),
            "additional_executions": sum(p.get("diagnostic", {}).get("additional_executions", 0) for p in probes)}
        root = Path(__file__).resolve().parents[5]
        result["source_sha256"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("src/vao/repair/diagnostics.py", "src/vao/repair/trace_worker.py", "src/vao/repair/verifier.py")}
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"false_positive_outputs": len(facts), "probe_summary": result.get("probe_summary"), "model_calls": 0}))


if __name__ == "__main__":
    main()
