"""Store verifiable repair artifacts and fork matched continue/restart requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

REPAIR_SYSTEM = "Repair the supplied Python files. Return only a JSON object mapping each editable filename to its complete replacement source. Preserve the function interface. The latest feedback describes the preceding failed attempt; it may refer to a different file state from the files supplied here."


def canonical(value: object) -> str:
    """Encode finite JSON deterministically for identity and strict comparisons."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def identity(value: object) -> str:
    """Identify an immutable JSON value, including its type and provenance."""
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_files(files: dict) -> None:
    """Accept only a small, flat Python workspace, never arbitrary disk paths."""
    if not isinstance(files, dict) or not 1 <= len(files) <= 2:
        raise ValueError("A task must contain one or two Python files")
    for name, source in files.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*\.py", name):
            raise ValueError("Only flat Python module filenames are allowed")
        if PurePosixPath(name).is_absolute() or not isinstance(source, str):
            raise ValueError("Invalid workspace file")
        if len(source.encode()) > 65536:
            raise ValueError("Source file exceeds 64 KiB")


def validate_cases(cases: list) -> None:
    """Check JSON call/expectation contracts before executing any candidate."""
    if not isinstance(cases, list) or not cases:
        raise ValueError("Both public and evaluator suites must be nonempty")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) - {"id", "args", "kwargs", "expected", "raises"}:
            raise ValueError("Unknown case fields")
        if not isinstance(case.get("id"), str) or not case["id"] or case["id"] in ids:
            raise ValueError("Case identifiers must be unique nonempty strings")
        ids.add(case["id"])
        if not isinstance(case.get("args"), list) or not isinstance(case.get("kwargs", {}), dict):
            raise ValueError("Cases require an args array and optional kwargs object")
        if ("expected" in case) == ("raises" in case):
            raise ValueError("Exactly one expected value or exception is required")
        if "raises" in case and case["raises"] not in {"ValueError", "TypeError", "KeyError", "IndexError"}:
            raise ValueError("Unsupported expected exception")
        canonical(case)


@dataclass(frozen=True)
class RepairTask:
    """Validated development task; evaluator cases are never solver input."""

    public_json: str
    evaluator_json: str

    @classmethod
    def from_dicts(cls, public: dict, evaluator: dict) -> "RepairTask":
        if set(public) != {"schema_version", "task_id", "instruction", "entrypoint", "files", "public_cases", "provenance"}:
            raise ValueError("Unexpected public task schema")
        if public["schema_version"] != 1 or set(evaluator) != {"cases"}:
            raise ValueError("Unsupported task schema")
        if not all(isinstance(public[k], str) and public[k] for k in ("task_id", "instruction")):
            raise ValueError("Task identity and instruction are required")
        validate_files(public["files"])
        entry = public["entrypoint"]
        if set(entry) != {"module", "function"} or any(
            not isinstance(entry[k], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", entry[k]) for k in entry
        ) or entry["module"] + ".py" not in public["files"]:
            raise ValueError("Entrypoint must name a supplied module and function")
        validate_cases(public["public_cases"])
        validate_cases(evaluator["cases"])
        if not isinstance(public["provenance"], dict) or not public["provenance"].get("kind"):
            raise ValueError("Task provenance kind is required")
        return cls(canonical(public), canonical(evaluator))

    @classmethod
    def load(cls, bundle: Path) -> "RepairTask":
        """Load separate public and evaluator fixtures without running their code."""
        return cls.from_dicts(json.loads((bundle / "task.json").read_text()),
                              json.loads((bundle / "evaluator.json").read_text()))

    @property
    def public(self) -> dict:
        return json.loads(self.public_json)

    @property
    def task_hash(self) -> str:
        return identity({"public": self.public, "evaluator": json.loads(self.evaluator_json)})

    def cases(self, channel: str) -> list:
        """Select exactly one suite; public requests cannot contain evaluator cases."""
        if channel == "public":
            return self.public["public_cases"]
        if channel == "evaluator":
            return json.loads(self.evaluator_json)["cases"]
        raise ValueError("Unknown verification channel")

    def validate_artifact(self, files: dict) -> None:
        validate_files(files)
        if set(files) != set(self.public["files"]):
            raise ValueError("Candidate must replace exactly the declared editable files")


class RepairRun:
    """Single-writer artifact journal; transport and accounting remain external."""

    def __init__(self, root: Path, task: RepairTask, verifier, *, mode: str = "offline_engineering"):
        if mode not in {"offline_engineering", "scripted_pilot", "model_pilot"}:
            raise ValueError("Unknown run mode")
        self.mode = mode
        self.root, self.task, self.verifier = root, task, verifier
        root.mkdir(parents=True, exist_ok=False)
        for name in ("objects", "events", "workspaces"):
            (root / name).mkdir()
        self.sequence, self.previous = 0, None
        self.task_object = self.put({"kind": "task", "public": task.public,
                                     "evaluator": json.loads(task.evaluator_json)})
        self.initial = self.snapshot(task.public["files"])
        self.record("initialized", [self.task_object, self.initial], {"mode": mode})

    def put(self, value: dict) -> str:
        """Write once; identical objects are shared, corruption fails closed."""
        self._writable()
        key = identity(value)
        path = self.root / "objects" / (key + ".json")
        if path.exists():
            self.get(key)
        else:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(canonical(value) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        return key

    def get(self, key: str) -> dict:
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("Invalid object identity")
        value = json.loads((self.root / "objects" / (key + ".json")).read_text())
        if identity(value) != key:
            raise ValueError("Corrupt stored object")
        return value

    def record(self, action: str, refs: list[str], detail: dict) -> None:
        self._writable()
        for key in refs:
            self.get(key)
        event = {"sequence": self.sequence, "previous": self.previous, "action": action,
                 "objects": refs, "detail": detail, "utc": datetime.now(timezone.utc).isoformat()}
        event["hash"] = identity(event)
        with (self.root / "events" / f"{self.sequence:06d}.json").open("x") as stream:
            stream.write(canonical(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.sequence += 1
        self.previous = event["hash"]

    def _writable(self) -> None:
        if (self.root / "completion.json").exists():
            raise ValueError("Completed engineering runs are sealed")

    def snapshot(self, files: dict) -> str:
        self.task.validate_artifact(files)
        return self.put({"kind": "artifact", "task": self.task.task_hash, "files": files})

    def artifact(self, key: str) -> dict:
        obj = self.get(key)
        if obj.get("kind") != "artifact" or obj.get("task") != self.task.task_hash:
            raise ValueError("Artifact belongs to another task or object type")
        self.task.validate_artifact(obj["files"])
        return obj["files"]

    def evaluate(self, artifact: str, channel: str) -> str:
        """Bind verifier outcomes to the exact task, artifact and information channel."""
        self._writable()
        files = self.artifact(artifact)
        cases = self.task.cases(channel)
        result = self.verifier.check(files, self.task.public["entrypoint"], cases)
        evaluation = self.put({"kind": "evaluation", "task": self.task.task_hash,
                               "artifact": artifact, "channel": channel, "result": result})
        self.record("evaluated", [artifact, evaluation], {"channel": channel})
        return evaluation

    def checkpoint(self, artifact: str, evaluation: str, parent: str | None = None) -> str:
        """Create a public-only checkpoint; evaluator results cannot become feedback."""
        self.artifact(artifact)
        ev = self.get(evaluation)
        if (ev.get("kind"), ev.get("task"), ev.get("artifact"), ev.get("channel")) != (
            "evaluation", self.task.task_hash, artifact, "public"
        ):
            raise ValueError("Checkpoint requires matching public verification")
        prior = self._checkpoint(parent) if parent else None
        if prior and prior["feedback"]["passed"]:
            raise ValueError("A public pass terminates the trajectory")
        history = prior["history"] if prior else []
        feedback = ev["result"]
        cp = self.put({"kind": "checkpoint", "task": self.task.task_hash, "artifact": artifact,
                       "evaluation": evaluation, "parent": parent, "feedback": feedback,
                       "history": history + [{"passed_cases": feedback["passed_cases"],
                                               "total_cases": feedback["total_cases"]}],
                       "mode": self.mode})
        self.record("checkpoint", [cp], {})
        return cp

    def _checkpoint(self, key: str) -> dict:
        cp = self.get(key)
        if cp.get("kind") != "checkpoint" or cp.get("task") != self.task.task_hash:
            raise ValueError("Checkpoint task mismatch")
        return cp

    def fork(self, checkpoint: str, action: str, remaining_budget_usd: str) -> str:
        """Clone a failed decision state; only the starting artifact differs by action."""
        if action not in {"continue", "restart"}:
            raise ValueError("Only continue/restart are implemented")
        budget = Decimal(remaining_budget_usd)
        if not budget.is_finite() or budget <= 0:
            raise ValueError("A finite positive planning budget is required")
        cp = self._checkpoint(checkpoint)
        if cp["feedback"]["passed"]:
            raise ValueError("Cannot fork after a public pass")
        artifact = cp["artifact"] if action == "continue" else self.initial
        branch = self.put({"kind": "branch", "checkpoint": checkpoint, "action": action,
                           "starting_artifact": artifact, "remaining_budget_usd": str(budget),
                           "budget_is_illustrative": self.mode != "model_pilot", "mode": self.mode})
        self.record("forked", [checkpoint, branch, artifact], {})
        return branch

    def request(self, branch: str) -> dict:
        """Project an allowlisted solver request, excluding history, oracle and labels."""
        b = self.get(branch)
        if b.get("kind") != "branch":
            raise ValueError("Expected a branch object")
        cp = self._checkpoint(b["checkpoint"])
        public = self.task.public
        # Feedback may include measured verifier times; they are not solver input.
        feedback = {k: cp["feedback"][k] for k in ("passed", "passed_cases", "total_cases", "cases")}
        payload = {"instruction": public["instruction"], "entrypoint": public["entrypoint"],
                   "public_cases": public["public_cases"], "latest_feedback": feedback,
                   "files": self.artifact(b["starting_artifact"])}
        messages = [{"role": "system", "content": REPAIR_SYSTEM},
                    {"role": "user", "content": canonical(payload)}]
        request = {"messages": messages, "remaining_budget_usd": b["remaining_budget_usd"],
                   "mode": self.mode, "provider_call_enabled": self.mode == "model_pilot"}
        request_object = self.put({"kind": "request", "branch": branch, "request": request})
        self.record("request_prepared", [branch, request_object], {})
        return request

    def materialize(self, artifact: str, name: str) -> Path:
        """Restore an artifact to a fresh workspace without touching its parent."""
        self._writable()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Invalid workspace name")
        files = self.artifact(artifact)
        work = self.root / "workspaces" / name
        work.mkdir(exist_ok=False)
        for path, source in files.items():
            (work / path).write_text(source, encoding="utf-8")
        self.record("materialized", [artifact], {"workspace": name})
        return work


def audit_run(root: Path) -> dict:
    """Verify object hashes, complete event chain and all referenced objects offline."""
    objects = {}
    for path in sorted((root / "objects").glob("*.json")):
        value = json.loads(path.read_text())
        if path.stem != identity(value):
            raise ValueError("Corrupt stored object")
        objects[path.stem] = value
    previous = None
    paths = sorted((root / "events").glob("*.json"))
    if not paths:
        raise ValueError("Empty run journal")
    for number, path in enumerate(paths):
        row = json.loads(path.read_text())
        digest = row.pop("hash")
        if (path.name != f"{number:06d}.json" or row["sequence"] != number
                or row["previous"] != previous or identity(row) != digest):
            raise ValueError("Corrupt or incomplete event chain")
        if any(key not in objects for key in row["objects"]):
            raise ValueError("Missing referenced object")
        previous = digest
    result = {"status": "verified", "objects": len(objects), "events": len(paths), "event_head": previous}
    completion = root / "completion.json"
    if completion.exists() and json.loads(completion.read_text())["audit"] != result:
        raise ValueError("Run differs from its completion record")
    return result
