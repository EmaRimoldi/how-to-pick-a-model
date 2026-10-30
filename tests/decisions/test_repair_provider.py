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


def client(tmp_path, monkeypatch, response=None, endpoints=None, credits=None, keyinfo=None, minimum_interval_seconds=0):
    (tmp_path / "requests").mkdir()
    (tmp_path / "receipts").mkdir()
    transport = OpenRouterTransport(tmp_path, "fixture-bearer-canary", Settings(), authorized_limit_usd="0.60",
                                    minimum_interval_seconds=minimum_interval_seconds)
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


def test_http_status_is_retained_without_server_body_or_credentials(tmp_path, monkeypatch, solver_request, meta):
    error = ProviderStopped("Do not persist this text: fixture-bearer-canary", http_status=429, transport_kind="http_error", retry_after="120")
    transport, calls = client(tmp_path, monkeypatch, response=error)
    transport.preflight()
    with pytest.raises(ProviderStopped):
        transport.complete(solver_request, meta)
    record = rows(tmp_path / "provider-errors.jsonl")[0]
    assert record["http_status"] == 429 and record["transport_kind"] == "http_error"
    assert record["retry_after"] == "120"
    assert "fixture-bearer-canary" not in canonical(record)
    assert len(transport.pending) == 1
    assert sum(path == "/chat/completions" for path, _ in calls) == 1


@pytest.mark.parametrize("failure,phase", [
    ("headers", "awaiting_response_headers"),
    ("body", "reading_response"),
    ("truncated_body", "reading_response"),
    ("json", "decoding_response"),
])
def test_transport_failure_phase_is_durable_without_retry_or_secret(
        tmp_path, monkeypatch, solver_request, meta, failure, phase):
    import http.client
    from vao.repair import provider

    transport, _ = client(tmp_path, monkeypatch)
    transport.preflight()  # Mocked account checks only.
    monkeypatch.setattr(transport, "_exchange", OpenRouterTransport._exchange.__get__(transport))
    calls, closed = [], []
    secret = "fixture-bearer-canary"

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            closed.append(True)

        def read(self):
            if failure == "body":
                raise TimeoutError(secret)
            if failure == "truncated_body":
                raise http.client.IncompleteRead(secret.encode(), 123)
            return ("not json " + secret).encode()

    class Opener:
        def open(self, request, timeout):
            calls.append((request.full_url, timeout))
            if failure == "headers":
                raise TimeoutError(secret)
            return Response()

    monkeypatch.setattr(provider.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(ProviderStopped):
        transport.complete(solver_request, meta)
    record = rows(tmp_path / "provider-errors.jsonl")[0]
    assert record["transport_phase"] == phase
    assert record["exchange_elapsed_seconds"] >= 0
    assert secret not in canonical(record)
    assert record["reservation_retained"] is True
    assert transport.pending == {"a": transport.reserve}
    assert transport.conservative_committed_usd == transport.reserve
    assert len(rows(tmp_path / "ledger.jsonl")) == 1  # No invented settlement.
    with pytest.raises(ProviderStopped):
        transport.complete(solver_request, {**meta, "attempt_id": "b"})
    assert calls == [("https://openrouter.ai/api/v1/chat/completions", 180)]
    assert bool(closed) == (failure != "headers")


def test_distinct_calls_are_paced_without_retrying(tmp_path, monkeypatch, solver_request, meta):
    from vao.repair import provider
    transport, _ = client(tmp_path, monkeypatch, minimum_interval_seconds=15)
    transport.preflight()
    clock, pauses, sent = [100.0], [], []
    monkeypatch.setattr(provider.time, "monotonic", lambda: clock[0])
    def sleep(seconds):
        pauses.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(provider.time, "sleep", sleep)
    def exchange(*_):
        sent.append(clock[0])
        return receipt(id="generation-" + str(len(sent)))
    monkeypatch.setattr(transport, "_exchange", exchange)
    transport.complete(solver_request, meta)
    clock[0] += 3
    transport.complete(solver_request, {**meta, "attempt_id": "b"})
    assert sent == [100, 115] and pauses == [12]
    assert len(transport.seen) == 2 and len(rows(tmp_path / "ledger.jsonl")) == 4


@pytest.mark.parametrize('streamed', [False, True])
@pytest.mark.parametrize('body_kind', ['structured', 'malformed', 'oversized', 'nested', 'read_failed'])
def test_http_failure_diagnostics_are_bounded_allowlisted_and_never_retry(
        tmp_path, monkeypatch, solver_request, meta, body_kind, streamed):
    import io
    import urllib.error
    from vao.repair import provider
    from vao.repair.streaming import StreamingOpenRouterTransport, StreamingSettings

    secret = 'fixture-bearer-canary'
    body = {'error': {'code': 429, 'message': secret,
        'metadata': {'error_type': 'rate_limit_exceeded', 'provider_code': secret,
                     'raw': secret, 'account_id': secret, 'limit_source': ['bad-shape']}}}
    raw = canonical(body).encode()
    if body_kind == 'malformed': raw = b'not json: ' + secret.encode()
    if body_kind == 'oversized': raw = b' ' * 8200 + raw
    if body_kind == 'nested': raw = b'[' * 1500 + b'0' + b']' * 1500
    # CPython/pytest recursion limits differ; inject the decoder failure rather
    # than relying on a particular nesting threshold in the running interpreter.
    original_loads = provider.json.loads
    def load(data, *args, **kwargs):
        if body_kind == 'nested' and data == raw:
            raise RecursionError(secret)
        return original_loads(data, *args, **kwargs)
    monkeypatch.setattr(provider.json, 'loads', load)
    calls = []
    class BrokenBody(io.BytesIO):
        def read(self, *_): raise ConnectionResetError(secret)
    response_body = BrokenBody(raw) if body_kind == 'read_failed' else io.BytesIO(raw)
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 429, secret,
                {'Retry-After': '60', 'X-RateLimit-Remaining-Requests': '0',
                 'X-RateLimit-Limit-Requests': secret, 'X-Request-Id': secret}, response_body)
    monkeypatch.setattr(provider.urllib.request, 'build_opener', lambda *_: Opener())
    (tmp_path / 'requests').mkdir()
    (tmp_path / 'receipts').mkdir()
    transport = (StreamingOpenRouterTransport(tmp_path, secret, StreamingSettings(), authorized_limit_usd='.60')
                 if streamed else OpenRouterTransport(tmp_path, secret, Settings(), authorized_limit_usd='.60'))
    transport.ready = True  # Exercise the real HTTP path without a network preflight.
    with pytest.raises(ProviderStopped): transport.complete(solver_request, meta)
    with pytest.raises(ProviderStopped): transport.complete(solver_request, {**meta, 'attempt_id': 'b'})
    error = rows(tmp_path / 'provider-errors.jsonl')[0]
    details = error['error_details']
    assert details['rate_headers'] == {'retry-after': 60, 'x-ratelimit-remaining-requests': 0}
    if body_kind == 'structured':
        assert details['code'] == 429 and details['error_type'] == 'rate_limit_exceeded'
        assert details['metadata_status'] == 'object' and details['other_metadata_present']
        assert details['omitted_metadata_fields'] == ['provider_code', 'limit_source']
    else:
        assert details['metadata_status'] == 'unavailable' and 'code' not in details
    assert details['body_status'] == {'structured': 'json', 'malformed': 'invalid_json',
        'oversized': 'oversized', 'nested': 'invalid_json', 'read_failed': 'read_failed'}[body_kind]
    assert error['retry_after'] == '60' and details['retry_after_status'] == 'retained'
    assert error['http_status'] == 429 and error['reservation_retained']
    assert len(calls) == 1 and transport.pending == {'a': Settings().reserve}
    assert response_body.closed and 'provider_code' not in details
    saved = ''.join(p.read_text() for p in tmp_path.rglob('*.json*'))
    assert secret not in saved and 'account_id' not in saved


@pytest.mark.parametrize('streamed', [False, True])
@pytest.mark.parametrize('delay,expected', [
    ('120', '120'), ('Fri, 30 Oct 2026 13:40:00 GMT', 'Fri, 30 Oct 2026 13:40:00 GMT'),
    ('fixture-private-header-canary', None), ('120; fixture-private-header-canary', None),
    ('Fri, 32 Oct 2026 13:40:00 GMT', None), (None, None),
])
def test_provider_attribution_and_retry_delay_are_diagnostics_not_retry_authority(
        tmp_path, monkeypatch, solver_request, meta, streamed, delay, expected):
    import io
    import urllib.error
    from vao.repair import provider
    from vao.repair.streaming import StreamingOpenRouterTransport, StreamingSettings

    calls = []
    secret = 'fixture-private-header-canary'
    payload = {'error': {'code': 429, 'message': secret, 'metadata': {
        'provider_name': 'Parasail', 'provider_code': 429, 'error_type': 'rate_limit_exceeded',
        'raw': secret, 'unknown-private-key': secret}}}
    headers = {} if delay is None else {'retry-after': delay}
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 429, secret, headers,
                                         io.BytesIO(canonical(payload).encode()))
    monkeypatch.setattr(provider.urllib.request, 'build_opener', lambda *_: Opener())
    for folder in ['requests', 'receipts']:
        (tmp_path/folder).mkdir()
    transport = (StreamingOpenRouterTransport(tmp_path, secret, StreamingSettings(), authorized_limit_usd='.60')
                 if streamed else OpenRouterTransport(tmp_path, secret, Settings(), authorized_limit_usd='.60'))
    transport.ready = True
    with pytest.raises(ProviderStopped): transport.complete(solver_request, meta)
    with pytest.raises(ProviderStopped): transport.complete(solver_request, {**meta, 'attempt_id': 'b'})
    error = rows(tmp_path/'provider-errors.jsonl')[0]
    assert error['retry_after'] == expected
    details = error['error_details']
    assert details['retry_after_status'] == ('absent' if delay is None else 'retained' if expected else 'omitted')
    assert details['provider_name'] == 'Parasail' and details['provider_code'] == 429
    assert details['omitted_metadata_fields'] == [] and details['other_metadata_present']
    assert len(calls) == 1 and transport.pending == {'a': Settings().reserve}
    assert [r['event'] for r in rows(tmp_path/'ledger.jsonl')] == ['reserve']
    assert not list((tmp_path/'receipts').iterdir())
    saved = ''.join(p.read_text() for p in tmp_path.rglob('*.json*'))
    assert secret not in saved and 'unknown-private-key' not in saved


def test_absent_metadata_is_distinct_from_filtered_or_malformed_metadata():
    from vao.repair.provider import safe_error_details
    assert safe_error_details({'error': {'code': 429}})['metadata_status'] == 'absent'
    assert safe_error_details({'error': {'metadata': None}})['metadata_status'] == 'non_object'
    filtered = safe_error_details({'error': {'metadata': {
        'provider_name': 'PRIVATE-NAME', 'provider_code': True,
        'limit_source': 'PRIVATE-SOURCE', 'reason': 'PRIVATE-REASON'}}})
    assert filtered['metadata_status'] == 'object'
    assert set(filtered['omitted_metadata_fields']) == {'provider_name', 'provider_code', 'limit_source', 'reason'}
    assert 'PRIVATE-' not in json.dumps(filtered)
    budget = safe_error_details({'error': {'code': 402, 'metadata': {
        'limit_source': 'openrouter_credits', 'reason': 'weight_exceeds_budget'}}})
    assert budget['limit_source'] == 'openrouter_credits' and budget['reason'] == 'weight_exceeds_budget'
