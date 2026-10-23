"""Pinned, standard-library BigCodeBench subset and sandbox reference audit."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import warnings

from .verification import SandboxVerifier, sandbox_profile, visible_examples


REVISION = "b74c0d0bf70d2c0bc459be537895cca163007f1a"
PARQUET_SHA256 = "d9a4965821c9507ebdfb551c288656b2d5fe553234f5183044333ca8a4018267"
DATA_FILE = "data/v0.1.4-00000-of-00001.parquet"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stdlib_task(task: dict) -> bool:
    imports = set()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        for source in (task["complete_prompt"], task["code_prompt"] + task["canonical_solution"], task["test"]):
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Import):
                    imports.update(x.name.split(".")[0] for x in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
    return not (imports - set(sys.stdlib_module_names) - {"__future__"})


def shingles(prompt: str) -> set[tuple]:
    words = re.findall(r"[a-z]+", prompt.lower())
    return {tuple(words[i:i + 5]) for i in range(len(words) - 4)}


def similarity(a: set, b: set) -> float:
    return len(a & b) / max(1, len(a | b))


class BigCodeVerifier(SandboxVerifier):
    def check(self, problem: dict, solution: str, mode: str, seed: int = 20261026) -> dict:
        if mode == "probe":
            return super().check(problem, solution, mode)
        if mode not in {"visible", "heldout"}:
            raise ValueError("Unknown BigCodeBench verifier mode")
        safe_problem = ({"prompt": problem["complete_prompt"], "entry_point": problem["entry_point"]}
                        if mode == "visible" else {"test": problem["test"]})
        with tempfile.TemporaryDirectory(prefix="bigcode-verifier-") as temp:
            work = Path(temp)
            env = {"PATH": "/usr/bin:/bin", "HOME": temp, "TMPDIR": temp,
                   "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
            command = ["sandbox-exec", "-p", sandbox_profile(work), sys.executable, "-I",
                       str(Path(__file__).with_name("bigcode_worker.py"))]
            try:
                result = subprocess.run(command, input=json.dumps({"problem": safe_problem,
                    "solution": solution, "mode": mode, "seed": seed}), text=True,
                    capture_output=True, timeout=self.timeout, cwd=work, env=env)
            except subprocess.TimeoutExpired:
                return {"passed": False, "status": "timeout", "feedback": "Public verification timed out"} if mode == "visible" else {"passed": False, "status": "timeout"}
            try:
                payload = json.loads(result.stdout)
            except ValueError:
                # Malformed generated code may exit the child without a result.
                return {"passed": False, "status": "worker_exit", "returncode": result.returncode}
            if not isinstance(payload.get("passed"), bool):
                raise RuntimeError("Malformed BigCodeBench verifier result")
            return payload


def audit_tasks(rows: list[dict], output: Path, prior_prompts: list[str], workers: int = 4) -> dict:
    """Eligibility depends only on requirements, references and prompt similarity."""
    verifier = BigCodeVerifier(timeout=15)
    probe = verifier.preflight()
    prior = [shingles(p) for p in prior_prompts]
    candidates = []
    decisions = []
    for task in sorted(rows, key=lambda t: int(t["task_id"].split("/")[-1])):
        reason = None
        if not stdlib_task(task):
            reason = "external_dependency"
        elif visible_examples(task["complete_prompt"]) == 0:
            reason = "no_public_doctests"
        elif any(similarity(shingles(task["complete_prompt"]), p) >= .60 for p in prior):
            reason = "prior_prompt_near_duplicate"
        if reason:
            decisions.append({"task_id": task["task_id"], "eligible": False, "reason": reason})
        else:
            candidates.append(task)

    def reference(task):
        solution = task["code_prompt"] + task["canonical_solution"]
        checks = [{"seed": seed, "visible": verifier.check(task, solution, "visible", seed),
                   "heldout": verifier.check(task, solution, "heldout", seed)} for seed in (20261026, 20261027)]
        return {"task_id": task["task_id"], "eligible": all(
            c[mode]["passed"] for c in checks for mode in ("visible", "heldout")), "checks": checks}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        decisions.extend(pool.map(reference, candidates))
    accepted = []
    task_map = {t["task_id"]: t for t in rows}
    accepted_shingles = []
    for row in sorted(decisions, key=lambda r: int(r["task_id"].split("/")[-1])):
        if row["eligible"]:
            prompt_shingles = shingles(task_map[row["task_id"]]["complete_prompt"])
            if any(similarity(prompt_shingles, p) >= .60 for p in accepted_shingles):
                row.update(eligible=False, reason="within_pool_prompt_near_duplicate")
            else:
                accepted.append(row["task_id"])
                accepted_shingles.append(prompt_shingles)
    random.Random(20261026).shuffle(accepted)
    output.mkdir(parents=True, exist_ok=False)
    (output / "reference-audit.json").write_text(json.dumps({"probe": probe, "decisions": decisions}, indent=2) + "\n")
    selected = accepted[:200]
    (output / "tasks.json").write_text(json.dumps([task_map[t] for t in selected], indent=2) + "\n")
    summary = {"dataset_revision": REVISION, "raw_tasks": len(rows), "reference_candidates": len(candidates),
               "eligible_tasks": len(accepted), "selected_tasks": len(selected), "selected_task_ids": selected,
               "tasks_sha256": sha(output / "tasks.json"), "audit_sha256": sha(output / "reference-audit.json"),
               "python": sys.version, "prior_prompt_count": len(prior_prompts),
               "qualification": "New to this project; public benchmark, training contamination not ruled out. Standard-library, reference-valid subset only."}
    (output / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
