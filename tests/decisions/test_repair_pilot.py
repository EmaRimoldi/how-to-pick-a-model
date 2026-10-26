"""Exercise real branch bookkeeping, information boundaries and costed selection."""

from dataclasses import asdict
from decimal import Decimal
import json

import pytest

from vao.repair.environment import RepairTask, canonical
from vao.repair.pilot import Design, ScriptedTransport, audit, collect, comparisons, public_choice, rows
from vao.repair import pilot
from vao.repair.provider import OpenRouterTransport, Settings


@pytest.fixture
def task():
    return RepairTask.from_dicts({"schema_version": 1, "task_id": "development/test",
        "instruction": "Repair solve", "entrypoint": {"module": "solution", "function": "solve"},
        "files": {"solution.py": "original"}, "public_cases": [{"id": "public", "args": [1], "expected": 1}],
        "provenance": {"kind": "synthetic_engineering_fixture"}},
        {"cases": [{"id": "SECRET_TEST_CANARY", "args": [981], "expected": 456}]})


class Verifier:
    def preflight(self):
        return {"test_double": True}

    def check(self, files, entrypoint, cases):
        # 'overfit' passes only the public test, 'fixed' passes both.
        passed = files["solution.py"] == "fixed" or (files["solution.py"] == "overfit" and cases[0]["id"] == "public")
        return {"passed": passed, "passed_cases": int(passed), "total_cases": 1,
                "cases": [{"id": cases[0]["id"], "passed": passed, "observed": {"status": "returned", "value": 0}}],
                "verifier_seconds": .01}


def failure_then_repairs(request, meta):
    assert "SECRET_TEST_CANARY" not in canonical(request)
    assert "history" not in canonical(request)
    if meta["phase"] == "prefix":
        return {"solution.py": f"prefix-{meta['depth']}"}
    return {"solution.py": "fixed" if meta["action"] == "restart" else "overfit"}


def bank(tmp_path, task, responder=failure_then_repairs, design=Design(1, 2, 2), **accounting):
    output = tmp_path / "bank"
    result = collect([task], design, output, Verifier(), lambda out: ScriptedTransport(out, responder, **accounting))
    return output, result


def test_forks_never_change_prefix_and_retain_public_false_positives(tmp_path, task):
    output, result = bank(tmp_path, task)
    assert result["observations"] == 10
    assert result["api_calls"] == 0 and not result["model_results"]
    observations = rows(output / "observations.jsonl")
    second = next(r for r in observations if r["phase"] == "prefix" and r["depth"] == 2)
    request = json.loads((output / "requests" / (second["attempt_id"] + ".json")).read_text())
    assert json.loads(request["request"]["messages"][1]["content"])["files"] == {"solution.py": "prefix-1"}
    assert all(not r["full_pass"] for r in observations if r.get("action") == "continue")
    assert all(r["full_pass"] for r in observations if r.get("action") == "restart")
    assert audit(output)["verified_observations"] == 10


def test_two_candidate_cost_includes_loser_and_prefix_once(tmp_path, task):
    output, _ = bank(tmp_path, task)
    groups = rows(output / "groups.jsonl")
    results = comparisons(output)
    assert len(results) == 10
    for group in groups:
        fixed = next(r for r in results if r["group"] == group["group"] and r["policy"] == "continue_one")
        mixed = next(r for r in results if r["group"] == group["group"] and r["policy"] == "mixed_two_public_select")
        assert Decimal(fixed["cost_usd"]) == Decimal(group["prefix_cost_usd"]) + Decimal(".00005")
        assert Decimal(mixed["cost_usd"]) == Decimal(group["prefix_cost_usd"]) + Decimal(".00010")
        assert len(mixed["candidate_attempts"]) == 2
        assert mixed["currency"] == "simulated_USD" and not mixed["model_results"]


def test_selection_cannot_use_hidden_success_even_in_a_tie():
    candidates = [{"attempt_id": "wrong", "public_passed_cases": 1, "full_pass": False},
                  {"attempt_id": "correct", "public_passed_cases": 1, "full_pass": True}]
    assert public_choice(candidates) == "wrong"
    candidates[0]["public_passed_cases"] = None
    assert public_choice(candidates) == "correct"


def test_public_pass_stops_prefix_even_if_private_tests_fail(tmp_path, task):
    output, report = bank(tmp_path, task, lambda *_: {"solution.py": "overfit"})
    assert report["observations"] == 1
    assert rows(output / "trajectories.jsonl")[0]["reason"] == "public_pass"
    assert rows(output / "observations.jsonl")[0]["full_pass"] is False
    assert comparisons(output) == []


def test_invalid_response_is_retained_and_paid_without_a_fabricated_patch(tmp_path, task):
    output, report = bank(tmp_path, task, lambda *_: "not JSON")
    assert report["observations"] == 1
    observation = rows(output / "observations.jsonl")[0]
    assert observation["status"] == "format_error" and observation["artifact"] is None
    assert rows(output / "trajectories.jsonl")[0]["reason"] == "prefix_format_error"
    assert audit(output)["settled_usd"] == "0.00005"


def test_admission_exhaustion_is_missing_not_strategy_failure(tmp_path, task):
    output, report = bank(tmp_path, task, limit="0.0003")
    assert report["observations"] == 1 and report["missing_groups"] == 1
    results = comparisons(output)
    assert len(results) == 5
    assert all(r["status"] == "missing" and r["full_pass"] is None and r["cost_usd"] is None for r in results)


def test_exception_retains_reserve_and_cannot_resume(tmp_path, task):
    sent = []
    def fail(request, meta):
        sent.append(meta["attempt_id"])
        raise TimeoutError("Pretend unknown provider outcome")
    with pytest.raises(TimeoutError):
        bank(tmp_path, task, fail)
    output = tmp_path / "bank"
    assert len(sent) == 1
    assert not (output / "pilot-completion.json").exists()
    assert audit(output)["pending"] == {sent[0]: "0.0001"}
    with pytest.raises(FileExistsError):
        bank(tmp_path, task, fail)
    assert len(sent) == 1


def test_scripted_adapter_refuses_same_request_twice(tmp_path):
    (tmp_path / "receipts").mkdir()
    client = ScriptedTransport(tmp_path, lambda *_: {})
    client.complete({}, {"attempt_id": "a"})
    with pytest.raises(ValueError, match="Duplicate"):
        client.complete({}, {"attempt_id": "a"})


def test_audit_detects_private_outcome_tampering_before_and_after_seal(tmp_path, task):
    output, _ = bank(tmp_path, task)
    observations = rows(output / "observations.jsonl")
    observations[0]["full_pass"] = True
    (output / "observations.jsonl").write_text("\n".join(canonical(r) for r in observations) + "\n")
    for sealed in (True, False):
        if not sealed:
            (output / "pilot-completion.json").unlink()
        with pytest.raises(ValueError, match="saved verification"):
            audit(output)


def test_unmatched_prompts_and_system_leak_are_rejected(tmp_path, task):
    output, _ = bank(tmp_path, task)
    observation = rows(output / "observations.jsonl")[0]
    path = output / "requests" / (observation["attempt_id"] + ".json")
    request = json.loads(path.read_text())
    request["request"]["messages"][0]["content"] += " SECRET_TEST_CANARY"
    path.write_text(canonical(request))
    with pytest.raises(ValueError, match="system instructions"):
        audit(output)


def test_design_bounds_and_call_ceiling():
    assert Design().maximum_calls(12) == 360
    for kwargs in ({"draws_per_action": 1}, {"prefix_attempts": 0}, {"prefix_replicates": True}):
        with pytest.raises(ValueError):
            Design(**kwargs)


def test_other_transports_cannot_enable_paid_calls(tmp_path, task):
    class PretendLive:
        mode = "model_pilot"
    with pytest.raises(ValueError, match="only the offline"):
        collect([task], Design(), tmp_path / "run", Verifier(), lambda _: PretendLive())


def funded_config():
    return {"status": "authorized_development_pilot", "live_calls_enabled": True,
            "campaign_id": "offline-contract-test", "authorization_reference": "TEST ONLY: mocked network",
            "monetary_authorization_usd": "0.60", "provider_settings": asdict(Settings()),
            "design": asdict(Design(1, 1, 2))}


def test_draft_cannot_freeze_and_source_drift_blocks_launch(tmp_path, task, monkeypatch):
    monkeypatch.setattr(pilot, "source_commit", lambda: "a" * 40)
    config = funded_config()
    with pytest.raises(ValueError, match="authorization"):
        pilot.funded_freeze({**config, "live_calls_enabled": False}, [task], tmp_path / "draft.json")
    frozen = pilot.funded_freeze(config, [task], tmp_path / "freeze.json")
    assert pilot.validate_freeze(frozen, [task]) == Design(1, 1, 2)
    monkeypatch.setattr(pilot, "source_commit", lambda: "b" * 40)
    with pytest.raises(ValueError, match="differ"):
        pilot.validate_freeze(frozen, [task])
    monkeypatch.setattr(pilot, "source_commit", lambda: "a" * 40)
    frozen["authorized_limit_usd"] = "1.00"
    with pytest.raises(ValueError, match="differ"):
        pilot.validate_freeze(frozen, [task])


def test_funded_path_uses_one_campaign_claim_and_audits_billing(tmp_path, task, monkeypatch):
    # Exercise the live code path with a completely mocked network and verifier.
    monkeypatch.setattr(pilot, "source_commit", lambda: "a" * 40)
    monkeypatch.setattr(pilot, "RepairVerifier", Verifier)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-test-only")
    config = funded_config()
    frozen = pilot.funded_freeze(config, [task], tmp_path / "freeze.json")
    sent = []
    def exchange(self, path, body=None):
        if path.endswith("/endpoints"):
            return {"data": {"id": self.settings.model, "endpoints": [{
                "tag": self.settings.endpoint, "provider_name": self.settings.provider_name,
                "quantization": "bf16", "context_length": 131072, "max_completion_tokens": 117964,
                "supported_parameters": ["seed", "temperature", "max_tokens", "response_format"],
                "pricing": {"prompt": "0.00000004", "completion": "0.00000005"}}]}}
        if path == "/key":
            return {"data": {"limit_remaining": 1}}
        if path == "/credits":
            return {"data": {"total_credits": 2, "total_usage": 1}}
        assert path == "/chat/completions"
        sent.append(body)
        return {"id": "fixture-" + str(len(sent)), "model": self.settings.model,
                "provider": self.settings.provider_name, "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost": .00008},
                "choices": [{"finish_reason": "stop", "message": {"content": '{"solution.py":"still broken"}'}}]}
    monkeypatch.setattr(OpenRouterTransport, "_exchange", exchange)
    output, claims = tmp_path / "live-mocked", tmp_path / "claims"
    report = pilot.live_collect(frozen, [task], output, claim_root=claims)
    assert report["api_calls"] == 5 and report["api_spend_usd"] == "0.00040"
    assert report["simulated_spend_usd"] == "0" and report["model_results"]
    assert audit(output)["api_calls"] == 5
    assert audit(output)["conservative_committed_usd"] == "0.00040"
    result = comparisons(output)
    assert len(result) == 5 and all(r["currency"] == "USD" for r in result)
    assert all("SECRET_TEST_CANARY" not in canonical(body) for body in sent)
    with pytest.raises(FileExistsError):
        pilot.live_collect(frozen, [task], tmp_path / "duplicate", claim_root=claims)
    assert len(sent) == 5
    # Even a separately saved freeze cannot silently reuse this campaign cap.
    again = pilot.funded_freeze(config, [task], tmp_path / "other-freeze.json")
    with pytest.raises(FileExistsError):
        pilot.live_collect(again, [task], tmp_path / "another", claim_root=claims)
    assert len(sent) == 5


def test_incomplete_live_bank_counts_known_overrun_not_just_reserve(tmp_path, task, monkeypatch):
    monkeypatch.setattr(pilot, "source_commit", lambda: "a" * 40)
    frozen = pilot.funded_freeze(funded_config(), [task], tmp_path / "freeze.json")
    def factory(output):
        transport = OpenRouterTransport(output, "fixture", Settings(), authorized_limit_usd="0.60")
        def preflight():
            transport.ready = True
        def exchange(*_):
            return {"model": "wrong", "usage": {"cost": .61}}
        monkeypatch.setattr(transport, "preflight", preflight)
        monkeypatch.setattr(transport, "_exchange", exchange)
        return transport
    with pytest.raises(RuntimeError):
        collect([task], Design(1, 1, 2), tmp_path / "partial", Verifier(), factory, freeze=frozen)
    result = audit(tmp_path / "partial")
    assert result["api_calls"] == 1 and result["verified_observations"] == 0
    assert result["conservative_committed_usd"] == "0.61" and result["cap_exceeded"]
    assert not result["sealed"]


def test_manual_continuation_excludes_started_trajectories_and_carries_uncertain_cost(tmp_path, task, monkeypatch):
    monkeypatch.setattr(pilot, "source_commit", lambda: "a" * 40)
    second = RepairTask.from_dicts({**task.public, "task_id": "development/second"},
                                  json.loads(task.evaluator_json))
    tasks, design = [task, second], Design(1, 1, 2)
    original = pilot.funded_freeze(funded_config(), tasks, tmp_path / "original.json")
    parent = tmp_path / "parent"
    def failing(output):
        client = OpenRouterTransport(output, "fixture", Settings(), authorized_limit_usd="0.60")
        monkeypatch.setattr(client, "preflight", lambda: setattr(client, "ready", True))
        def exchange(*_):
            raise TimeoutError("offline test")
        monkeypatch.setattr(client, "_exchange", exchange)
        return client
    with pytest.raises(RuntimeError):
        collect(tasks, design, parent, Verifier(), failing, freeze=original)
    before = pilot.file_hashes(parent)
    started = sorted(p.name for p in (parent / "trajectories").iterdir())
    allowed = [f"task-{i:03d}-rep-{r:02d}" for i, r in pilot.schedule_for(tasks, design)
               if f"task-{i:03d}-rep-{r:02d}" not in started]
    carried = audit(parent)["conservative_committed_usd"]
    config = {**funded_config(), "campaign_id": "offline-contract-test-successor",
              "monetary_authorization_usd": str(Decimal(".60")-Decimal(carried)),
              "continuation": {"parent_run": str(parent), "parent_freeze_id": original["freeze_id"],
                 "parent_hashes": before, "retained_committed_usd": carried,
                 "cumulative_limit_usd": "0.60", "omitted_started_trajectories": started,
                 "allowed_trajectories": allowed}}
    assert len(allowed) == 1
    assert pilot.check_continuation(config, tasks, design) == Settings().reserve
    bad = json.loads(json.dumps(config))
    bad["continuation"]["allowed_trajectories"] = started
    with pytest.raises(ValueError, match="unstarted"):
        pilot.check_continuation(bad, tasks, design)
    bad = json.loads(json.dumps(config))
    bad["monetary_authorization_usd"] = "0.60"
    with pytest.raises(ValueError, match="accounting"):
        pilot.check_continuation(bad, tasks, design)
    successor = pilot.funded_freeze(config, tasks, tmp_path / "successor.json")
    def succeeding(output):
        client = OpenRouterTransport(output, "fixture", Settings(), authorized_limit_usd=config["monetary_authorization_usd"])
        monkeypatch.setattr(client, "preflight", lambda: setattr(client, "ready", True))
        monkeypatch.setattr(client, "_exchange", lambda *_: {
            "id": "fixture", "model": client.settings.model, "provider": client.settings.provider_name,
            "usage": {"cost": .00008, "prompt_tokens": 100, "completion_tokens": 10},
            "choices": [{"finish_reason": "stop", "message": {"content": '{"solution.py":"fixed"}'}}]})
        return client
    report = collect(tasks, design, tmp_path / "successor", Verifier(), succeeding, freeze=successor)
    assert report["trajectories"] == 1 and report["api_calls"] == 1
    assert report["carried_committed_usd"] == carried
    assert Decimal(report["cumulative_committed_usd"]) == Settings().reserve + Decimal(".00008")
    assert audit(tmp_path / "successor")["conservative_committed_usd"] == report["cumulative_committed_usd"]
    new = rows(tmp_path / "successor" / "observations.jsonl")
    assert all(r["trajectory"] in allowed and r["trajectory"] not in started for r in new)
    assert before == pilot.file_hashes(parent)
