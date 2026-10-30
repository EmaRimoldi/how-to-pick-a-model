"""Prespecified terminal analysis of the four repair-interface conditions."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import random

from vao.repair.contract_collection import audit, read
from vao.repair.contracts import INTERFACE_STUDY
from vao.repair.interface_study import ARMS, DRAWS
from vao.repair.records import rows, save
from .contract_diagnostic import export_evidence
from .repair_stagnation import classify

CONTRASTS = {
    'both_minus_original': {'both': 1, 'original': -1},
    'claim_removal_main_effect': {'claim_removed': .5, 'both': .5, 'original': -.5, 'helpers_explicit': -.5},
    'explicit_helpers_main_effect': {'helpers_explicit': .5, 'both': .5, 'original': -.5, 'claim_removed': -.5},
    'interaction': {'both': 1, 'original': 1, 'claim_removed': -1, 'helpers_explicit': -1},
}


def linear_bounds(weights, bounds):
    low = high = 0
    for arm, weight in weights.items():
        a, b = bounds[arm]
        low += weight * (a if weight >= 0 else b)
        high += weight * (b if weight >= 0 else a)
    return [low, high]


def interval(values):
    rng = random.Random(43127)
    sampled = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(10000))
    return [sampled[249], sampled[9749]]


def summarize(output):
    if not any((output / name).exists() for name in ('pilot-completion.json', 'interruption.json')):
        raise ValueError('Do not inspect active treatment outcomes')
    checked = audit(output)
    frozen = read(output / 'manifest.json')['freeze']
    packet = frozen['packet']
    if packet['study'] != INTERFACE_STUDY:
        raise ValueError('Expected interface-cue study')
    observed = {r['attempt_id']: r for r in rows(output / 'observations.jsonl')}
    cells = []
    for planned in packet['requests']:
        meta = planned['metadata']; key = meta['attempt_id']; row = observed.get(key)
        source = packet['tasks'][meta['task_index']]
        baseline = source['source_public_result']
        public, fraction, seconds, category = None, None, None, None
        if row:
            seconds, fraction, public, category = 0, 0, False, 'no_artifact'
            for channel in ('public', 'evaluator'):
                if row[channel]:
                    result = read(output / 'cells' / key / 'objects' / (row[channel] + '.json'))['result']
                    seconds += result['verifier_seconds']
                    if channel == 'public':
                        public = result['passed']; fraction = result['passed_cases'] / result['total_cases']
            if row['artifact']:
                artifact = read(output / 'cells' / key / 'objects' / (row['artifact'] + '.json'))['files']
                projection = json.loads(planned['request']['messages'][1]['content'])
                category = classify(projection['files'], artifact, projection['entrypoint'])
        receipt = read(output / 'receipts' / (key + '.json')) if row or key in checked['paid_without_outcome'] else None
        cells.append({**meta, 'observed': row is not None, 'full_pass': row['full_pass'] if row else None,
            'artifact_valid': row['decoded']['artifact_valid'] if row else None, 'edit_category': category,
            'public_pass': public, 'public_fraction': fraction,
            'public_improvement': fraction > baseline['passed_cases'] / baseline['total_cases'] if row else None,
            'public_regression': fraction < baseline['passed_cases'] / baseline['total_cases'] if row else None,
            'public_false_positive': bool(public and not row['full_pass']) if row else None,
            'cost_usd': receipt['cost_usd'] if receipt else None,
            'provider_elapsed_seconds': receipt['elapsed_seconds'] if receipt else None,
            'committed_usd': checked['committed_by_attempt_usd'].get(key, '0'),
            'uncertain': key in checked['pending'], 'paid_without_outcome': key in checked['paid_without_outcome'],
            'counterfactual_prefix_usd': source['source_cost_usd'],
            'source_public_verification_seconds_per_deployment': source['initial_public_result']['verifier_seconds'],
            'response_verification_seconds': seconds})
    table = []
    categories = ('exact_copy', 'format_or_comment_only', 'entrypoint_only_syntax_change',
                  'other_syntax_change', 'unparseable', 'no_artifact')
    for arm in ARMS:
        scoped = [c for c in cells if c['arm'] == arm]
        successes = sum(c['full_pass'] is True for c in scoped)
        missing = sum(not c['observed'] for c in scoped)
        table.append({'arm': arm, 'planned': len(scoped), 'observed': len(scoped) - missing,
            'successes': successes, 'missing': missing,
            'success_bounds': [successes / len(scoped), (successes + missing) / len(scoped)],
            'valid': sum(c['artifact_valid'] is True for c in scoped),
            'public_passes': sum(c['public_pass'] is True for c in scoped),
            'false_positives': sum(c['public_false_positive'] is True for c in scoped),
            'regressions': sum(c['public_regression'] is True for c in scoped),
            'public_improvements': sum(c['public_improvement'] is True for c in scoped),
            'edit_categories': {k: sum(c['edit_category'] == k for c in scoped) for k in categories},
            'known_usd': str(sum((Decimal(c['cost_usd']) for c in scoped if c['cost_usd'] is not None), Decimal(0))),
            'committed_usd': str(sum((Decimal(c['committed_usd']) for c in scoped), Decimal(0))),
            'counterfactual_prefix_usd': str(sum((Decimal(c['counterfactual_prefix_usd']) for c in scoped), Decimal(0))),
            'source_public_verification_seconds_if_deployed': sum(c['source_public_verification_seconds_per_deployment'] for c in scoped),
            'response_verification_seconds': sum(c['response_verification_seconds'] for c in scoped if c['observed']),
            'provider_elapsed_seconds': sum(c['provider_elapsed_seconds'] for c in scoped if c['provider_elapsed_seconds'] is not None)})
    if sum((Decimal(t['committed_usd']) for t in table), Decimal(0)) != Decimal(checked['study_committed_usd']):
        raise ValueError('Arm accounting does not reproduce total commitment')
    complete = checked['sealed'] and not checked['cap_exceeded']
    tasks = [{'task_index': i, 'task': r['public']['task_id'], 'eligible': r['eligible'],
              'reason': r['eligibility_reason'], 'source_full_pass': r['source_full_pass'],
              'cells': [c for c in cells if c['task_index'] == i]} for i, r in enumerate(packet['tasks'])]
    contrasts = {}
    for name, weights in CONTRASTS.items():
        values = []
        if complete:
            for t in tasks:
                if t['eligible']:
                    values.append(sum(weights.get(arm, 0) * sum(c['full_pass'] for c in t['cells'] if c['arm'] == arm) / DRAWS for arm in ARMS))
        contrasts[name] = {'primary': name == 'both_minus_original', 'weights': weights,
            'selected_cell_difference_bounds': linear_bounds(weights, {r['arm']: r['success_bounds'] for r in table}),
            'mean_difference': sum(values) / len(values) if complete else None,
            'descriptive_bug_bootstrap_95': interval(values) if complete else None}
    components, gate = None, 'inconclusive_incomplete_bank'
    if complete:
        repeated = sum(sum(c['full_pass'] for c in t['cells'] if c['arm'] == 'both') >= 2 for t in tasks if t['eligible'])
        halves = [sum(c['full_pass'] for c in cells if c['arm'] == 'both' and c['draw'] in draws)
                  - sum(c['full_pass'] for c in cells if c['arm'] == 'original' and c['draw'] in draws)
                  for draws in ({0, 1}, {2, 3})]
        net = sum(c['full_pass'] for c in cells if c['arm'] == 'both') - sum(c['full_pass'] for c in cells if c['arm'] == 'original')
        components = {'bugs_with_two_both_successes': repeated, 'net_both_successes': net, 'two_draw_half_differences': halves}
        gate = ('candidate_for_independent_interface_calibration' if repeated >= 3 and net >= 4 and all(h > 0 for h in halves)
                else 'no_repeated_primary_interface_benefit_demonstrated')
    return {'study': INTERFACE_STUDY, 'model_results': True,
        'status': 'complete_development_interface_probe' if complete else 'incomplete_development_interface_probe',
        'packet_id': packet['packet_id'], 'freeze_id': frozen['freeze_id'], 'source_commit': frozen['source_commit'],
        'accounting': checked, 'study_limit_usd': frozen['authorized_limit_usd'], 'cumulative_limit_usd': frozen['config']['cumulative_limit_usd'],
        'arm_table': table, 'task_table': tasks, 'contrasts': contrasts, 'gate': gate,
        'gate_components': components, 'fit_selector': False,
        'limitations': ['Eight exposed failure checkpoints with four draws each; twelve source candidates retained. No untouched evaluation.',
            'Primary: both cues minus original. Factorial main effects and interaction are secondary, not substitutes for the primary screen.',
            'Incomplete banks retain finite selected-cell missingness bounds; no complete-bank mean, bootstrap or screen is computed.',
            'Complete-bank paired bug bootstrap intervals are descriptive; eight clusters cannot support broad population inference.',
            'Syntax categories do not establish semantic equivalence or identify psychological anchoring or general model intelligence.',
            'Fewer copies or more changed code is not the objective; full public-plus-evaluator repair is required, with false acceptance and regressions retained.',
            'Equal call caps do not mean equal actual spending or a policy-level budget advantage. Prefix costs are counterfactual, not newly billed.',
            'Local verification and provider latency are separate resources. Operational request pacing is not a policy decision cost.',
            'No trace is acquired in this control and no acquisition policy or repair selector is trained. A passed screen only permits independent calibration.']}


def render(report):
    lines = ['# Repair interface development control', '',
        f"Status: **{report['status']}**. Gate: **{report['gate']}**. No selector trained.", '',
        f"Study commitment: ${report['accounting']['study_committed_usd']} / ${report['study_limit_usd']}; cumulative including prior reserves: ${report['accounting']['cumulative_committed_usd']} / ${report['cumulative_limit_usd']}.", '',
        '| Condition | Observed/planned | Full repairs | Copies | Entrypoint-only edits | Regressions | Missing | Known API USD |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in report['arm_table']:
        lines.append(f"| {r['arm']} | {r['observed']}/{r['planned']} | {r['successes']} | {r['edit_categories']['exact_copy']} | {r['edit_categories']['entrypoint_only_syntax_change']} | {r['regressions']} | {r['missing']} | {r['known_usd']} |")
    lines += ['', 'Primary and secondary contrasts:', '', '```json', json.dumps(report['contrasts'], indent=2), '```', '', '## Limitations', '']
    lines += ['- ' + item for item in report['limitations']]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--export-evidence', action='store_true')
    args = parser.parse_args()
    report = summarize(args.input)
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / 'analysis.json', report)
    (args.output / 'REPORT.md').write_text(render(report))
    if args.export_evidence:
        export_evidence(args.input, args.output, summarize_fn=summarize, report_entrypoint='report_repair_interface_study')
    print(json.dumps({'status': report['status'], 'gate': report['gate'], 'fit_selector': False}))


if __name__ == '__main__':
    main()
