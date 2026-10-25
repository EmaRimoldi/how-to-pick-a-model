from __future__ import annotations

import json
from pathlib import Path

import pytest

from vao.decisions.openrouter import BudgetLedger, insured_empty_error, read_stream
from vao.decisions.recovery_import import ImportedClient, import_completed
from vao.decisions.pilot import digest


def test_only_explicit_empty_identified_provider_error_has_policy_zero():
    record = {"usage": {}, "content": "", "finish_reason": "error", "generation_id": "gen-test", "provider": "SiliconFlow"}
    assert insured_empty_error(record)
    assert record["usage"]["cost"] == 0 and record["reported_usage"] == {}
    assert record["billing_source"] == "published_zero_completion_insurance"
    for changed in ({"finish_reason": "stop"}, {"content": "partial"}, {"generation_id": None}):
        candidate = {"usage": {}, "content": "", "finish_reason": "error", "generation_id": "gen-test", "provider": "SiliconFlow", **changed}
        assert not insured_empty_error(candidate)


def test_stream_preserves_identified_provider_error_without_retrying():
    event = {"id": "gen-test", "provider": "SiliconFlow", "model": "model", "error": {"code": 503}}
    payload = read_stream([("data: " + json.dumps(event) + "\n").encode()])
    assert payload["id"] == "gen-test"
    assert payload["choices"][0]["finish_reason"] == "error"


def test_fresh_journal_import_reuses_failed_draw_and_refuses_prompt_drift(tmp_path, monkeypatch):
    source, output = tmp_path / "source", tmp_path / "new"
    source.mkdir(); output.mkdir()
    config = {"anything": "frozen"}
    (source / "manifest.json").write_text(json.dumps({"config_sha256": digest(config), "git_sha": "a" * 40}))
    monkeypatch.setattr("vao.decisions.recovery_import.subprocess.check_output", lambda args: Path(args[-1].split(":", 1)[1]).read_bytes())
    (source / "evaluations.jsonl").write_text("")
    call = {"call": 1, "model_name": "small", "task_id": "t", "split": "development", "action": "branch", "arm": "fresh", "draw": 0,
            "messages": [{"role": "user", "content": "task"}], "usage": {}, "finish_reason": "error", "content": "",
            "generation_id": "gen-test", "provider": "SiliconFlow"}
    (source / "calls.jsonl").write_text(json.dumps(call) + "\n")
    (source / "budget.jsonl").write_text(json.dumps({"event": "reserve", "call": 1, "reserved_usd": 0.01}) + "\n")
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps({"matches_within_1e_8": True, "account_usage_change_usd": 0}))
    ledger = BudgetLedger(output / "budget.jsonl", 1)
    imported, provenance = import_completed(source, output, ledger, config, proof)
    client = ImportedClient("dummy", config, output, ledger, imported)
    monkeypatch.setattr(client, "request", lambda *args: pytest.fail("No inference request is allowed for imported jobs"))
    metadata = {k: call[k] for k in ("task_id", "split", "action", "arm", "draw", "model_name")}
    result = client.complete("small", call["messages"], 1, metadata)
    assert result["call"] == 1 and result["finish_reason"] == "error" and result["cost_usd"] == 0
    assert ledger.calls == 1 and ledger.spent == 0 and not ledger.pending
    with pytest.raises(ValueError, match="Duplicate job"):
        client.complete("small", call["messages"], 1, metadata)
    with pytest.raises(ValueError, match="prompt changed"):
        client.complete("small", [{"role": "user", "content": "changed"}], 1, metadata)
