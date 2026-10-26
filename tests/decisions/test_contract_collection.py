"""Exercise funded collection with a mocked network, never live credentials."""
import json
from decimal import Decimal

import pytest

from vao.repair import contract_collection as cc
from vao.repair.contracts import construct
from vao.repair.environment import RepairTask, canonical
from vao.repair.provider import OpenRouterTransport, ProviderStopped
from vao.repair.records import rows

FIXED = 'def solve(x):\n    return x + 1\n'


class Verifier:
    def preflight(self):
        return {'test_double': True}

    def check(self, files, entrypoint, cases):
        passed = files['solution.py'] == FIXED
        return {'passed': passed, 'passed_cases': int(passed), 'total_cases': 1,
                'cases': [{'id': cases[0]['id'], 'passed': passed, 'observed': {'status': 'returned', 'value': 0}}],
                'verifier_seconds': .01}


def task():
    return RepairTask.from_dicts({'schema_version': 1, 'task_id': 'development/test',
        'instruction': 'Repair solve', 'entrypoint': {'module': 'solution', 'function': 'solve'},
        'files': {'solution.py': 'def solve(x):\n    return x\n'},
        'public_cases': [{'id': 'public', 'args': [1], 'expected': 2}],
        'provenance': {'kind': 'synthetic_engineering_fixture'}},
        {'cases': [{'id': 'SECRET_EVALUATOR_CANARY', 'args': [100], 'expected': 101}]})


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, 'source_commit', lambda: 'a'*40)
    monkeypatch.setattr(cc, 'RepairVerifier', Verifier)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'mock-bearer-canary')
    monkeypatch.setattr('vao.repair.provider.time.sleep', lambda *_: None)
    prior = tmp_path / 'prior.json'
    prior.write_text(json.dumps({'model_results': True, 'conservative_committed_usd': '0.01011411'}))
    config = {'status': 'authorized_contract_diagnostic', 'live_calls_enabled': True,
              'authorization_reference': 'TEST ONLY: mocked network', 'monetary_authorization_usd': '0.06',
              'cumulative_limit_usd': '0.60', 'minimum_request_interval_seconds': 60,
              'closed_pilot_report': str(prior)}
    packet = construct([task()], Verifier())
    return packet, config


def network(monkeypatch, failure=None, content_for=None):
    sent = []
    def exchange(self, endpoint, body=None):
        if endpoint.endswith('/endpoints'):
            return {'data': {'id': self.settings.model, 'endpoints': [{
                'tag': self.settings.endpoint, 'provider_name': 'Parasail', 'quantization': 'bf16',
                'context_length': 131072, 'max_completion_tokens': 117964,
                'supported_parameters': ['seed','temperature','max_tokens','response_format'],
                'pricing': {'prompt': '.00000004', 'completion': '.00000005'}}]}}
        if endpoint == '/key':return {'data': {'limit_remaining': 1}}
        if endpoint == '/credits':return {'data': {'total_credits': 1, 'total_usage': 0}}
        assert endpoint == '/chat/completions'
        sent.append(body)
        assert 'SECRET_EVALUATOR_CANARY' not in canonical(body)
        assert 'mock-bearer-canary' not in canonical(body)
        assert rows(self.output / 'ledger.jsonl')[-1]['event'] == 'reserve'
        if failure == 'timeout' and len(sent) == 2:
            raise TimeoutError('mock-bearer-canary')
        text = FIXED if 'response_format' not in body else canonical({'solution.py': FIXED})
        if failure == 'empty':text = '{}'
        if content_for is not None:text = content_for(body)
        result = {'id': 'mock-gen-' + str(len(sent)), 'model': self.settings.model, 'provider': 'Parasail',
                  'usage': {'cost': .00008, 'prompt_tokens': 100, 'completion_tokens': 10},
                  'choices': [{'finish_reason': 'stop', 'message': {'content': text}}]}
        if failure == 'overrun':result['usage']['cost'] = .07
        return result
    monkeypatch.setattr(OpenRouterTransport, '_exchange', exchange)
    return sent


def test_unfunded_or_underfunded_config_cannot_freeze(tmp_path, monkeypatch):
    packet, config = prepare(tmp_path, monkeypatch)
    for change in ({'live_calls_enabled': False}, {'authorization_reference': ''},
                   {'monetary_authorization_usd': '.001'}, {'monetary_authorization_usd': '.61'},
                   {'cumulative_limit_usd': '.06'}, {'minimum_request_interval_seconds': 0}):
        with pytest.raises(ValueError):
            cc.freeze(packet, {**config, **change}, tmp_path / 'rejected.json')
    assert not (tmp_path / 'rejected.json').exists()


def test_exact_three_contracts_and_paired_settings_are_sent_once(tmp_path, monkeypatch):
    packet, config = prepare(tmp_path, monkeypatch)
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    sent = network(monkeypatch)
    out, claims = tmp_path / 'run', tmp_path / 'claims'
    result = cc.collect(frozen, out, claim_root=claims)
    assert sent == [r['provider_body'] for r in packet['requests']]
    assert len(sent) == 3 and result['sealed'] and result['observations'] == 3
    assert result['settled_usd'] == '0.00024' and result['cumulative_committed_usd'] == '0.01035411'
    assert all(r['full_pass'] for r in rows(out / 'observations.jsonl'))
    with pytest.raises(FileExistsError):
        cc.collect(frozen, tmp_path / 'another', claim_root=claims)
    assert len(sent) == 3
    assert 'mock-bearer-canary' not in ''.join(p.read_text() for p in out.rglob('*.json*'))


def test_timeout_is_censored_reserved_and_stops_before_next_request(tmp_path, monkeypatch):
    packet, config = prepare(tmp_path, monkeypatch)
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    sent = network(monkeypatch, 'timeout')
    out, claims = tmp_path / 'run', tmp_path / 'claims'
    with pytest.raises(ProviderStopped):
        cc.collect(frozen, out, claim_root=claims)
    result = cc.audit(out)
    assert len(sent) == 2 and result['observations'] == 1 and not result['sealed']
    assert len(result['pending']) == 1
    assert result['study_committed_usd'] == '0.00159552'
    assert result['cumulative_committed_usd'] == '0.01170963'
    with pytest.raises(FileExistsError):
        cc.collect(frozen, tmp_path / 'retry', claim_root=claims)
    assert len(sent) == 2


def test_known_charge_above_reserve_is_not_hidden(tmp_path, monkeypatch):
    packet, config = prepare(tmp_path, monkeypatch)
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    sent = network(monkeypatch, 'overrun')
    out = tmp_path / 'run'
    with pytest.raises(ProviderStopped):
        cc.collect(frozen, out, claim_root=tmp_path / 'claims')
    result = cc.audit(out)
    assert len(sent) == 1 and result['study_committed_usd'] == '0.07' and result['cap_exceeded']
    assert result['observations'] == 0 and len(result['pending']) == 1


def test_empty_json_and_empty_python_module_are_different_diagnostics_not_success(tmp_path, monkeypatch):
    packet, config = prepare(tmp_path, monkeypatch)
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    network(monkeypatch, 'empty')
    out = tmp_path / 'run'
    cc.collect(frozen, out, claim_root=tmp_path / 'claims')
    obs = rows(out / 'observations.jsonl')
    assert all(not r['full_pass'] for r in obs)
    plain = next(r for r in obs if r['contract'] == 'python_text')
    assert plain['decoded']['artifact_valid'] and plain['decoded']['syntax_valid']
    assert not plain['decoded']['declared_entrypoint']
    assert all(not r['decoded']['artifact_valid'] for r in obs if r['contract'] != 'python_text')


def test_source_or_prior_drift_blocks_before_any_provider_call(tmp_path, monkeypatch):
    packet, config = prepare(tmp_path, monkeypatch)
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    sent = network(monkeypatch)
    monkeypatch.setattr(cc, 'source_commit', lambda: 'b'*40)
    with pytest.raises(ValueError, match='source'):
        cc.collect(frozen, tmp_path / 'run', claim_root=tmp_path / 'claims')
    monkeypatch.setattr(cc, 'source_commit', lambda: 'a'*40)
    __import__('pathlib').Path(config['closed_pilot_report']).write_text('{}')
    with pytest.raises(ValueError, match='prior evidence'):
        cc.collect(frozen, tmp_path / 'run', claim_root=tmp_path / 'claims')
    assert sent == []


def test_outcome_tampering_rejected_without_completion_seal(tmp_path, monkeypatch):
    packet, config = prepare(tmp_path, monkeypatch)
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    network(monkeypatch)
    out = tmp_path / 'run'
    cc.collect(frozen, out, claim_root=tmp_path / 'claims')
    (out / 'pilot-completion.json').unlink()
    obs = rows(out / 'observations.jsonl');obs[0]['full_pass'] = False
    (out / 'observations.jsonl').write_text(''.join(canonical(r)+'\n' for r in obs))
    with pytest.raises(ValueError, match='outcome'):
        cc.audit(out)


def test_paid_response_without_local_score_remains_accounted_and_unrepeated(tmp_path, monkeypatch):
    packet, config = prepare(tmp_path, monkeypatch)
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    sent = network(monkeypatch)
    class BrokenVerifier(Verifier):
        def check(self, files, *args):
            if files['solution.py'] == FIXED:raise RuntimeError('local verifier stopped')
            return super().check(files, *args)
    monkeypatch.setattr(cc, 'RepairVerifier', BrokenVerifier)
    out = tmp_path / 'run'
    with pytest.raises(RuntimeError):
        cc.collect(frozen, out, claim_root=tmp_path / 'claims')
    result = cc.audit(out)
    assert len(sent) == 1 and result['settled_usd'] == '0.00008'
    assert len(result['paid_without_outcome']) == 1 and result['observations'] == 0


def test_report_keeps_missing_cells_and_forbids_incomplete_gate(tmp_path, monkeypatch):
    from vao.analysis.contract_diagnostic import summarize, render
    packet, config = prepare(tmp_path, monkeypatch)
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    network(monkeypatch, 'timeout')
    out = tmp_path / 'run'
    with pytest.raises(ProviderStopped):
        cc.collect(frozen, out, claim_root=tmp_path / 'claims')
    report = summarize(out)
    assert report['gate'] == 'inconclusive_incomplete_bank' and report['fit_selector'] is False
    assert sum(t['missing'] for t in report['contract_table']) == 2
    assert all(t['engineering_eligible'] is None for t in report['contract_table'])
    assert any(t['selected_task_success_bounds'] == [0, 1] for t in report['contract_table'])
    assert sum(Decimal(t['committed_usd']) for t in report['contract_table']) == Decimal('.00159552')
    assert 'missing' in render(report)
    (out / 'interruption.json').unlink()
    with pytest.raises(ValueError, match='active'):
        summarize(out)


def test_full_36_cell_mock_bank_obeys_prespecified_gate_without_training(tmp_path, monkeypatch):
    from vao.analysis.contract_diagnostic import summarize
    _, config = prepare(tmp_path, monkeypatch)
    original = task()
    tasks = [RepairTask.from_dicts({**original.public, 'task_id': f'development/mock-{i}'}, json.loads(original.evaluator_json)) for i in range(12)]
    packet = construct(tasks, Verifier())
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    meta_by_body = {canonical(r['provider_body']): r['metadata'] for r in packet['requests']}
    def answer(body):
        meta = meta_by_body[canonical(body)]
        count = {'json_current': 4, 'json_example': 3, 'python_text': 0}[meta['contract']]
        source = FIXED if meta['task_index'] < count else original.public['files']['solution.py']
        return source if meta['contract'] == 'python_text' else canonical({'solution.py': source})
    sent = network(monkeypatch, content_for=answer)
    out = tmp_path / 'run'
    cc.collect(frozen, out, claim_root=tmp_path / 'claims')
    report = summarize(out)
    assert len(sent) == 36
    assert [r['full_successes'] for r in report['contract_table']] == [4, 3, 0]
    assert all(r['ready_source'] == 12 for r in report['contract_table'])
    assert report['engineering_candidate_for_future_calibration'] == 'json_current'
    assert report['fit_selector'] is False and len(report['task_table']) == 12
    assert report['accounting']['settled_usd'] == '0.00288'


def test_duplicate_provider_identity_stops_before_third_call(tmp_path, monkeypatch):
    packet, config = prepare(tmp_path, monkeypatch)
    frozen = cc.freeze(packet, config, tmp_path / 'freeze.json')
    sent = network(monkeypatch)
    original = OpenRouterTransport._exchange
    def duplicate(self, endpoint, body=None):
        result = original(self, endpoint, body)
        if body is not None:result['id'] = 'same-provider-generation'
        return result
    monkeypatch.setattr(OpenRouterTransport, '_exchange', duplicate)
    out = tmp_path / 'run'
    with pytest.raises(ProviderStopped, match='Repeated'):
        cc.collect(frozen, out, claim_root=tmp_path / 'claims')
    assert len(sent) == 2
    assert json.loads((out / 'interruption.json').read_text())['settled_usd'] == '0.00016'
    with pytest.raises(ValueError, match='Repeated provider'):
        cc.audit(out)
