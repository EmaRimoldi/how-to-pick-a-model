"""Prespecified complete-task comparisons for the three-arm public-contrast study."""
import argparse
from decimal import Decimal
from pathlib import Path
import json
import random

from vao.repair.contract_collection import audit, read
from vao.repair.contracts import CONTRASTIVE_TRACE_STUDY
from vao.repair.contrastive_study import ARMS, DRAWS
from vao.repair.records import rows, save
from .contract_diagnostic import export_evidence


def screen(cells, bugs):
    """Monotone primary screen at both binary completion extremes, no imputation."""
    expected = {(bug, draw, arm) for bug in bugs for draw in range(DRAWS) for arm in ('focused', 'paired_trace')}
    if len(bugs) != len(set(bugs)) or not bugs or set(cells) != expected or any(v is not None and type(v) is not bool for v in cells.values()):
        raise ValueError('Every selected primary cell must be present, boolean or unknown')
    def extreme(favorable):
        completed = {k: v if v is not None else ((k[2] == 'paired_trace') == favorable) for k, v in cells.items()}
        repeated = sum(sum(completed[(b, d, 'paired_trace')] for d in range(DRAWS)) >= 2 for b in bugs)
        by_draw = [sum(int(completed[(b, d, 'paired_trace')]) - int(completed[(b, d, 'focused')]) for b in bugs) for d in range(DRAWS)]
        return {'bugs_with_two_paired_successes': repeated, 'net_paired_successes': sum(by_draw),
            'draw_differences': by_draw,
            'screen_passed': repeated >= 3 and sum(by_draw) >= 4 and all(v > 0 for v in by_draw)}
    lower, upper = extreme(False), extreme(True)
    return {'least_favorable': lower, 'most_favorable': upper,
        'all_completions_pass': lower['screen_passed'], 'no_completion_passes': not upper['screen_passed'],
        'missing_primary_cells': sum(v is None for v in cells.values()), 'fit_selector': False}


def interval(values):
    rng = random.Random(43138)
    draws = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(10000))
    return [draws[249], draws[9749]]


def summarize(output):
    if not ((output / 'pilot-completion.json').exists() or (output / 'interruption.json').exists()):
        raise ValueError('Do not inspect treatments before terminal state')
    checked = audit(output)
    frozen = read(output / 'manifest.json')['freeze']
    packet = frozen['packet']
    if packet['study'] != CONTRASTIVE_TRACE_STUDY:
        raise ValueError('Expected the separately frozen contrastive study')
    observed = {r['attempt_id']: r for r in rows(output / 'observations.jsonl')}
    cells = []
    for planned in packet['requests']:
        meta = planned['metadata']; key = meta['attempt_id']; row = observed.get(key)
        source = packet['tasks'][meta['task_index']]
        public = evaluator = None
        if row:
            def result(channel):
                return read(output / 'cells' / key / 'objects' / (row[channel] + '.json'))['result'] if row[channel] else None
            public, evaluator = result('public'), result('evaluator')
        diagnostic = source['diagnostics'].get(meta['arm'])
        public_fraction = (public['passed_cases'] / public['total_cases'] if public else 0) if row else None
        cells.append({**meta, 'observed': row is not None, 'full_pass': row['full_pass'] if row else None,
            'artifact_valid': row['decoded']['artifact_valid'] if row else None,
            'public_pass': bool(public and public['passed']) if row else None,
            'false_public_acceptance': bool(public and public['passed'] and not row['full_pass']) if row else None,
            'net_public_regression': public_fraction < source['source_public_result']['passed_cases'] / source['source_public_result']['total_cases'] if row else None,
            'cost_usd': read(output / 'receipts' / (key + '.json'))['cost_usd'] if row or key in checked['paid_without_outcome'] else None,
            'committed_usd': checked['committed_by_attempt_usd'].get(key, '0'),
            'uncertain': key in checked['pending'], 'paid_without_outcome': key in checked['paid_without_outcome'],
            'source_prefix_usd': source['source_cost_usd'],
            'source_public_verification_seconds_per_deployment': source['observation']['verifier_seconds'],
            'diagnostic_available': diagnostic['available'] if diagnostic else None,
            'diagnostic_executions_per_deployment': diagnostic['additional_executions'] if diagnostic else 0,
            'diagnostic_seconds_per_deployment': diagnostic['diagnostic_seconds'] if diagnostic else 0,
            'response_public_verification_seconds': public['verifier_seconds'] if public else (0 if row else None),
            'response_evaluator_verification_seconds': evaluator['verifier_seconds'] if evaluator else (0 if row else None)})
    complete = checked['sealed'] and not checked['cap_exceeded']
    table = []
    for arm in ARMS:
        group = [c for c in cells if c['arm'] == arm]
        successes = sum(c['full_pass'] is True for c in group)
        missing = sum(not c['observed'] for c in group)
        item = {'arm': arm, 'planned': len(group), 'observed': len(group) - missing,
            'successes': successes, 'missing': missing,
            'success_bounds': [successes / len(group), (successes + missing) / len(group)],
            'public_passes': sum(c['public_pass'] is True for c in group),
            'false_positives': sum(c['false_public_acceptance'] is True for c in group),
            'regressions': sum(c['net_public_regression'] is True for c in group),
            'unusable_responses': sum(c['observed'] and not c['artifact_valid'] for c in group)}
        for out, field in [('known_usd', 'cost_usd'), ('committed_usd', 'committed_usd'), ('counterfactual_prefix_usd', 'source_prefix_usd')]:
            item[out] = str(sum((Decimal(c[field]) for c in group if c[field] is not None), Decimal(0)))
        for field in ('diagnostic_executions_per_deployment', 'diagnostic_seconds_per_deployment',
            'source_public_verification_seconds_per_deployment', 'response_public_verification_seconds', 'response_evaluator_verification_seconds'):
            item[field + '_sum'] = sum(c[field] for c in group if c[field] is not None)
        table.append(item)
    if sum((Decimal(r['committed_usd']) for r in table), Decimal(0)) != Decimal(checked['study_committed_usd']):
        raise ValueError('Arm costs do not reproduce full accounting')
    tasks = [{'task_index': i, 'task': r['public']['task_id'], 'eligible': r['eligible'],
        'reason': r['eligibility_reason'], 'source_full_pass': r['source_full_pass'],
        'diagnostics_available': {a: d['available'] for a, d in r['diagnostics'].items()},
        'cells': [c for c in cells if c['task_index'] == i]} for i, r in enumerate(packet['tasks'])]
    contrasts, by_arm = {}, {r['arm']: r for r in table}
    for treatment, control in [('paired_trace', 'focused'), ('paired_trace', 'single_trace'), ('single_trace', 'focused')]:
        a, b = by_arm[treatment], by_arm[control]
        values = [(sum(c['full_pass'] for c in t['cells'] if c['arm'] == treatment)
            - sum(c['full_pass'] for c in t['cells'] if c['arm'] == control)) / DRAWS for t in tasks if t['eligible']] if complete else []
        contrasts[treatment + '_minus_' + control] = {'primary': control == 'focused' and treatment == 'paired_trace',
            'selected_cell_difference_bounds': [a['success_bounds'][0] - b['success_bounds'][1], a['success_bounds'][1] - b['success_bounds'][0]],
            'mean_difference': sum(values) / len(values) if complete else None,
            'descriptive_bug_bootstrap_95': interval(values) if complete else None}
    robust = screen({(c['task_index'], c['draw'], c['arm']): c['full_pass'] for c in cells if c['arm'] != 'single_trace'}, [t['task_index'] for t in tasks if t['eligible']])
    gate = ('inconclusive_accounting_cap_exceeded' if checked['cap_exceeded'] else
        'candidate_for_independent_acquisition_calibration' if robust['all_completions_pass'] else
        'no_completion_meets_development_screen' if robust['no_completion_passes'] else 'inconclusive_selected_cell_bounds')
    return {'study': packet['study'], 'model_results': True,
        'status': 'complete_contrastive_development_probe' if complete else 'incomplete_contrastive_development_probe',
        'packet_id': packet['packet_id'], 'freeze_id': frozen['freeze_id'], 'source_commit': frozen['source_commit'],
        'accounting': checked, 'study_limit_usd': frozen['authorized_limit_usd'], 'cumulative_limit_usd': frozen['config']['cumulative_limit_usd'],
        'arm_table': table, 'task_table': tasks, 'contrasts': contrasts, 'screen': robust, 'gate': gate, 'fit_selector': False,
        'limitations': [
            'Eight exposed checkpoints, seven youtube-dl and one httpie, three draws per arm; development only.',
            'All twelve original sources retained; four public passes do not trigger acquisition, including evaluator failures.',
            'Primary paired_trace minus focused; favorable single-trace contrasts cannot replace it.',
            'New concurrent requests only; no pooling, reused historical controls or filled missing requests.',
            'Three-draw finite screen is newly prospective; no historical four-draw gate is changed.',
            'Equal per-call limits are not equal realized spending or an equal-total-budget policy test.',
            'Counterfactual prefix and diagnostic resources are charged for every planned deployment, not rebilled research API charges.',
            'Selection/preparation time is included in diagnostic_seconds; prompt projection and full deployment overhead still need policy accounting.',
            'Public response verification and private evaluator research time are separate; local time is not converted to dollars.',
            'Incomplete banks retain null mean/bootstrap and finite selected-cell bounds; no random-missingness assumption.',
            'A screen pass permits only a separately reviewed independent calibration, never selector training.',
            'The network-error rule permits only never-admitted scheduled cells after bounded cooldown; no retry/resumption or key rotation.',
            'Raw SSE bytes are not archived; saved metrics are not byte-level wire replay.',
            'Input similarity need not expose a useful semantic contrast; omitted trace values remain omitted.',
        ]}


def render(report):
    lines = ['# Public contrastive-trace development calibration', '',
        f"Status: **{report['status']}**. Gate: **{report['gate']}**. No selector trained.", '',
        f"Commitment: ${report['accounting']['study_committed_usd']} / ${report['study_limit_usd']}; cumulative ${report['accounting']['cumulative_committed_usd']} / ${report['cumulative_limit_usd']}.", '',
        '| Arm | Observed/planned | Full repairs | False acceptances | Regressions | Missing | Known API USD |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in report['arm_table']:
        lines.append(f"| {r['arm']} | {r['observed']}/{r['planned']} | {r['successes']} | {r['false_positives']} | {r['regressions']} | {r['missing']} | {r['known_usd']} |")
    lines += ['', 'Primary and fixed secondary comparisons:', '', '```json', json.dumps(report['contrasts'], indent=2), '```', '',
        'All twelve sources, unobserved cells, cost components and completion extremes are retained in analysis.json.', '', '## Limits', '']
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
        export_evidence(args.input, args.output, summarize_fn=summarize, report_entrypoint='report_repair_contrastive_study')
    print(json.dumps({'status': report['status'], 'gate': report['gate'], 'fit_selector': False}))


if __name__ == '__main__':
    main()
