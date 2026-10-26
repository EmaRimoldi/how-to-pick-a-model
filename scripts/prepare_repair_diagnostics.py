"""Execute a public-only offline diagnostic demo; never dispatch model requests."""

import argparse
import hashlib
import json
from pathlib import Path

from vao.repair.diagnostics import ARMS, acquire, observe, project
from vao.repair.environment import identity
from vao.repair.verifier import RepairVerifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-task", type=Path, required=True, help="Public task.json only")
    parser.add_argument("--artifact", type=Path, help="Optional complete filename-to-source JSON")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    public = json.loads(args.public_task.read_text())
    files = json.loads(args.artifact.read_text()) if args.artifact else public["files"]
    args.output.mkdir(parents=True, exist_ok=False)
    verifier = RepairVerifier()
    preflight = verifier.preflight()
    observation = observe(public, files, verifier)
    diagnostic = acquire(public, files, observation, verifier)
    requests = {arm: project(public, files, observation, arm, diagnostic) for arm in ARMS}
    report = {"schema_version": 1, "kind": "offline_public_diagnostic_demo",
              "api_calls": 0, "model_results": False, "preflight": preflight,
              "public_task": public, "artifact": files, "observation": observation,
              "diagnostic": diagnostic, "requests": requests}
    source_root = Path(__file__).resolve().parents[1]
    report["source_sha256"] = {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
                              for name in ("src/vao/repair/diagnostics.py", "src/vao/repair/trace_worker.py",
                                           "src/vao/repair/verifier.py", "src/vao/repair/worker.py")}
    report["record_id"] = identity(report)
    (args.output / "diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "available": diagnostic["available"],
                      "reason": diagnostic["reason"], "api_calls": 0}))


if __name__ == "__main__":
    main()
