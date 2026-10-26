"""Offline provider contracts; no live OpenRouter credentials or requests."""

from dataclasses import asdict
from decimal import Decimal
import json

import pytest

from vao.repair.environment import canonical
from vao.repair.pilot import rows
from vao.repair.provider import OpenRouterTransport, ProviderStopped, Settings


@pytest.fixture
def solver_request():
    return {"mode": "model_pilot", "provider_call_enabled": True,
            "messages": [{"role": "system", "content": "Return JSON"}, {"role": "user", "content": "Bug"}]}


@pytest.fixture
def meta():
    return {"attempt_id": "a", "trajectory": "task-000-rep-00", "phase": "branch",
            "depth": 1, "draw": 0, "action": "continue"}


def endpoint():
    return {"id": "google/gemma-3-4b-it", "endpoints": [{"tag": "parasail/bf16",
        "provider_name": "Parasail", "quantization": "bf16", "context_length": 131072,
        "max_completion_tokens": 117964,
        "supported_parameters": ["max_tokens", "temperature", "seed", "response_format"],
        "pricing": {"prompt": "0.00000004", "completion": "0.00000005", "input_cache_read": "0.00000002"}}]}


def receipt(**updates):
    result = {"id": "gen-test", "model": "google/gemma-3-4b-it", "provider": "Parasail",
              "choices": [{"finish_reason": "stop", "message": {"content": '{"solution.py":"pass"}'}}],
              "usage": {"cost": 0.00008, "prompt_tokens": 100, "completion_tokens": 10,
                        "prompt_tokens_details": {"cached_tokens": 0}}}
    result.update(updates)
    return result


def client(tmp_path, monkeypatch, response=None, endpoints=None, credits=None, keyinfo=None):
    (tmp_path / "requests").mkdir()
    (tmp_path / "receipts").mkdir()
    transport = OpenRouterTransport(tmp_path, "fixture-bearer-canary", Settings(), authorized_limit_usd="0.60")
    calls = []
    def exchange(path, body=None):
        calls.append((path, body))
        if path.endswith("/endpoints"):
            return {"data": endpoints or endpoint()}
        if path == "/key":
            return {"data": keyinfo or {"limit_remaining": 1, "label": "PRIVATE-LABEL"}}
        if path == "/credits":
            return {"data": credits or {"total_credits": 2, "total_usage": 1}}
        assert path == "/chat/completions"
        # Exact solver_request and admission are durable before POST, receipt is not.
        assert (tmp_path / "requests" / "a.provider.json").exists()
        assert rows(tmp_path / "ledger.jsonl")[-1]["event"] == "reserve"
        assert not (tmp_path / "receipts" / "a.raw.json").exists()
        if isinstance(response, Exception):
            raise response
        return response if response is not None else receipt()
    monkeypatch.setattr(transport, "_exchange", exchange)
    return transport, calls


def test_pinned_generation_and_durable_billed_receipt(tmp_path, monkeypatch, solver_request, meta):
    transport, calls = client(tmp_path, monkeypatch)
    assert calls == []  # Constructing a client is inert.
    with pytest.raises(ProviderStopped):
        transport.complete(solver_request, meta)
    transport.preflight()
    result = transport.complete(solver_request, meta)
    assert result["cost_usd"] == "0.00008"
    assert not transport.pending
    assert transport.conservative_committed_usd == Decimal(".00008")
    assert [r["event"] for r in rows(tmp_path / "ledger.jsonl")] == ["reserve", "settle"]
    body = calls[-1][1]
    assert body["provider"]["only"] == ["parasail/bf16"] and not body["provider"]["allow_fallbacks"]
    assert body["provider"]["require_parameters"] and body["response_format"] == {"type": "json_object"}
    assert "fixture-bearer-canary" not in "".join(p.read_text() for p in tmp_path.rglob("*.json*"))
    assert "PRIVATE-LABEL" not in (tmp_path / "provider-preflight.json").read_text()
    with pytest.raises(ProviderStopped):
        transport.complete(solver_request, meta)
    with pytest.raises(ValueError, match="resumed"):
        OpenRouterTransport(tmp_path, "fixture-bearer-canary", Settings(), authorized_limit_usd="0.60")


def test_action_pairs_share_settings_seed_without_private_inputs(solver_request, meta):
    a = Settings().body(solver_request, meta)
    b = Settings().body(solver_request, {**meta, "attempt_id": "b", "action": "restart"})
    assert a == b
    c = Settings().body(solver_request, {**meta, "draw": 1})
    assert a["seed"] != c["seed"]
    assert Settings().reserve * 360 == Decimal("0.54558720")


@pytest.mark.parametrize("change", ["price", "extra_charge", "precision", "parameters", "context"])
def test_changed_endpoint_blocks_all_generation(tmp_path, monkeypatch, change, solver_request, meta):
    data = endpoint()
    e = data["endpoints"][0]
    if change == "price":
        e["pricing"]["prompt"] = "0.00000005"
    elif change == "extra_charge":
        e["pricing"]["request"] = "0.001"
    elif change == "precision":
        e["quantization"] = "fp8"
    elif change == "parameters":
        e["supported_parameters"].remove("seed")
    else:
        e["context_length"] = 8192
    transport, calls = client(tmp_path, monkeypatch, endpoints=data)
    with pytest.raises(ProviderStopped):
        transport.preflight()
    with pytest.raises(ProviderStopped):
        transport.complete(solver_request, meta)
    assert all(path != "/chat/completions" for path, _ in calls)


@pytest.mark.parametrize("source", ["key", "account"])
def test_balance_must_cover_full_declared_cap(tmp_path, monkeypatch, source):
    kwargs = {"keyinfo": {"limit_remaining": .59}} if source == "key" else {"credits": {"total_credits": 1, "total_usage": .41}}
    transport, calls = client(tmp_path, monkeypatch, **kwargs)
    with pytest.raises(ProviderStopped, match="balance"):
        transport.preflight()
    assert all(path != "/chat/completions" for path, _ in calls)


@pytest.mark.parametrize("failure", ["timeout", "missing_cost", "overrun", "wrong_provider", "wrong_model", "token_overrun"])
def test_uncertain_calls_preserve_receipts_and_reserves_without_retry(tmp_path, monkeypatch, solver_request, meta, failure):
    response = receipt()
    if failure == "timeout":
        response = TimeoutError("fixture-bearer-canary")
    elif failure == "missing_cost":
        response["usage"].pop("cost")
    elif failure == "overrun":
        response["usage"]["cost"] = .61
    elif failure == "wrong_provider":
        response["provider"] = "Other"
    elif failure == "wrong_model":
        response["model"] = "Other"
    else:
        response["usage"]["prompt_tokens"] = 32769
    transport, calls = client(tmp_path, monkeypatch, response=response)
    transport.preflight()
    with pytest.raises(ProviderStopped) as error:
        transport.complete(solver_request, meta)
    assert "fixture-bearer-canary" not in str(error.value)
    assert len(transport.pending) == 1 and not transport.available()
    assert len(rows(tmp_path / "ledger.jsonl")) == 1
    if failure != "timeout":
        assert (tmp_path / "receipts" / "a.raw.json").exists()
    if failure == "overrun":
        assert transport.conservative_committed_usd == Decimal(".61")
    with pytest.raises(ProviderStopped):
        transport.complete(solver_request, {**meta, "attempt_id": "b"})
    assert sum(path == "/chat/completions" for path, _ in calls) == 1


def test_malformed_or_truncated_text_is_still_paid_and_saved(tmp_path, monkeypatch, solver_request, meta):
    response = receipt(choices=[{"finish_reason": "length", "message": {"content": "not JSON"}}])
    transport, _ = client(tmp_path, monkeypatch, response=response)
    transport.preflight()
    result = transport.complete(solver_request, meta)
    assert result["finish_reason"] == "length" and result["content"] == "not JSON"
    assert transport.spent == Decimal(".00008") and not transport.pending


@pytest.mark.parametrize("change", ["offline", "too_large"])
def test_bad_request_is_rejected_before_reservation_or_post(tmp_path, monkeypatch, solver_request, meta, change):
    transport, calls = client(tmp_path, monkeypatch)
    transport.preflight()
    if change == "offline":
        solver_request["provider_call_enabled"] = False
    else:
        solver_request["messages"][1]["content"] = "x" * 40000
    with pytest.raises(ProviderStopped):
        transport.complete(solver_request, meta)
    assert not transport.pending and not (tmp_path / "ledger.jsonl").exists()
    assert all(path != "/chat/completions" for path, _ in calls)


def test_even_unexpected_key_echo_is_redacted(tmp_path, monkeypatch, solver_request, meta):
    transport, _ = client(tmp_path, monkeypatch, response=receipt(unexpected="fixture-bearer-canary"))
    transport.preflight()
    transport.complete(solver_request, meta)
    assert "fixture-bearer-canary" not in (tmp_path / "receipts" / "a.raw.json").read_text()


def test_invalid_numeric_settings_and_funding_fail_closed(tmp_path):
    for kwargs in ({"temperature": float("nan")}, {"max_tokens": True}, {"input_per_million": "NaN"}):
        with pytest.raises((ValueError, ProviderStopped)):
            Settings(**{**asdict(Settings()), **kwargs})
    for limit in ("0", "NaN", "Infinity", "6", ".00001"):
        with pytest.raises((ValueError, ProviderStopped)):
            OpenRouterTransport(tmp_path, "fixture", Settings(), authorized_limit_usd=limit)
