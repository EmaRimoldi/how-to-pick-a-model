import base64
import copy
import json
from pathlib import Path
import sys
from dataclasses import asdict
import itertools

import pytest

from vao.repair import stdin_ablation as ablation
from vao.repair import stdin_collection as study
from vao.repair import stdin_pilot as pilot
from vao.repair import stdin_results as results
from vao.repair.environment import identity
from vao.repair.provider import ProviderStopped
from vao.repair.records import save


class Verifier:
    calls = 0
    fail_on = None

    def preflight(self):
        return {'candidate_executions': 2, 'synthetic': True}

    def invoke(self, source, stdin, *, coverage=False):
        type(self).calls += 1
        if self.calls == self.fail_on:
            raise RuntimeError('synthetic local execution interruption')
        observed = {'status': 'exited', 'returncode': 0,
                    'stdout_b64': base64.b64encode(b'1\n' if source == b'print(1)\n' else b'0\n').decode(),
                    'stderr_b64': ''}
        row = {'observed': observed, 'elapsed_seconds': 0.0, 'candidate_executions': 1, 'python': '3.13.12'}
        if coverage:
            row['coverage'] = {'available': True, 'data': {'version': 'stdin-monitoring-line-coverage-v1',
                'lines': [['main.py', 1]], 'line_events': 1, 'limit_reached': False, 'intact': True,
                'event_limit': 100000, 'line_limit': 4096}}
        return row


@pytest.fixture
def setup(tmp_path, monkeypatch):
    tasks, decisions = [], []
    for i in range(11):
        public = {'schema_version': 3, 'instruction': f'Problem {i}: print one.', 'files': {'main.py': 'print(0)\n'},
                  'comparator': 'ascii_whitespace_tokens',
                  'public_cases': [{'id': 'public_001', 'stdin': '', 'expected_stdout': '1\n'}]}
        tasks.append({'problem_id': f'p{i}', 'pair_index': 0, 'binding': ablation.binding(public), 'public': public,
                      'private_cases': [{'id': 'PRIVATE_CASE', 'input_b64': base64.b64encode(b'PRIVATE_INPUT').decode(),
                                         'expected_b64': base64.b64encode(b'1\n').decode()}]})
        decisions.append({'problem_id': f'p{i}', 'selected_pair_index': 0})
    decisions.append({'problem_id': 'excluded', 'selected_pair_index': None})
    design = pilot.plan(tasks, decisions, 'a'*64)
    inputs = {'design': design, 'tasks': tasks}
    config = {'study': study.STUDY, 'status': 'standing_authorization_suballocation',
              'allocation_usd': '0.32', 'prior_committed_usd': '0.25463059', 'cumulative_cap_usd': '0.60',
              'prior_uncertain_reserves': 14, 'maximum_calls': 110, 'minimum_interval_seconds': 60,
              'max_wire_bytes': 8388608, 'resume_allowed': False, 'retries': 0, 'key_rotation': False,
              'new_explicit_human_numeric_approval': False, 'authorization_reference': 'synthetic test only'}
    frozen = {'study': study.STUDY, 'inputs': inputs, 'config': config, 'runtime': {}, 'source_commit': 'SYNTHETIC_TEST'}
    frozen['freeze_id'] = identity(frozen)
    monkeypatch.setattr(study, 'ROOT', tmp_path)
    monkeypatch.setattr(study, 'load_inputs', lambda: inputs)
    monkeypatch.setattr(study, 'runtime', lambda: {})
    monkeypatch.setattr(study, 'source_commit', lambda: 'SYNTHETIC_TEST')
    (tmp_path / study.CONFIG).parent.mkdir(parents=True)
    save(tmp_path / study.CONFIG, config)
    (tmp_path / 'runs').mkdir()
    save(tmp_path / 'runs/ACTIVE_RESEARCH_STATE.json', {'current_repair_budget': {
        'cumulative_committed_usd': '0.25463059', 'total_unresolved_reservations': 14, 'active_collectors': 0}})
    monkeypatch.setenv('OPENROUTER_API_KEY', 'synthetic-private-test-value')
    Verifier.calls = 0; Verifier.fail_on = None
    monkeypatch.setattr(study, 'MonitoringStdinVerifier', lambda *a: Verifier())
    monkeypatch.setattr(results, 'MonitoringStdinVerifier', lambda *a: Verifier())
    calls = []
    control = {'interrupt_at': None, 'long_initial': False, 'all_initial': None}
    slots = {s['id']: s for s in design['slots']}

    def preflight(transport):
        transport.ready = True
        save(transport.output/'provider-preflight.json', {'settings': asdict(study.SETTINGS),
            'credit_covers_declared_cap': True, 'cap_usd': '0.32', 'minimum_interval_seconds': 60,
            'reservation_usd': str(study.SETTINGS.reserve), 'synthetic': True})

    def exchange(transport, endpoint, body=None):
        assert endpoint == '/chat/completions'
        slot = slots[transport._stream_attempt]
        calls.append(slot)
        text = json.dumps(body)
        assert 'PRIVATE_CASE' not in text and 'PRIVATE_INPUT' not in text
        assert 'private_cases' not in text and 'pair_index' not in text
        assert body['seed'] == slot['seed']
        if len(calls) == control['interrupt_at']:
            save(transport.output / 'stream-metrics' / (slot['id']+'.json'),
                 {'stream_complete': False, 'done_received': False, 'usage_received': False, 'reported_cost_usd': '0'})
            raise ProviderStopped('synthetic transport failure')
        if slot['phase'] == 'initial':
            content = 'invalid JSON' if slot['problem_id'] == 'p1' else json.dumps({'main.py': 'print(1)\n' if slot['problem_id'] == 'p0' else 'print(0)\n'})
            if control['long_initial'] and slot['problem_id'] == 'p2':
                content = json.dumps({'main.py': '#'+('x'*59000)+'\nprint(0)\n'})
            if control['all_initial'] is not None:
                content = 'invalid JSON' if control['all_initial'] == 'invalid' else json.dumps({'main.py': 'print(1)\n'})
        else:
            content = json.dumps({'main.py': 'print(1)\n' if slot['arm'] == 'scored' else 'print(0)\n'})
        save(transport.output / 'stream-metrics' / (slot['id']+'.json'),
             {'stream_complete': True, 'done_received': True, 'usage_received': True, 'reported_cost_usd': '0.00001'})
        return {'id': 'synthetic-'+slot['id'], 'model': study.SETTINGS.model, 'provider': study.SETTINGS.provider_name,
                'reconstructed_from_sse': True, 'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': content}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30, 'cost': 0.00001}}

    monkeypatch.setattr(study.StreamingOpenRouterTransport, 'preflight', preflight)
    monkeypatch.setattr(study.StreamingOpenRouterTransport, '_exchange', exchange)
    clock = itertools.count()
    monkeypatch.setattr(study, 'dispatch_timestamp', lambda _: next(clock)*60)
    # Keep the actual reservation/settlement and streaming adapter paths, without
    # sleeping or contacting a service. The constructor's 60s argument is checked.
    constructor = study.StreamingOpenRouterTransport.__init__
    def init(transport, *args, **kwargs):
        assert kwargs['minimum_interval_seconds'] == 60 and kwargs['max_wire_bytes'] == 8388608
        constructor(transport, *args, **kwargs)
        transport.minimum_interval_seconds = 0
    monkeypatch.setattr(study.StreamingOpenRouterTransport, '__init__', init)
    return tmp_path, frozen, calls, control


def run(setup):
    root, frozen, calls, control = setup
    model, verification = root/'model', root/'verification'
    terminal = study.collect(frozen, model)
    results.verify(model, verification)
    report = results.analyze(model, verification)
    return model, verification, terminal, report


def test_complete_generated_checkpoint_collection_and_independent_analysis(setup):
    model, verification, terminal, report = run(setup)
    root, frozen, calls, _ = setup
    assert terminal['status'] == 'completed'
    assert len(calls) == 92 and all(s['phase'] == 'initial' for s in calls[:11])
    assert all(s['problem_id'] not in {'p0', 'p1'} for s in calls[11:])
    assert len(list((model/'dispositions').iterdir())) == 110
    assert len(list((model/'acquisitions').iterdir())) == 9
    assert report['accounting']['known_usd'] == '0.00092'
    assert report['accounting']['pending'] == {}
    assert report['analysis']['initial_flow'] == {'missing': 0, 'invalid': 1, 'public_pass': 1, 'public_fail': 9}
    assert report['analysis']['gate'] == 'advance_to_replication_planning'
    assert report['selector_training_allowed'] is False
    assert report['collection_execution_journal']['completed_candidate_executions'] == 120
    assert report['verification_execution_journal']['completed_candidate_executions'] == 182
    assert not report['public_replay_mismatches']
    paths = report['policy_resource_paths']
    assert all(p['known_api_usd'] == '0.00020' for p in paths)
    assert all(p['recorded_acquisition_executions'] == (0 if p['arm']=='feedback' else 18) for p in paths)
    assert all(p['acquisition_divided_by_draws'] is False for p in paths)
    with pytest.raises(ValueError, match='resume'):
        study.collect(frozen, model)
    with pytest.raises((ValueError, FileExistsError)):
        study.collect(frozen, root/'duplicate')


@pytest.mark.parametrize('interruption', [1, 3, 12, 20])
def test_transport_interruption_retains_reserve_and_never_retries(setup, interruption):
    setup[3]['interrupt_at'] = interruption
    model, verification, terminal, report = run(setup)
    assert terminal['status'] == 'interrupted'
    assert len(setup[2]) == interruption
    assert len(report['accounting']['pending']) == 1
    assert next(iter(report['accounting']['pending'].values())) == str(study.SETTINGS.reserve)
    assert report['analysis']['gate'] == 'inconclusive'
    assert report['analysis']['conditional_means'] is None
    assert report['analysis']['conditional_contrasts'] is None
    assert report['accounting']['settled'] == interruption-1
    state = study.read(setup[0]/'runs/ACTIVE_RESEARCH_STATE.json')['current_repair_budget']
    assert state['active_collectors'] == 0 and state['total_unresolved_reservations'] == 15
    assert state['cumulative_committed_usd'] == report['accounting']['cumulative_committed_usd']


def test_partial_local_phase_keeps_paid_reply_and_every_completed_execution(setup):
    Verifier.fail_on = 5
    root, frozen, calls, _ = setup
    model, verification = root/'model', root/'verification'
    terminal = study.collect(frozen, model)
    assert terminal['status'] == 'interrupted'
    Verifier.fail_on = None
    results.verify(model, verification)
    report = results.analyze(model, verification)
    assert report['accounting']['settled'] == 3
    assert report['accounting']['pending'] == {}
    assert report['collection_execution_journal']['unknown_execution_counts'] == 1
    assert report['analysis']['gate'] == 'inconclusive'
    assert len(report['panel']) == 11


@pytest.mark.parametrize('tamper', ['prompt', 'private_score', 'receipt', 'journal', 'branch_without_failure'])
def test_terminal_audit_rejects_forged_source_scores_money_and_work(setup, tamper):
    model, verification, terminal, report = run(setup)
    slots = setup[1]['inputs']['design']['slots']
    k = slots[0]['id']
    if tamper == 'prompt':
        p = model/'requests'/(k+'.provider.json'); data = study.read(p)
        data['messages'][1]['content'] = 'PRIVATE_ORACLE'; p.write_text(json.dumps(data))
    elif tamper == 'private_score':
        p = verification/'cells'/(k+'.json'); data = study.read(p)
        data['private'][0]['passed'] = False; p.write_text(json.dumps(data))
    elif tamper == 'receipt':
        p = model/'receipts'/(k+'.json'); data = study.read(p)
        data['cost_usd'] = '0'; p.write_text(json.dumps(data))
    elif tamper == 'journal':
        p = model/'execution-journal.jsonl'; data = p.read_text().splitlines()
        row = json.loads(data[2]); row['source_sha256'] = 'wrong'; data[2] = json.dumps(row)
        p.write_text('\n'.join(data)+'\n')
        # Force the secondary inventory to acknowledge the file mutation, so the
        # actual source-to-execution binding check, not just its hash, must fail.
        p = verification/'manifest.json'; m = study.read(p); m['model_inventory'] = results.inventory(model); p.write_text(json.dumps(m))
    else:
        skipped = next(s for s in slots if s['phase']=='recovery' and s['problem_id']=='p0')
        (model/'requests'/(skipped['id']+'.json')).write_text('{}')
    with pytest.raises(ValueError):
        results.analyze(model, verification)


def test_real_cohort_is_bound_without_private_prompt_projection():
    inputs = study.load_inputs()
    assert len(inputs['tasks']) == 11 and len(inputs['design']['slots']) == 110
    assert sum(t['private_cases'] != [] for t in inputs['tasks']) == 11
    assert len({s['id'] for s in inputs['design']['slots']}) == 110


def test_over_limit_generated_prompts_remain_missing_without_truncation_or_replacement(setup):
    setup[3]['long_initial'] = True
    model, verification, terminal, report = run(setup)
    assert terminal['status'] == 'completed'
    assert len(setup[2]) == 86
    assert report['accounting']['pending'] == {}
    assert report['analysis']['gate'] == 'inconclusive'
    assert report['analysis']['conditional_means'] is None
    rejected = [study.read(p) for p in (model/'dispositions').iterdir() if study.read(p)['status']=='missing_not_sent']
    assert len(rejected) == 6 and all(d['reason']=='input_admission_bound' for d in rejected)


def test_budget_lock_prevents_parallel_collection_before_any_admission(setup):
    import fcntl
    root, frozen, calls, _ = setup
    with (root/'runs/.stdin-pilot-budget.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='budget lock'):
            study.collect(frozen, root/'duplicate')
    assert calls == [] and not (root/'duplicate').exists()


@pytest.mark.parametrize('kind', ['public_pass', 'invalid'])
def test_zero_generated_failures_preserves_complete_initial_flow_without_recovery(setup, kind):
    setup[3]['all_initial'] = kind
    model, verification, terminal, report = run(setup)
    assert len(setup[2]) == 11 and report['accounting']['pending'] == {}
    assert len(list((model/'dispositions').iterdir())) == 110
    assert report['analysis']['initial_flow'][kind] == 11
    assert report['analysis']['known_outcomes_complete'] is True
    assert report['analysis']['gate'] == 'insufficient_generated_failures'
    assert report['analysis']['conditional_means'] is None
    assert 'no materializable generated failures' in results.render(report)


def test_publish_and_reproduce_inert_complete_evidence(setup, monkeypatch):
    root, frozen, calls, _ = setup
    code = root/'example.py'; code.write_text('pass\n')
    runtime = {'files': {'example.py': study.digest(code)}}
    frozen['runtime'] = runtime
    frozen['freeze_id'] = identity({k:v for k,v in frozen.items() if k!='freeze_id'})
    monkeypatch.setattr(study, 'runtime', lambda: runtime)
    for name in [study.BANK/'evidence.zip', study.BANK/'manifest.json', study.BANK/'pilot-design.json',
                 study.BASE/'results/fixeval-source-qualification-20261030/evidence.zip']:
        p = root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'synthetic dependency record')
    model, verification, terminal, report = run(setup)
    output = root/'published'
    results.publish(model, verification, output)
    before = len(calls)
    assert results.reproduce(output) == {'gate': 'advance_to_replication_planning', 'admitted': 92,
                                         'settled': 92, 'new_model_calls': 0, 'candidate_executions': 0}
    assert len(calls) == before
    assert (output/'results.png').stat().st_size > 1000
    with pytest.raises(ValueError, match='overwrite'):
        results.publish(model, verification, output)
    p = output/'analysis.json'; data = study.read(p); data['analysis']['gate']='FORGED'; p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Published analysis'):
        results.reproduce(output)


@pytest.mark.skipif(sys.platform != 'darwin' or not hasattr(sys, 'monitoring'), reason='native macOS monitoring backend')
def test_native_sandbox_end_to_end_without_provider_calls(setup, monkeypatch):
    from vao.repair.stdin_monitoring import MonitoringStdinVerifier
    monkeypatch.setattr(study, 'MonitoringStdinVerifier', MonitoringStdinVerifier)
    monkeypatch.setattr(results, 'MonitoringStdinVerifier', MonitoringStdinVerifier)
    model, verification, terminal, report = run(setup)
    assert terminal['status'] == 'completed'
    assert report['accounting']['admitted'] == 92
    assert report['verification_execution_journal']['completed_candidate_executions'] == 182
    assert not report['public_replay_mismatches']
