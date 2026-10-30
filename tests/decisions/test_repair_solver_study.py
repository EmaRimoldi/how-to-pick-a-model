"""Solver control: public-only projection, repeated success, missingness and billing."""
import copy
from decimal import Decimal
import hashlib
import json
import zipfile

import pytest

from vao.analysis.repair_solver import summarize, render
from vao.repair import contract_collection as cc
from vao.repair import solver_study as study
from vao.repair.contracts import INTERFACE_STUDY, SOLVER_STUDY
from vao.repair.environment import canonical, identity
from vao.repair.provider import OpenRouterTransport, ProviderStopped
from vao.repair.records import rows

BROKEN = '# Adapted from test/project; upstream definitions are unchanged.\ndef solve(x):\n    return 0\n'
FIXED = BROKEN.replace('return 0', 'return x')


class Verifier:
    def preflight(self):
        return {'test_double': True}

    def check(self, files, entry, cases):
        code = files['solution.py']
        observations = []
        for c in cases:
            value = c['args'][0] if 'return x' in code else (2 if 'return 2' in code else 0)
            observations.append({'id': c['id'], 'passed': value == c['expected'],
                                 'observed': {'status': 'returned', 'value': value}})
        return {'passed': all(c['passed'] for c in observations),
            'passed_cases': sum(c['passed'] for c in observations), 'total_cases': len(cases),
            'cases': observations, 'verifier_seconds': .01}


def records():
    result = []
    for i in range(12):
        public = {'schema_version': 1, 'task_id': f'development/mock-{i}', 'instruction': 'Return x',
            'entrypoint': {'module': 'solution', 'function': 'solve'}, 'files': {'solution.py': BROKEN if i < 8 else FIXED},
            'public_cases': [{'id': 'public', 'args': [2], 'expected': 2}], 'provenance': {'kind': 'engineering'}}
        feedback = Verifier().check(public['files'], public['entrypoint'], public['public_cases'])
        feedback.pop('verifier_seconds')
        result.append({'public': public, 'evaluator': {'cases': [{'id': 'HIDDEN_CANARY', 'args': [99], 'expected': 99}]},
            'source_attempt_id': f'source-{i}', 'source_task_hash': f'task-{i}', 'source_artifact': f'artifact-{i}',
            'source_cost_usd': '.0001', 'source_public_result': feedback, 'source_full_pass': i >= 8})
    return result


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, 'source_commit', lambda: 'a' * 40)
    monkeypatch.setattr(cc, 'RepairVerifier', Verifier)
    monkeypatch.setattr(study, 'validate_origin', lambda p: None)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'mock-key-only')
    monkeypatch.setattr('vao.repair.provider.time.sleep', lambda *_: None)
    prior = tmp_path / 'prior.json'
    prior.write_text(json.dumps({'model_results': True, 'study': INTERFACE_STUDY,
        'status': 'incomplete_development_interface_probe', 'gate': 'inconclusive_incomplete_bank',
        'fit_selector': False, 'accounting': {'cumulative_committed_usd': str(study.CARRY)}}))
    config = {'status': 'authorized_contract_diagnostic', 'study': SOLVER_STUDY, 'live_calls_enabled': True,
        'authorization_reference': 'TEST ONLY MOCK TRANSPORT', 'monetary_authorization_usd': '.24',
        'cumulative_limit_usd': '.60', 'minimum_request_interval_seconds': 60, 'closed_pilot_report': str(prior)}
    packet = study.construct(records(), Verifier())
    return packet, config, cc.freeze(packet, config, tmp_path / 'freeze.json')


def network(monkeypatch, packet, *, mode='none', fail_at=None):
    sent = []
    metadata = {canonical(r['provider_body']): r['metadata'] for r in packet['requests']}
    def exchange(self, endpoint, body=None):
        if endpoint.endswith('/endpoints'):
            return {'data': {'id': self.settings.model, 'endpoints': [{'tag': self.settings.endpoint,
                'provider_name': self.settings.provider_name, 'quantization': self.settings.quantization,
                'context_length': 131072, 'max_completion_tokens': 8192,
                'supported_parameters': ['seed', 'temperature', 'max_tokens', 'response_format'],
                'pricing': {'prompt': '.00000012', 'completion': '.0000008', 'input_cache_read': '.00000007'}}]}}
        if endpoint == '/key': return {'data': {'limit_remaining': 1}}
        if endpoint == '/credits': return {'data': {'total_credits': 1, 'total_usage': 0}}
        assert endpoint == '/chat/completions' and 'HIDDEN_CANARY' not in canonical(body)
        assert rows(self.output / 'ledger.jsonl')[-1]['event'] == 'reserve'
        sent.append(body)
        if len(sent) == fail_at:
            raise ProviderStopped('mock error', http_status=429)
        meta = metadata[canonical(body)]
        fixed = meta['task_index'] < 3 and meta['draw'] in ({0, 2} if mode == 'repeated' else {0, 1}) and mode in ('repeated', 'one_half')
        code = FIXED if fixed else BROKEN
        if mode == 'false_positive': code = BROKEN.replace('return 0', 'return 2')
        return {'id': f'mock-{len(sent)}', 'model': self.settings.model, 'provider': self.settings.provider_name,
            'usage': {'cost': .0001, 'prompt_tokens': 100, 'completion_tokens': 10},
            'choices': [{'finish_reason': 'stop', 'message': {'content': canonical({'solution.py': code})}}]}
    monkeypatch.setattr(OpenRouterTransport, '_exchange', exchange)
    return sent


def test_same_original_messages_hidden_data_exclusion_and_exact_replicates():
    from vao.repair.interface_study import project
    packet = study.construct(records(), Verifier())
    assert len(packet['tasks']) == 12 and len(packet['requests']) == 32
    assert packet['maximum_new_reservations_usd'] == '0.23068672'
    assert packet['maximum_cumulative_commitment_usd'] == '0.28195411'
    for row in packet['requests']:
        source = packet['tasks'][row['metadata']['task_index']]
        assert row['request']['messages'] == project(source, 'original')['messages']
        assert row['provider_body']['provider']['only'] == ['parasail/bf16']
        assert row['provider_body']['provider']['allow_fallbacks'] is False
        assert 'HIDDEN_CANARY' not in canonical(row['provider_body'])
    changed = records()
    for r in changed:
        r['evaluator']['cases'][0]['expected'] = -1
        r['source_full_pass'] = not r['source_full_pass']
    other = study.construct(changed, Verifier())
    assert [r['provider_body'] for r in packet['requests']] == [r['provider_body'] for r in other['requests']]


@pytest.mark.parametrize('mode,successes,passed', [('none', 0, False), ('repeated', 6, True), ('one_half', 6, False), ('false_positive', 0, False)])
def test_engineering_screen_requires_repeated_full_repairs_not_public_scores(tmp_path, monkeypatch, mode, successes, passed):
    packet, _, frozen = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, packet, mode=mode)
    output = tmp_path / 'run'
    cc.collect(frozen, output, claim_root=tmp_path / 'claims')
    report = summarize(output)
    assert len(sent) == 32 and len(report['task_table']) == 12
    assert report['summary']['successes'] == successes
    assert report['summary']['mean_success'] == successes / 32
    assert report['summary']['false_positives'] == (32 if mode == 'false_positive' else 0)
    assert report['gate'] == ('candidate_for_separate_intervention_calibration' if passed else 'no_repeated_solver_compatibility_demonstrated')
    assert not report['fit_selector'] and not report['causal_model_comparison']
    assert Decimal(report['accounting']['cumulative_committed_usd']) == study.CARRY + Decimal('.0032')
    with pytest.raises(FileExistsError): cc.collect(frozen, tmp_path / 'duplicate', claim_root=tmp_path / 'claims')
    from vao.analysis.contract_diagnostic import summarize as historical
    with pytest.raises(ValueError, match='solver-compatibility report'): historical(output)


def test_interruption_retains_all_cells_reserve_and_terminal_only_analysis(tmp_path, monkeypatch):
    packet, _, frozen = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, packet, fail_at=4)
    output = tmp_path / 'run'
    with pytest.raises(ProviderStopped): cc.collect(frozen, output, claim_root=tmp_path / 'claims')
    report = summarize(output)
    assert len(sent) == 4 and report['summary']['observed'] == 3 and report['summary']['missing'] == 29
    assert report['summary']['success_bounds'] == [0, 29/32]
    assert len(report['accounting']['pending']) == 1
    assert Decimal(report['accounting']['cumulative_committed_usd']) == study.CARRY + Decimal('.0003') + Decimal('.00720896')
    assert report['gate'] == 'inconclusive_incomplete_bank'
    assert report['summary']['mean_success'] is None and report['summary']['descriptive_bug_bootstrap_95'] is None
    (output / 'interruption.json').unlink()
    with pytest.raises(ValueError, match='active treatment'): summarize(output)


def test_rehashed_plan_drift_and_unfunded_or_wrong_prior_are_rejected(tmp_path, monkeypatch):
    packet, config, _ = prepare(tmp_path, monkeypatch)
    for mutate in (lambda p: p['requests'].reverse(), lambda p: p.update(closed_pilot_commitment_usd='0'),
                   lambda p: p['design'].update(draws_per_checkpoint=2),
                   lambda p: p['requests'][0]['provider_body'].update(temperature=1)):
        changed = copy.deepcopy(packet); mutate(changed)
        changed['packet_id'] = identity({k: v for k, v in changed.items() if k != 'packet_id'})
        with pytest.raises(ValueError): study.validate_packet(changed)
    config['live_calls_enabled'] = False
    with pytest.raises(ValueError, match='authorization'): cc.freeze(packet, config, tmp_path / 'disabled.json')
    config['live_calls_enabled'] = True
    prior = json.loads((tmp_path / 'prior.json').read_text()); prior['study'] = 'some_other_study'
    (tmp_path / 'prior.json').write_text(json.dumps(prior))
    with pytest.raises(ValueError, match='closed incomplete interface'): cc.freeze(packet, config, tmp_path / 'wrong.json')


def test_archived_solver_report_dispatch_and_independent_replay(tmp_path, monkeypatch):
    from vao.analysis import contract_verification as cv
    packet, _, frozen = prepare(tmp_path, monkeypatch)
    network(monkeypatch, packet, fail_at=4)
    output = tmp_path / 'run'
    with pytest.raises(ProviderStopped): cc.collect(frozen, output, claim_root=tmp_path / 'claims')
    report = summarize(output)
    delivery = tmp_path / 'delivery'; delivery.mkdir()
    (delivery / 'analysis.json').write_text(json.dumps(report))
    (delivery / 'REPORT.md').write_text(render(report))
    members = {'collection/' + p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob('*') if p.is_file()}
    archive = delivery / 'evidence.zip'
    with zipfile.ZipFile(archive, 'w') as zipped:
        for name, content in members.items(): zipped.writestr(name, content)
    (delivery / 'evidence-manifest.json').write_text(json.dumps({'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'files': {name: hashlib.sha256(content).hexdigest() for name, content in members.items()}}))
    monkeypatch.setattr(cv, 'RepairVerifier', Verifier)
    cv.reproduce(delivery, tmp_path / 'replay.json')
    replay = json.loads((tmp_path / 'replay.json').read_text())
    assert replay['full_analysis_and_markdown_reproduced'] and replay['checked_evaluation_records'] == 6
    assert not replay['discrepancies']
