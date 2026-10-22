"""Explicitly import a stopped run into a fresh journal without repeating paid jobs."""

from __future__ import annotations

import json
import re
import subprocess
import threading
from decimal import Decimal
from pathlib import Path

from .openrouter import OpenRouterClient, append_json, insured_empty_error
from .pilot import digest


def records(root: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in (root / (name + ".jsonl")).read_text().splitlines() if line]


def job_key(model: str, messages: list[dict], metadata: dict) -> str:
    keys = ("task_id", "split", "action", "arm", "draw", "checkpoint_id", "parent_call", "donor_checkpoint_id", "view", "model_name")
    return digest({"model_name": model, "messages": messages,
                   "metadata": {k: metadata[k] for k in keys if k in metadata}})


def import_completed(source: Path, output: Path, ledger, config: dict, reconciliation: Path | None) -> tuple[list[dict], dict]:
    """Copy immutable source evidence into a NEW journal; retain every original failed draw."""
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest["config_sha256"] != digest(config):
        raise ValueError("Import must use the identical frozen configuration")
    if not re.fullmatch(r"[0-9a-f]{40}", manifest["git_sha"]):
        raise ValueError("Source commit identity is invalid")
    for name in ("verification.py", "verifier_worker.py"):
        relative = "src/vao/decisions/" + name
        original = subprocess.check_output(["git", "show", manifest["git_sha"] + ":" + relative])
        if original != Path(relative).read_bytes():
            raise ValueError("Evaluator changed; importing old scores is refused")
    calls = records(source, "calls")
    events = records(source, "budget")
    reserve = {r["call"]: Decimal(str(r["reserved_usd"])) for r in events if r["event"] == "reserve"}
    settled = {r["call"]: Decimal(str(r["cost_usd"])) for r in events if r["event"] == "settle"}
    if set(reserve) != {c["call"] for c in calls}:
        raise ValueError("An admitted request has no response identity; explicit import refuses it")
    normalized = []
    for call in calls:
        if call["call"] not in settled:
            if not insured_empty_error(call):
                raise ValueError("Unresolved non-insured billing prevents import")
            normalized.append(call["call"])
    proof = None
    if normalized:
        if reconciliation is None:
            raise ValueError("Insured source errors require the explicit account reconciliation record")
        proof = json.loads(reconciliation.read_text())
        if not proof["matches_within_1e_8"] or abs(proof["account_usage_change_usd"] - float(sum(settled.values()))) >= 1e-8:
            raise ValueError("Aggregate account charge does not match source receipts")
    costs = {c["call"]: Decimal(str(c["usage"]["cost"])) for c in calls}
    if any(not cost.is_finite() or cost < 0 or cost > reserve[i] for i, cost in costs.items()):
        raise ValueError("Invalid imported billing")
    if any(costs[i] != amount for i, amount in settled.items()):
        raise ValueError("Imported receipt differs from its original settlement")
    total = sum(costs.values())
    if total > ledger.limit:
        raise ValueError("Imported charges exceed the new run's total ceiling")
    for event in events:
        append_json(ledger.path, event)
    for call_id in normalized:
        append_json(ledger.path, {"event": "settle", "call": call_id, "cost_usd": 0,
                                 "billing_source": "published_zero_completion_insurance"})
    for call in calls:
        append_json(output / "calls.jsonl", call)
    ledger.spent = total
    ledger.calls = max(reserve, default=0)
    provenance = {"source_collector_git_sha": manifest["git_sha"], "source_calls_sha256": digest(records(source, "calls")),
                  "source_budget_sha256": digest(events), "imported_calls": len(calls),
                  "source_evaluations_sha256": digest(records(source, "evaluations")),
                  "imported_cost_usd": float(total), "insured_zero_charge_call_ids": normalized,
                  "aggregate_reconciliation": proof,
                  "rule": "Existing jobs are reused once; provider error outputs remain failures, never resampled."}
    (output / "import-provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    return calls, provenance


class ImportedClient(OpenRouterClient):
    """Deduplicate by complete observable job identity, with a fresh append-only ledger."""

    def __init__(self, key, config, output, ledger, imported, evaluations=None):
        super().__init__(key, config, output, ledger)
        self._cached = {job_key(c["model_name"], c["messages"], c): c for c in imported}
        if len(self._cached) != len(imported):
            raise ValueError("Source contains duplicate jobs")
        self._seen = set()
        self._identities = {job_key(c["model_name"], [], c): job_key(c["model_name"], c["messages"], c) for c in imported}
        self._cache_lock = threading.Lock()
        self._evaluations = {r["call"]: r for r in (evaluations or [])}

    def cached_evaluation(self, call):
        return self._evaluations.get(call)

    def complete(self, model_name, messages, seed, metadata):
        key = job_key(model_name, messages, metadata)
        with self._cache_lock:
            previous = self._identities.get(job_key(model_name, [], metadata))
            if previous is not None and previous != key:
                raise ValueError("Imported job identity matches but its prompt changed")
            if key in self._seen:
                raise ValueError("Duplicate job admission refused")
            self._seen.add(key)
            cached = self._cached.get(key)
        if cached is not None:
            append_json(self.output / "import-uses.jsonl", {"call": cached["call"], "job_sha256": key})
            return {**cached, "cost_usd": cached["usage"]["cost"]}
        return super().complete(model_name, messages, seed, metadata)
