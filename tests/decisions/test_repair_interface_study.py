"""Factorial isolation, prospective analysis and one-use funded boundaries."""
import ast
import copy
import json
from collections import Counter
from decimal import Decimal

import pytest

from vao.analysis.repair_interface import linear_bounds, summarize
from vao.repair import contract_collection as cc
from vao.repair import interface_study as study
from vao.repair.contracts import TRACE_STUDY, INTERFACE_STUDY
from vao.repair.environment import canonical, identity
from vao.repair.provider import OpenRouterTransport, ProviderStopped
from vao.repair.records import rows

HEADER = '# Adapted from test/project; upstream definitions are unchanged.\n# License: test-only\n'
BROKEN = HEADER + 'def helper(x):\n    return 0\ndef solve(x):\n    return helper(x)\n'
FIXED = HEADER + 'def helper(x):\n    return x\ndef solve(x):\n    return helper(x)\n'


class Verifier:
    def preflight(self):
        return {'test_double': True}

    def check(self, files, entry, cases):
        passed = 'return x\n' in files['solution.py']
        return {'passed': passed, 'passed_cases': int(passed), 'total_cases': 1,
            'cases': [{'id': cases[0]['id'], 'passed': passed,
                       'observed': {'status': 'returned', 'value': cases[0]['args'][0] if passed else 0}}],
            'verifier_seconds': .01}


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
    prior.write_text(json.dumps({'model_results': True, 'study': TRACE_STUDY,
        'status': 'incomplete_development_information_probe', 'gate': 'inconclusive_incomplete_bank',
        'fit_selector': False, 'accounting': {'cumulative_committed_usd': str(study.CARRY)}}))
    config = {'status': 'authorized_contract_diagnostic', 'study': INTERFACE_STUDY, 'live_calls_enabled': True,
        'authorization_reference': 'TEST ONLY MOCK TRANSPORT', 'monetary_authorization_usd': '.43',
        'cumulative_limit_usd': '.60', 'minimum_request_interval_seconds': 30, 'closed_pilot_report': str(prior)}
    packet = study.construct(records(), Verifier())
    return packet, config, cc.freeze(packet, config, tmp_path / 'freeze.json')


def network(monkeypatch, packet, *, useful=False, fail_at=None):
    sent = []
    metadata = {canonical(r['provider_body']): r['metadata'] for r in packet['requests']}
    def exchange(self, endpoint, body=None):
        if endpoint.endswith('/endpoints'):
            return {'data': {'id': self.settings.model, 'endpoints': [{'tag': self.settings.endpoint,
                'provider_name': self.settings.provider_name, 'quantization': self.settings.quantization,
                'context_length': 131072, 'max_completion_tokens': 8192,
                'supported_parameters': ['seed', 'temperature', 'max_tokens', 'response_format'],
                'pricing': {'prompt': '.00000008', 'completion': '.00000016'}}]}}
        if endpoint == '/key': return {'data': {'limit_remaining': 1}}
        if endpoint == '/credits': return {'data': {'total_credits': 1, 'total_usage': 0}}
        assert endpoint == '/chat/completions' and 'HIDDEN_CANARY' not in canonical(body)
        assert rows(self.output / 'ledger.jsonl')[-1]['event'] == 'reserve'
        sent.append(body)
        if len(sent) == fail_at:
            raise TimeoutError('mock-key-only')
        meta = metadata[canonical(body)]
        fixed = useful and meta['arm'] == 'both' and meta['task_index'] < 3
        return {'id': f'mock-{len(sent)}', 'model': self.settings.model, 'provider': self.settings.provider_name,
            'usage': {'cost': .00008, 'prompt_tokens': 100, 'completion_tokens': 10},
            'choices': [{'finish_reason': 'stop', 'message': {'content': canonical({'solution.py': FIXED if fixed else BROKEN})}}]}
    monkeypatch.setattr(OpenRouterTransport, '_exchange', exchange)
    return sent


def test_four_conditions_change_only_declared_cues_and_retain_attribution():
    packet = study.construct(records(), Verifier())
    assert len(packet['tasks']) == 12 and len(packet['requests']) == 128
    assert packet['maximum_new_reservations_usd'] == '0.4194304'
    grouped = {}
    for row in packet['requests']:
        meta = row['metadata']; grouped.setdefault((meta['task_index'], meta['draw']), {})[meta['arm']] = row
    positions = Counter()
    for (i, draw), group in grouped.items():
        assert set(group) == set(study.ARMS)
        assert len({r['provider_body']['seed'] for r in group.values()}) == 1
        original = group['original']['request']['messages']
        base = json.loads(original[1]['content'])
        for arm, row in group.items():
            remove, explicit = study.FACTORS[arm]
            messages = row['request']['messages']; content = json.loads(messages[1]['content'])
            assert messages[0]['content'] == original[0]['content'] + (study.PERMISSION if explicit else '')
            assert {k: v for k, v in content.items() if k != 'files'} == {k: v for k, v in base.items() if k != 'files'}
            expected = study.remove_claim(base['files']) if remove else base['files']
            assert content['files'] == expected
            assert ast.dump(ast.parse(content['files']['solution.py'])) == ast.dump(ast.parse(base['files']['solution.py']))
            assert '# License: test-only' in content['files']['solution.py'] and '# Adapted from test/project' in content['files']['solution.py']
        for position, arm in enumerate(group): positions[i, arm, position] += 1
    assert set(positions.values()) == {1}
    changed = records()
    for r in changed:
        r['source_full_pass'] = not r['source_full_pass']
        r['evaluator']['cases'][0]['expected'] = -999
    other = study.construct(changed, Verifier())
    assert [r['provider_body'] for r in packet['requests']] == [r['provider_body'] for r in other['requests']]


def test_comment_removal_does_not_rewrite_strings_or_other_comments():
    code = BROKEN + 'text = "; upstream definitions are unchanged."\n# Other; upstream definitions are unchanged.\n'
    removed = study.remove_claim({'solution.py': code})['solution.py']
    assert removed.count(study.CLAIM) == 2
    assert ast.dump(ast.parse(code)) == ast.dump(ast.parse(removed))
    for code in (BROKEN.replace(study.CLAIM, '.'), BROKEN + HEADER):
        with pytest.raises(ValueError, match='exactly one'): study.remove_claim({'solution.py': code})


@pytest.mark.parametrize('useful', [False, True])
def test_complete_mock_bank_preserves_primary_screen_and_never_trains(tmp_path, monkeypatch, useful):
    packet, config, frozen = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, packet, useful=useful)
    output = tmp_path / 'run'
    cc.collect(frozen, output, claim_root=tmp_path / 'claims')
    report = summarize(output)
    assert len(sent) == 128 and len(report['task_table']) == 12
    assert report['accounting']['cumulative_committed_usd'] == '0.05082467'
    assert report['gate'] == ('candidate_for_independent_interface_calibration' if useful else 'no_repeated_primary_interface_benefit_demonstrated')
    assert report['contrasts']['both_minus_original']['mean_difference'] == (.375 if useful else 0)
    assert not report['fit_selector']
    with pytest.raises(FileExistsError): cc.collect(frozen, tmp_path / 'duplicate', claim_root=tmp_path / 'claims')
    from vao.analysis.contract_diagnostic import summarize as historical
    with pytest.raises(ValueError, match='interface-cue report'): historical(output)


def test_failure_retains_reserve_missingness_and_no_live_treatment_report(tmp_path, monkeypatch):
    packet, config, frozen = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, packet, fail_at=10)
    output = tmp_path / 'run'
    with pytest.raises(ProviderStopped): cc.collect(frozen, output, claim_root=tmp_path / 'claims')
    report = summarize(output)
    assert len(sent) == 10 and sum(a['observed'] for a in report['arm_table']) == 9
    assert sum(a['missing'] for a in report['arm_table']) == 119
    assert len(report['accounting']['pending']) == 1
    assert Decimal(report['accounting']['cumulative_committed_usd']) == study.CARRY + Decimal('.00008') * 9 + Decimal('.0032768')
    assert report['gate'] == 'inconclusive_incomplete_bank'
    assert all(c['mean_difference'] is None and c['descriptive_bug_bootstrap_95'] is None for c in report['contrasts'].values())
    (output / 'interruption.json').unlink()
    with pytest.raises(ValueError, match='active treatment'): summarize(output)


def test_rehashed_packet_drift_and_unfunded_freeze_are_rejected(tmp_path, monkeypatch):
    packet, config, frozen = prepare(tmp_path, monkeypatch)
    for mutate in (lambda p: p['requests'].reverse(), lambda p: p.update(closed_pilot_commitment_usd='0'),
                   lambda p: p['design'].update(draws_per_arm=2),
                   lambda p: p['requests'][0]['provider_body'].update(temperature=1)):
        changed = copy.deepcopy(packet); mutate(changed)
        changed['packet_id'] = identity({k: v for k, v in changed.items() if k != 'packet_id'})
        with pytest.raises(ValueError): study.validate_packet(changed)
    config['live_calls_enabled'] = False
    with pytest.raises(ValueError, match='authorization'): cc.freeze(packet, config, tmp_path / 'disabled.json')


def test_factorial_missing_bounds_keep_signs_and_interaction_range():
    weights = {'both': 1, 'original': 1, 'claim_removed': -1, 'helpers_explicit': -1}
    assert linear_bounds(weights, {arm: [0, 1] for arm in study.ARMS}) == [-2, 2]
    assert linear_bounds({'both': 1, 'original': -1}, {'both': [.25, .5], 'original': [.5, .75]}) == [-.5, 0]


def test_archived_interface_report_dispatch_and_reverification(tmp_path, monkeypatch):
    import hashlib
    import zipfile
    from vao.analysis import contract_verification as cv
    from vao.analysis.repair_interface import render

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
    (delivery / 'evidence-manifest.json').write_text(json.dumps({
        'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'files': {name: hashlib.sha256(content).hexdigest() for name, content in members.items()}}))
    monkeypatch.setattr(cv, 'RepairVerifier', Verifier)
    cv.reproduce(delivery, tmp_path / 'replay.json')
    replay = json.loads((tmp_path / 'replay.json').read_text())
    assert replay['full_analysis_and_markdown_reproduced']
    assert replay['checked_evaluation_records'] == 6 and not replay['discrepancies']
