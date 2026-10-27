"""Prospective controls, finite missingness, cost conservation and inert replay."""
import copy
from collections import Counter
from decimal import Decimal
import hashlib
import itertools
import json
import zipfile

import pytest

from test_repair_independent_information import network
from test_repair_qwen_information_study import Verifier as BaseVerifier, records as base_records, FIXED, BROKEN
from vao.analysis.repair_contrastive import summarize, render, screen
from vao.repair import contract_collection as cc, contrastive_study as ds
from vao.repair.contracts import CONTRASTIVE_TRACE_STUDY, INDEPENDENT_TRACE_STUDY
from vao.repair.environment import canonical, identity
from vao.repair.provider import ProviderStopped
from vao.repair.records import rows


class Verifier(BaseVerifier):
    def check(self, files, entry, cases):
        results = [{'id': c['id'], 'passed': self.invoke(files, entry, c)['value'] == c['expected'],
                    'observed': self.invoke(files, entry, c)} for c in cases]
        return {'passed': all(r['passed'] for r in results), 'passed_cases': sum(r['passed'] for r in results),
                'total_cases': len(results), 'cases': results, 'verifier_seconds': .01}


def records():
    result = base_records()
    for r in result:
        p = r['public']
        p['public_cases'].append({'id': 'already-passing', 'args': [0], 'expected': 0})
        observed = Verifier().check(p['files'], p['entrypoint'], p['public_cases'])
        observed.pop('verifier_seconds')
        r['source_public_result'] = observed
    return result


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, 'source_commit', lambda: 'a' * 40)
    monkeypatch.setattr(cc, 'RepairVerifier', Verifier)
    monkeypatch.setattr(ds, 'validate_origin', lambda p: None)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'mock-key-only')
    now = [1000.0]
    def sleep(seconds): now[0] += seconds
    monkeypatch.setattr('vao.repair.provider.time.sleep', sleep)
    monkeypatch.setattr('vao.repair.provider.time.monotonic', lambda: now[0])
    prior = tmp_path / 'prior.json'
    prior.write_text(json.dumps({'study': INDEPENDENT_TRACE_STUDY, 'model_results': True,
        'status': 'complete_development_information_probe', 'gate': 'no_completion_meets_development_screen',
        'fit_selector': False, 'accounting': {'sealed': True, 'cumulative_committed_usd': str(ds.CARRY)}}))
    config = {'status': 'authorized_contract_diagnostic', 'study': CONTRASTIVE_TRACE_STUDY,
        'live_calls_enabled': True, 'authorization_reference': 'MOCK TRANSPORT ONLY',
        'monetary_authorization_usd': '.40', 'cumulative_limit_usd': '.60',
        'minimum_request_interval_seconds': 60, 'closed_pilot_report': str(prior)}
    packet = ds.construct(records(), Verifier())
    return packet, cc.freeze(packet, config, tmp_path / 'freeze.json')


def run(tmp_path, monkeypatch, *, failures=None, benefit=None, stops=False):
    packet, frozen = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, packet, failures=failures,
        content_for=lambda m: FIXED if m['arm'] == benefit and m['task_index'] < 3 else BROKEN)
    out = tmp_path / 'run'
    if stops:
        with pytest.raises(ProviderStopped): cc.collect(frozen, out, claim_root=tmp_path / 'claims')
    else:
        cc.collect(frozen, out, claim_root=tmp_path / 'claims')
    return packet, frozen, sent, out, summarize(out)


def test_only_runtime_information_differs_and_all_orders_balance():
    p = ds.construct(records(), Verifier())
    orders, seeds = Counter(), set()
    for start in range(0, 72, 3):
        triplet = p['requests'][start:start + 3]
        orders[tuple(r['metadata']['arm'] for r in triplet)] += 1
        assert len({r['metadata']['trajectory'] for r in triplet}) == 1
        assert len({r['provider_body']['seed'] for r in triplet}) == 1
        seeds.add(triplet[0]['provider_body']['seed'])
        bodies = {r['metadata']['arm']: copy.deepcopy(r['provider_body']) for r in triplet}
        messages = {a: json.loads(b['messages'][1]['content']) for a, b in bodies.items()}
        single = messages['single_trace'].pop('runtime_diagnostic')
        paired = messages['paired_trace'].pop('runtime_diagnostic')
        assert all(v == messages['focused'] for v in messages.values())
        assert single['records'] == paired['records'][:1]
        assert [r['role'] for r in paired['records']] == ['failure', 'passing']
        for arm in ('single_trace', 'paired_trace'):
            bodies[arm]['messages'] = bodies['focused']['messages']
            assert bodies[arm] == bodies['focused']
    assert orders == {order: 4 for order in itertools.permutations(ds.ARMS)} and len(seeds) == 24
    assert p['maximum_new_reservations_usd'] == '0.39518208'
    assert p['maximum_cumulative_commitment_usd'] == '0.56013863'
    changed = records()
    for r in changed:
        r['evaluator']['cases'][0]['expected'] = -55
        r['source_full_pass'] = not r['source_full_pass']
    q = ds.construct(changed, Verifier())
    assert [r['provider_body'] for r in p['requests']] == [r['provider_body'] for r in q['requests']]
    assert 'HIDDEN_CANARY' not in canonical([r['provider_body'] for r in p['requests']])
    checked = ds.validate_origin({'tasks': ds.source_records(), 'requests': p['requests']})
    assert checked['historical_archives'] == 15 and checked['historical_unique_bodies'] == 620


@pytest.mark.parametrize('change', ['order', 'settings', 'design', 'carry', 'binding'])
def test_rehashing_cannot_hide_protocol_or_accounting_drift(change):
    p = ds.construct(records(), Verifier())
    if change == 'order': p['requests'].reverse()
    if change == 'settings': p['provider_settings']['max_tokens'] = 2048
    if change == 'design': p['design']['draws_per_arm'] = 4
    if change == 'carry': p['closed_pilot_commitment_usd'] = '0'
    if change == 'binding': p['tasks'][0]['diagnostics']['paired_trace']['binding'] = 'changed'
    p['packet_id'] = identity({k: v for k, v in p.items() if k != 'packet_id'})
    with pytest.raises(ValueError): ds.validate_packet(p)


def test_allocation_preserves_closed_bank_reserves_and_both_caps(tmp_path, monkeypatch):
    p, frozen = prepare(tmp_path, monkeypatch)
    config, prior = frozen['config'], frozen['prior_report']
    for changes in ({'monetary_authorization_usd': '.39'}, {'monetary_authorization_usd': '.44'},
                    {'cumulative_limit_usd': '.55'}, {'live_calls_enabled': False}):
        with pytest.raises(ValueError): cc.authorization({**config, **changes}, p, prior)
    for changes in ({'accounting': {'sealed': True, 'cumulative_committed_usd': '0'}},
                    {'accounting': {'sealed': False, 'cumulative_committed_usd': str(ds.CARRY)}},
                    {'gate': 'candidate_for_independent_acquisition_calibration'}):
        with pytest.raises(ValueError): cc.authorization(config, p, {**prior, **changes})


@pytest.mark.parametrize('benefit', [None, 'paired_trace', 'single_trace'])
def test_complete_collection_costs_primary_and_secondary_cannot_swap(tmp_path, monkeypatch, benefit):
    p, f, sent, out, report = run(tmp_path, monkeypatch, benefit=benefit)
    assert len(sent) == len({canonical(b) for b in sent}) == 72
    assert report['accounting']['sealed'] and len(report['task_table']) == 12
    assert report['screen']['all_completions_pass'] == (benefit == 'paired_trace')
    assert not report['fit_selector']
    expected = 'candidate_for_independent_acquisition_calibration' if benefit == 'paired_trace' else 'no_completion_meets_development_screen'
    assert report['gate'] == expected
    assert report['accounting']['cumulative_committed_usd'] == str(ds.CARRY + 72 * Decimal('.00008'))
    arms = {a['arm']: a for a in report['arm_table']}
    assert [arms[a]['diagnostic_executions_per_deployment_sum'] for a in ds.ARMS] == [0, 48, 96]
    assert all(Decimal(a['counterfactual_prefix_usd']) == Decimal('.0024') for a in arms.values())
    assert sum(Decimal(a['known_usd']) for a in arms.values()) == Decimal('.00576')
    if benefit == 'single_trace':
        assert report['contrasts']['single_trace_minus_focused']['mean_difference'] == .375
        assert report['contrasts']['paired_trace_minus_focused']['mean_difference'] == 0
    from vao.analysis.contract_diagnostic import summarize as routed
    with pytest.raises(ValueError, match='contrastive-trace report'): routed(out)
    with pytest.raises(FileExistsError): cc.collect(f, tmp_path / 'duplicate', claim_root=tmp_path / 'claims')
    assert len(sent) == 72


def test_missing_response_retains_reserve_and_nulls_all_means(tmp_path, monkeypatch):
    p, f, sent, out, report = run(tmp_path, monkeypatch, benefit='paired_trace', failures={2: 'timeout'})
    assert len(sent) == 72 and sum(a['missing'] for a in report['arm_table']) == 1
    assert not report['accounting']['sealed'] and (out / 'interruption.json').exists()
    assert report['accounting']['cumulative_committed_usd'] == str(ds.CARRY + 71 * Decimal('.00008') + Decimal('.00548864'))
    for contrast in report['contrasts'].values():
        assert contrast['mean_difference'] is None and contrast['descriptive_bug_bootstrap_95'] is None
    from vao.repair.contract_progress import progress
    operational = progress(out)
    assert operational['admissions'] == 72 and operational['observations'] == 71
    assert operational['cumulative_commitment_usd'] == report['accounting']['cumulative_committed_usd']
    assert not any(k in operational for k in ('gate', 'screen', 'successes', 'arm_table', 'contrasts'))
    events = [e for e in rows(out / 'ledger.jsonl') if e['event'] == 'retain_unknown']
    assert len(events) == 1 and events[0]['cooldown_elapsed_seconds'] == 120


@pytest.mark.parametrize('failures,count', [({1: 'http'}, 1), ({1: 'timeout', 2: 'headers', 3: 'reset'}, 3)])
def test_terminal_failure_keeps_all_selected_cells(tmp_path, monkeypatch, failures, count):
    p, f, sent, out, report = run(tmp_path, monkeypatch, failures=failures, stops=True)
    assert len(sent) == count and sum(a['missing'] for a in report['arm_table']) == 72
    assert len(report['accounting']['pending']) == count and report['gate'] == 'inconclusive_selected_cell_bounds'
    assert Decimal(report['accounting']['study_committed_usd']) == count * Decimal('.00548864')
    (out / 'interruption.json').unlink()
    with pytest.raises(ValueError, match='before terminal'): summarize(out)


def test_finite_screen_matches_enumerated_completions_and_never_mutates_unknowns():
    bugs = list(range(4))
    cells = {(b, d, arm): arm == 'paired_trace' for b in bugs for d in range(3) for arm in ('focused', 'paired_trace')}
    missing = [(0, 0, 'focused'), (1, 2, 'paired_trace'), (2, 1, 'paired_trace')]
    for k in missing: cells[k] = None
    frozen = copy.deepcopy(cells)
    decisions = []
    for values in itertools.product((False, True), repeat=len(missing)):
        complete = {**cells, **dict(zip(missing, values))}
        successes = sum(sum(complete[b, d, 'paired_trace'] for d in range(3)) >= 2 for b in bugs)
        differences = [sum(int(complete[b, d, 'paired_trace']) - int(complete[b, d, 'focused']) for b in bugs) for d in range(3)]
        decisions.append(successes >= 3 and sum(differences) >= 4 and all(v > 0 for v in differences))
    result = screen(cells, bugs)
    assert result['all_completions_pass'] == all(decisions)
    assert result['no_completion_passes'] == (not any(decisions)) and cells == frozen
    for bad in ({**cells, missing[0]: 1}, {k: v for k, v in cells.items() if k != missing[0]}):
        with pytest.raises(ValueError): screen(bad, bugs)


def test_changed_trace_is_rejected_before_dispatch_or_claim(tmp_path, monkeypatch):
    p, f = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch, p)
    class Changed(Verifier):
        def trace(self, *args):
            result = super().trace(*args)
            result['trace']['events'][0]['locals']['x'] = 100
            return result
    monkeypatch.setattr(cc, 'RepairVerifier', Changed)
    with pytest.raises(ValueError, match='does not reproduce'):
        cc.collect(f, tmp_path / 'run', claim_root=tmp_path / 'claims')
    assert not sent and not (tmp_path / 'run').exists() and not (tmp_path / 'claims').exists()


def test_archive_replays_three_arm_analysis_and_all_saved_evaluations(tmp_path, monkeypatch):
    from vao.analysis import contract_verification as cv
    p, f, sent, out, report = run(tmp_path, monkeypatch, benefit='paired_trace', failures={2: 'timeout'})
    source = tmp_path / 'export'; source.mkdir()
    (source / 'analysis.json').write_text(json.dumps(report))
    (source / 'REPORT.md').write_text(render(report))
    members = {}
    with zipfile.ZipFile(source / 'evidence.zip', 'w') as z:
        for path in out.rglob('*'):
            if path.is_file():
                name = 'collection/' + path.relative_to(out).as_posix(); data = path.read_bytes()
                z.writestr(name, data); members[name] = hashlib.sha256(data).hexdigest()
    (source / 'evidence-manifest.json').write_text(json.dumps({'files': members,
        'archive_sha256': hashlib.sha256((source / 'evidence.zip').read_bytes()).hexdigest()}))
    monkeypatch.setattr(cv, 'RepairVerifier', Verifier)
    result = tmp_path / 'reverified.json'; cv.reproduce(source, result)
    checked = json.loads(result.read_text())
    assert checked['full_analysis_and_markdown_reproduced'] and checked['public_diagnostic_projections_reexecuted']
    assert checked['checked_evaluation_records'] == 142 and checked['discrepancies'] == []


def test_full_success_rejects_public_false_acceptance_and_preservation_regression(tmp_path, monkeypatch):
    p, f = prepare(tmp_path, monkeypatch)
    false_acceptance = "def solve(x):\n    return x if x != 99 else 0\n"
    regression = "def solve(x):\n    return -1\n"
    class Alternatives(Verifier):
        def invoke(self, files, entry, case):
            code, x = files['solution.py'], case['args'][0]
            if code == false_acceptance: return {'status': 'returned', 'value': x if x != 99 else 0}
            if code == regression: return {'status': 'returned', 'value': -1}
            return super().invoke(files, entry, case)
    monkeypatch.setattr(cc, 'RepairVerifier', Alternatives)
    network(monkeypatch, p, content_for=lambda m: {'focused': false_acceptance, 'single_trace': FIXED, 'paired_trace': regression}[m['arm']])
    out = tmp_path / 'run'
    cc.collect(f, out, claim_root=tmp_path / 'claims')
    report = summarize(out); arms = {r['arm']: r for r in report['arm_table']}
    assert arms['focused']['public_passes'] == arms['focused']['false_positives'] == 24
    assert arms['focused']['successes'] == arms['paired_trace']['successes'] == 0
    assert arms['paired_trace']['regressions'] == 24 and arms['single_trace']['successes'] == 24
    assert report['gate'] == 'no_completion_meets_development_screen'
