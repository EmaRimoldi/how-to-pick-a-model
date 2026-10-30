"""Independent development calibration: exact controls, retained missing cells, no retries."""
import copy
import json
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest

from vao.repair import contract_collection as cc
from vao.repair import extension_information_study as ds
from vao.repair.contracts import EXTENSION_TRACE_STUDY, QWEN_TRACE_STUDY
from vao.repair.environment import canonical, identity
from vao.repair.provider import OpenRouterTransport, ProviderStopped
from vao.repair.records import rows
from vao.analysis.repair_information import summarize

# Reuse the same explicitly synthetic verifier/task fixture as the preceding tests.
spec = importlib.util.spec_from_file_location('qwen_information_fixture', Path(__file__).with_name('test_repair_qwen_information_study.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
Verifier, FIXED, BROKEN = fixture.Verifier, fixture.FIXED, fixture.BROKEN


def packet():
    return ds.construct(fixture.records()[:3], Verifier())


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, 'source_commit', lambda: 'b' * 40)
    monkeypatch.setattr(cc, 'RepairVerifier', Verifier)
    monkeypatch.setattr(ds, 'validate_origin', lambda p: None)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-not-a-real-key')
    sleeps = []
    monkeypatch.setattr('vao.repair.provider.time.sleep', lambda seconds: sleeps.append(seconds))
    prior = tmp_path / 'prior.json'
    prior.write_text(json.dumps({'study': QWEN_TRACE_STUDY, 'model_results': True,
        'status': 'incomplete_development_information_probe', 'gate': 'inconclusive_incomplete_bank',
        'fit_selector': False, 'accounting': {'cumulative_committed_usd': str(ds.CARRY)}}))
    config = {'status': 'authorized_contract_diagnostic', 'study': EXTENSION_TRACE_STUDY,
        'live_calls_enabled': True, 'authorization_reference': 'MOCK ONLY',
        'monetary_authorization_usd': '.18', 'cumulative_limit_usd': '.60',
        'minimum_request_interval_seconds': 60, 'closed_pilot_report': str(prior)}
    p = packet()
    return p, config, cc.freeze(p, config, tmp_path / 'freeze.json'), sleeps


def network(monkeypatch, p, failures=None, useful=False):
    failures = failures or {}
    sent = []
    metadata = {canonical(r['provider_body']): r['metadata'] for r in p['requests']}
    def exchange(self, endpoint, body=None):
        if endpoint.endswith('/endpoints'):
            return {'data': {'id': self.settings.model, 'endpoints': [{'tag': self.settings.endpoint,
                'provider_name': self.settings.provider_name, 'quantization': self.settings.quantization,
                'context_length': 131072, 'max_completion_tokens': 8192,
                'supported_parameters': ['seed', 'temperature', 'max_tokens', 'response_format'],
                'pricing': {'prompt': '.00000012', 'completion': '.00000080'}}]}}
        if endpoint == '/key': return {'data': {'limit_remaining': 1}}
        if endpoint == '/credits': return {'data': {'total_credits': 1, 'total_usage': 0}}
        assert endpoint == '/chat/completions' and 'HIDDEN_CANARY' not in canonical(body)
        assert rows(self.output / 'ledger.jsonl')[-1]['event'] == 'reserve'
        sent.append(body)
        failure = failures.get(len(sent))
        if failure in ('timeout', 'http'):
            raise ProviderStopped('test-not-a-real-key', http_status=429 if failure == 'http' else None,
                transport_kind='http_error' if failure == 'http' else 'TimeoutError',
                transport_phase='awaiting_response_headers', exchange_elapsed_seconds=180)
        meta = metadata[canonical(body)]
        fixed = useful and meta['arm'] == 'focused_trace'
        return {'id': f'extension-mock-{len(sent)}', 'model': self.settings.model, 'provider': self.settings.provider_name,
            'usage': {'cost': .19 if failure == 'overrun' else .00008, 'prompt_tokens': 100, 'completion_tokens': 10},
            'choices': [{'finish_reason': 'stop', 'message': {'content': canonical({'solution.py': FIXED if fixed else BROKEN})}}]}
    monkeypatch.setattr(OpenRouterTransport, '_exchange', exchange)
    return sent


def test_exact_design_same_information_controls_hidden_independence():
    p = packet()
    assert len(p['requests']) == 24 and len(p['tasks']) == 3
    assert p['maximum_new_reservations_usd'] == '0.17301504'
    assert p['maximum_cumulative_commitment_usd'] == '0.25893779'
    assert p['design']['transport_missing_policy']['maximum_retained_errors_before_continuing'] == 1
    for i in range(0, 24, 2):
        pair = p['requests'][i:i+2]
        assert len({r['provider_body']['seed'] for r in pair}) == 1
        payloads = []
        for r in pair:
            body = json.loads(r['provider_body']['messages'][1]['content'])
            body.pop('runtime_diagnostic', None)
            payloads.append(body)
        assert payloads[0] == payloads[1]
    changed = fixture.records()[:3]
    for r in changed:
        r['evaluator']['cases'][0]['expected'] = -100
        r['source_full_pass'] = True
    q = ds.construct(changed, Verifier())
    assert [r['provider_body'] for r in p['requests']] == [r['provider_body'] for r in q['requests']]
    p['design']['transport_missing_policy']['maximum_retained_errors_before_continuing'] = 2
    p['packet_id'] = identity({k:v for k,v in p.items() if k != 'packet_id'})
    with pytest.raises(ValueError): ds.validate_packet(p)


@pytest.mark.parametrize('useful,gate', [(False, 'no_repeated_information_benefit_demonstrated'),
                                        (True, 'candidate_for_independent_acquisition_calibration')])
def test_complete_bank_and_fixed_screen_remain_development_only(tmp_path, monkeypatch, useful, gate):
    p, config, frozen, _ = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, p, useful=useful)
    output = tmp_path / 'run'
    cc.collect(frozen, output, claim_root=tmp_path / 'claims')
    r = summarize(output)
    assert len(sent) == 24 and r['gate'] == gate and r['fit_selector'] is False
    assert r['accounting']['sealed'] and len(r['task_table']) == 3
    assert Decimal(r['accounting']['cumulative_committed_usd']) == ds.CARRY + Decimal('.00192')
    assert len({canonical(b) for b in sent}) == 24


def test_one_unknown_keeps_reserve_and_continues_only_new_cells(tmp_path, monkeypatch):
    p, config, frozen, sleeps = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, p, {2:'timeout'}, useful=True)
    output = tmp_path / 'run'
    audit = cc.collect(frozen, output, claim_root=tmp_path / 'claims')
    r = summarize(output)
    assert len(sent) == 24 and len({canonical(b) for b in sent}) == 24
    assert audit['admissions'] == 24 and audit['observations'] == 23
    assert len(audit['pending']) == 1 and not audit['sealed']
    assert r['gate'] == 'inconclusive_incomplete_bank' and not r['fit_selector']
    assert sum(a['missing'] for a in r['arm_table']) == 1
    assert r['contrasts']['focused_trace_minus_focused']['mean_difference'] is None
    assert r['contrasts']['focused_trace_minus_focused']['descriptive_bug_bootstrap_95'] is None
    assert Decimal(audit['cumulative_committed_usd']) == ds.CARRY + Decimal('.00184') + Decimal('.00720896')
    assert sleeps.count(120) == 1
    missing = p['requests'][1]['metadata']['attempt_id']
    assert missing in audit['pending'] and not (output/'receipts'/(missing+'.json')).exists()
    with pytest.raises(FileExistsError): cc.collect(frozen, tmp_path/'duplicate', claim_root=tmp_path/'claims')
    # Removing the error disposition cannot make a later admission valid.
    ledger = output/'ledger.jsonl'
    ledger.write_text(''.join(canonical(e)+'\n' for e in rows(ledger) if e['event']!='retain_unknown'))
    with pytest.raises(ValueError, match='Repeated admission'): cc.audit(output)
    assert len(sent) == 24


def test_second_uncertainty_stops_without_releasing_either_reserve(tmp_path, monkeypatch):
    p, config, frozen, sleeps = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, p, {2:'timeout', 5:'timeout'})
    output = tmp_path/'run'
    with pytest.raises(ProviderStopped): cc.collect(frozen, output, claim_root=tmp_path/'claims')
    a=cc.audit(output);r=summarize(output)
    assert len(sent)==5 and len(a['pending'])==2 and a['observations']==3
    assert Decimal(a['study_committed_usd'])==Decimal('.00024')+2*Decimal('.00720896')
    assert sum(t['missing'] for t in r['arm_table'])==21 and sleeps.count(120)==1


@pytest.mark.parametrize('failure', ['http','overrun'])
def test_nontransport_failures_are_always_terminal(tmp_path, monkeypatch, failure):
    p, config, frozen, sleeps = prepare(tmp_path, monkeypatch)
    sent=network(monkeypatch,p,{2:failure})
    output=tmp_path/'run'
    with pytest.raises(ProviderStopped):cc.collect(frozen,output,claim_root=tmp_path/'claims')
    a=cc.audit(output)
    assert len(sent)==2 and len(a['pending'])==1 and 120 not in sleeps
    if failure=='overrun':
        assert a['cap_exceeded'] and Decimal(a['study_committed_usd'])==Decimal('.19008')


def test_missing_disposition_cannot_settle_an_unknown_charge(tmp_path, monkeypatch):
    p, config, frozen, _=prepare(tmp_path,monkeypatch)
    network(monkeypatch,p,{2:'timeout'})
    output=tmp_path/'run';cc.collect(frozen,output,claim_root=tmp_path/'claims')
    ledger=output/'ledger.jsonl';events=rows(ledger)
    pos=next(i for i,e in enumerate(events) if e['event']=='retain_unknown')
    events.insert(pos+1,{'event':'settle','attempt_id':events[pos]['attempt_id'],'usd':'0','currency':'USD'})
    ledger.write_text(''.join(canonical(e)+'\n' for e in events))
    with pytest.raises(ValueError,match='Invalid settlement'):cc.audit(output)
