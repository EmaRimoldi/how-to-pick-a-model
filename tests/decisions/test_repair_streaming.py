"""Offline SSE fault injection: no real credentials, socket or model calls."""
from copy import deepcopy
from decimal import Decimal
from email.message import Message
import io
import json
import urllib.error

import pytest

from vao.repair import streaming
from vao.repair.provider import ProviderStopped, Settings
from vao.repair.records import rows
from vao.repair.streaming import ChatStream, SSEFrames, StreamingOpenRouterTransport, StreamingSettings

SECRET = 'synthetic-bearer-canary-for-redaction'
REQUEST = {'mode': 'model_pilot', 'provider_call_enabled': True,
           'messages': [{'role': 'system', 'content': 'Return JSON'}, {'role': 'user', 'content': 'Offline mock'}]}
META = {'attempt_id': 'a', 'trajectory': 'synthetic', 'phase': 'branch', 'depth': 1, 'draw': 0}
USAGE = {'prompt_tokens': 100, 'completion_tokens': 10, 'total_tokens': 110, 'cost': .00008}


def chunk(content=None, finish=None, usage=None, **extra):
    p = {'id': 'gen-synthetic', 'model': Settings().model, 'provider': 'Parasail',
         'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': finish}], **extra}
    if usage is not None:
        p['usage'] = usage
    return p


def events(content='{"value":"caffè ☕"}', finish='stop'):
    return [chunk(content[:8]), chunk(content[8:], finish), chunk('', finish, deepcopy(USAGE)), '[DONE]']


def wire(es, newline='\n'):
    out = ': synthetic keepalive'+newline+newline
    for p in es:
        out += 'data: '+(p if isinstance(p, str) else json.dumps(p, ensure_ascii=False))+newline+newline
    return out.encode()


def decode(data, size):
    frames, stream = SSEFrames(), ChatStream(Settings().model, 'Parasail')
    for i in range(0, len(data), size):
        for event in frames.feed(data[i:i+size]):
            stream.consume(event)
    return stream.result(), frames


@pytest.mark.parametrize('size', [1, 2, 7, 127, 4096])
@pytest.mark.parametrize('newline', ['\n', '\r', '\r\n'])
def test_utf8_framing_and_terminal_usage_are_chunk_boundary_independent(size, newline):
    payload, framing = decode(b'\xef\xbb\xbf'+wire(events(), newline), size)
    assert payload['choices'][0]['message']['content'] == '{"value":"caffè ☕"}'
    assert payload['usage'] == USAGE and framing.comments == 1
    assert framing.events == 4 and payload['reconstructed_from_sse']


def test_multiline_data_and_sse_reconnect_fields_do_not_dispatch():
    f = SSEFrames()
    es = f.feed(b'id: untrusted\r\nretry: 1\r\n: ping\r\ndata: {"x":\r\ndata: 1}\r\n\r\n')
    assert es == ['{"x":\n1}'] and f.comments == 1
    assert streaming.strict_json(es[0]) == {'x': 1}


def test_settings_only_change_stream_and_leave_historical_contract_unchanged():
    old = Settings().body(REQUEST, META)
    new = StreamingSettings().body(REQUEST, META)
    assert old['stream'] is False and new == {**old, 'stream': True}
    assert StreamingSettings().reserve == Settings().reserve


def client(tmp_path, monkeypatch, es=None, *, failure=None, size=4096, content_type='text/event-stream'):
    for d in ['requests', 'receipts']:
        (tmp_path/d).mkdir()
    transport = StreamingOpenRouterTransport(tmp_path, SECRET, StreamingSettings(), authorized_limit_usd='.60')
    transport.ready = True  # Unit fixture only; production still requires preflight.
    calls, closed = [], []
    data = wire(events() if es is None else es)

    class Response:
        def __init__(self):
            self.data = io.BytesIO(data)
            self.headers = Message()
            self.headers['Content-Type'] = content_type
        def __enter__(self):return self
        def __exit__(self, *_):closed.append(True)
        def read1(self, _):
            b = self.data.read(size)
            if b:return b
            if failure == 'body':raise ConnectionResetError(SECRET)
            return b''

    class Opener:
        def open(self, request, timeout):
            calls.append((request.full_url, json.loads(request.data), timeout))
            assert rows(tmp_path/'ledger.jsonl')[-1]['event'] == 'reserve'
            if failure == 'headers':raise TimeoutError(SECRET)
            if failure == 'http':
                raise urllib.error.HTTPError(request.full_url, 429, SECRET, {},
                                             io.BytesIO(json.dumps({'error': {'code': 429, 'message': SECRET}}).encode()))
            return Response()
    monkeypatch.setattr(streaming.urllib.request, 'build_opener', lambda *_: Opener())
    return transport, calls, closed


def assert_no_secret(root):
    assert SECRET not in ''.join(p.read_text() for p in root.rglob('*.json*'))


def test_completed_stream_settles_once_and_redacts_content_across_chunks(tmp_path, monkeypatch):
    t, calls, closed = client(tmp_path, monkeypatch, events(SECRET), size=3)
    result = t.complete(REQUEST, META)
    assert result['content'] == '[REDACTED]' and result['cost_usd'] == '0.00008'
    assert [r['event'] for r in rows(tmp_path/'ledger.jsonl')] == ['reserve', 'settle']
    assert not t.pending and t.conservative_committed_usd == Decimal('.00008')
    assert len(calls) == len(closed) == 1 and calls[0][1]['stream'] is True
    with pytest.raises(ProviderStopped):t.complete(REQUEST, META)
    assert len(calls) == 1
    m=json.loads((tmp_path/'stream-metrics/a.json').read_text())
    assert m['stream_complete'] and m['done_received'] and m['usage_received']
    assert m['partial_content_persisted'] is False
    assert_no_secret(tmp_path)


@pytest.mark.parametrize('finish', ['length', 'content_filter'])
def test_bad_or_truncated_model_artifact_with_complete_receipt_is_still_billed(tmp_path, monkeypatch, finish):
    t, _, _ = client(tmp_path, monkeypatch, events('{"incomplete":', finish))
    result=t.complete(REQUEST,META)
    assert result['finish_reason']==finish and result['content']=='{"incomplete":'
    assert not t.pending and t.spent == Decimal('.00008')


def damaged(case):
    es=events(SECRET)
    if case=='no_usage':return es[:2]+['[DONE]']
    if case=='no_done':return es[:-1]
    if case=='partial':return es[:1]
    if case=='wrong_model':es[1]['model']='different'
    if case=='wrong_provider':es[1]['provider']='different'
    if case=='wrong_id':es[1]['id']='gen-other'
    if case=='multiple':es[1]['choices'].append(deepcopy(es[1]['choices'][0]))
    if case=='noninteger_index':es[1]['choices'][0]['index']=False
    if case=='after_finish':es.insert(2,chunk(SECRET))
    if case=='duplicate_usage':es.insert(3,deepcopy(es[2]))
    if case=='finish_mismatch':es[2]['choices'][0]['finish_reason']='length'
    if case=='bad_tokens':es[2]['usage']['total_tokens']=True
    if case=='bad_sum':es[2]['usage']['total_tokens']=111
    if case=='negative_cost':es[2]['usage']['cost']=-1
    if case=='no_cost':del es[2]['usage']['cost']
    if case=='error':es=[chunk(error={'code':500,'message':SECRET})]
    if case=='choice_error':es[1]['choices'][0]['error']={'message':SECRET}
    if case=='tool_call':es[1]['choices'][0]['delta']['tool_calls']=[{'function':SECRET}]
    if case=='duplicate_key':return ['{"id":"gen-synthetic","id":"other"}']
    if case=='nonfinite':return ['{"usage":{"cost":NaN}}']
    if case=='empty_identity':es[2]['provider']=''
    return es


@pytest.mark.parametrize('case', ['no_usage','no_done','partial','wrong_model','wrong_provider','wrong_id',
    'multiple','noninteger_index','after_finish','duplicate_usage','finish_mismatch','bad_tokens',
    'bad_sum','negative_cost','no_cost','error','choice_error','tool_call','duplicate_key','nonfinite','empty_identity'])
def test_invalid_or_incomplete_stream_keeps_reserve_and_stops(tmp_path, monkeypatch, case):
    t, calls, closed=client(tmp_path,monkeypatch,damaged(case),size=13)
    with pytest.raises(ProviderStopped):t.complete(REQUEST,META)
    assert t.pending == {'a':t.reserve} and t.conservative_committed_usd >= t.reserve
    assert len(rows(tmp_path/'ledger.jsonl'))==1 and len(calls)==len(closed)==1
    assert not list((tmp_path/'receipts').iterdir())
    with pytest.raises(ProviderStopped):t.complete(REQUEST,{**META,'attempt_id':'b'})
    assert len(calls)==1
    assert_no_secret(tmp_path)


@pytest.mark.parametrize('failure,phase', [('headers','awaiting_response_headers'),('body','reading_stream'),('http','awaiting_response_headers')])
def test_transport_failures_keep_uncertainty_and_close_acquired_response(tmp_path,monkeypatch,failure,phase):
    t,calls,closed=client(tmp_path,monkeypatch,events(SECRET)[:1],failure=failure)
    with pytest.raises(ProviderStopped):t.complete(REQUEST,META)
    error=rows(tmp_path/'provider-errors.jsonl')[0]
    assert error['transport_phase']==phase and error['reservation_retained']
    assert len(calls)==1 and bool(closed)==(failure=='body')
    assert error['http_status']==(429 if failure=='http' else None)
    assert t.conservative_committed_usd == t.reserve
    assert_no_secret(tmp_path)


def test_lost_done_after_cost_overrun_keeps_larger_observed_charge(tmp_path,monkeypatch):
    es=events()[:-1];es[-1]['usage']['cost']=.2
    t,_,_=client(tmp_path,monkeypatch,es,failure='body')
    with pytest.raises(ProviderStopped):t.complete(REQUEST,META)
    assert t.conservative_committed_usd==Decimal('.2') and t.pending=={'a':t.reserve}
    assert rows(tmp_path/'provider-errors.jsonl')[0]['conservative_committed_usd']=='0.2'
    assert json.loads((tmp_path/'stream-metrics/a.json').read_text())['reported_cost_usd']=='0.2'


def test_complete_receipt_overrun_is_retained_without_false_settlement(tmp_path,monkeypatch):
    es=events();es[-2]['usage']['cost']=.2
    t,_,_=client(tmp_path,monkeypatch,es)
    with pytest.raises(ProviderStopped):t.complete(REQUEST,META)
    assert t.conservative_committed_usd==Decimal('.2') and t.pending
    assert (tmp_path/'receipts/a.raw.json').exists() and not (tmp_path/'receipts/a.json').exists()


def test_non_sse_response_is_not_reinterpreted_as_fallback(tmp_path,monkeypatch):
    t,calls,_=client(tmp_path,monkeypatch,content_type='application/json')
    with pytest.raises(ProviderStopped):t.complete(REQUEST,META)
    assert len(calls)==1 and t.pending
    assert json.loads((tmp_path/'stream-metrics/a.json').read_text())['protocol_error']=='unexpected_content_type'


def test_empty_choices_accounting_frame_and_done_repetition_do_not_duplicate_content():
    es=events();es[-2]['choices']=[];es+=['[DONE]',chunk('ignored after DONE')]
    payload,_=decode(wire(es),1)
    assert payload['usage']==USAGE and payload['choices'][0]['message']['content']=='{"value":"caffè ☕"}'


def test_wire_bound_and_invalid_utf8_are_rejected():
    with pytest.raises(streaming.StreamProtocolError,match='wire_limit'):SSEFrames(max_bytes=10).feed(b'x'*11)
    with pytest.raises(UnicodeDecodeError):SSEFrames().feed(b'\xff')
    with pytest.raises(streaming.StreamProtocolError,match='line_limit'):SSEFrames().feed(b'data: '+b'x'*65536)
