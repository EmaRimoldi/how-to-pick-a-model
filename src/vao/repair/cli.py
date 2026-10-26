"""Plan, demonstrate, qualify and audit the offline Python repair environment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

from .environment import RepairRun, RepairTask, audit_run
from .verifier import RepairVerifier


def source_manifest(bundle: Path) -> dict:
    """Fingerprint the exact runtime and fixture bytes used for an engineering run."""
    files = {"runtime/" + p.name: p for p in Path(__file__).parent.glob("*.py")}
    from vao.decisions import verification
    files["runtime/verification.py"] = Path(verification.__file__)
    files.update({"fixture/" + p.name: p for p in bundle.glob("*.json")})
    return {"python": sys.version, "platform": platform.platform(),
            "sha256": {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in sorted(files.items())}}


def finish(run: RepairRun, bundle: Path, provenance: dict, report: dict) -> dict:
    """Seal the run without using the historical collectors' completion filename."""
    if source_manifest(bundle) != provenance:
        raise ValueError("Runtime or fixture changed during the engineering run")
    report.update(mode="offline_engineering", api_calls=0, api_spend_usd="0",
                  model_results=False, provenance=provenance, audit=audit_run(run.root))
    with (run.root / "completion.json").open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    audit_run(run.root)
    return report


def qualify(bundle: Path, output: Path) -> dict:
    """Require repeatable initial failures and a reference passing both test suites."""
    provenance = source_manifest(bundle)
    task = RepairTask.load(bundle)
    reference = json.loads((bundle / "reference.json").read_text())
    task.validate_artifact(reference)
    verifier = RepairVerifier()
    probe = verifier.preflight()
    run = RepairRun(output, task, verifier)
    artifacts = {"initial": run.initial, "reference": run.snapshot(reference)}
    checks = {}
    for label, artifact in artifacts.items():
        checks[label] = {}
        for channel in ("public", "evaluator"):
            rows = [run.get(run.evaluate(artifact, channel))["result"] for _ in range(2)]
            checks[label][channel] = {"passed": [r["passed"] for r in rows],
                                      "repeatable": rows[0]["cases"] == rows[1]["cases"]}
    stable = all(row["repeatable"] for channels in checks.values() for row in channels.values())
    discriminates = all(checks["initial"][c]["passed"] == [False, False]
                        and checks["reference"][c]["passed"] == [True, True] for c in ("public", "evaluator"))
    return finish(run, bundle, provenance, {"task": task.public["task_id"], "task_hash": task.task_hash,
                                "task_provenance": task.public["provenance"], "probe": probe,
                                "checks": checks, "engineering_qualified": stable and discriminates,
                                "evaluation_ready": False,
                                "limitation": "Qualification checks the harness, not model difficulty, contamination, test completeness or recoverability."})


def demo(bundle: Path, output: Path) -> dict:
    """Exercise forks and rollback using labeled handwritten development attempts."""
    provenance = source_manifest(bundle)
    task = RepairTask.load(bundle)
    if task.public["provenance"]["kind"] != "synthetic_engineering_fixture":
        raise ValueError("Demo accepts only labeled engineering fixtures")
    scripted = json.loads((bundle / "scripted-attempts.json").read_text())
    reference = json.loads((bundle / "reference.json").read_text())
    verifier = RepairVerifier()
    probe = verifier.preflight()
    run = RepairRun(output, task, verifier)
    checkpoint = None
    checkpoints, progression = [], []
    for label, files in [("initial", task.public["files"]), *scripted.items()]:
        artifact = run.snapshot(files)
        evaluation = run.evaluate(artifact, "public")
        checkpoint = run.checkpoint(artifact, evaluation, checkpoint)
        checkpoints.append(checkpoint)
        progression.append({"label": label, "checkpoint": checkpoint,
                            "passed_cases": run.get(evaluation)["result"]["passed_cases"]})
    branches = {}
    for action in ("continue", "restart"):
        branch = run.fork(checkpoint, action, "0.01")
        request = run.request(branch)
        branch_record = run.get(branch)
        workspace = run.materialize(branch_record["starting_artifact"], action)
        # Both arms receive the same handwritten final repair. These are not LLM draws.
        result_artifact = run.snapshot(reference)
        public = run.evaluate(result_artifact, "public")
        evaluator = run.evaluate(result_artifact, "evaluator")
        run.record("scripted_branch_result", [branch, result_artifact, public, evaluator],
                   {"origin": "handwritten_fixture", "model": None, "api_calls": 0})
        branches[action] = {"branch": branch, "starting_artifact": branch_record["starting_artifact"],
                            "workspace": workspace.relative_to(output).as_posix(), "request": request,
                            "public_pass": run.get(public)["result"]["passed"],
                            "evaluator_pass": run.get(evaluator)["result"]["passed"]}
    # Rollback is an engineering restore demonstration, not a third measured policy.
    rollback = run.get(checkpoints[1])["artifact"]
    run.materialize(rollback, "rollback-to-partial")
    return finish(run, bundle, provenance, {"task": task.public["task_id"], "probe": probe,
                                "progression": progression, "branches": branches,
                                "rollback_artifact": rollback, "evaluation_ready": False,
                                "limitation": "Handwritten engineering fixtures only. No efficacy estimate or model comparison."})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "demo", "qualify", "audit"), nargs="?", default="plan")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.action == "plan":
        result = {"mode": "plan_only", "api_calls": 0, "live_mode_available": False,
                  "actions": ["demo", "qualify", "audit"], "execution_backend": "macos-sandbox-exec",
                  "next_step": "Run the engineering demo, then qualify real function-level bug bundles before any model pilot."}
    elif args.action == "audit":
        if not args.input:
            parser.error("audit requires --input")
        result = audit_run(args.input)
    else:
        if not args.bundle or not args.output:
            parser.error("demo/qualify require --bundle and a fresh --output directory")
        result = (demo if args.action == "demo" else qualify)(args.bundle, args.output)
    print(json.dumps(result, indent=2))
    return 1 if result.get("engineering_qualified") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
