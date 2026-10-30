"""Prospective matched generation comparisons conditional on one saved public acquisition."""
import argparse
from decimal import Decimal
from pathlib import Path
import json
import random

from vao.repair.contract_collection import audit, read
from vao.repair.contracts import SNAPSHOT_TRACE_STUDY
from vao.repair.region_information_study import ARMS, DRAWS
from vao.repair.records import rows, save
from .contract_diagnostic import export_evidence


def screen(cells, bugs):
    """Monotone primary screen at both binary completion extremes, no imputation."""
    expected = {(bug, draw, arm) for bug in bugs for draw in range(DRAWS) for arm in ('focused', 'focused_trace')}
    if len(bugs) != len(set(bugs)) or not bugs or set(cells) != expected or any(v is not None and type(v) is not bool for v in cells.values()):
        raise ValueError('Every selected primary cell must be present, boolean or unknown')
    def extreme(favorable):
        completed = {k: v if v is not None else ((k[2] == 'focused_trace') == favorable) for k, v in cells.items()}
        repeated = sum(sum(completed[(b, d, 'focused_trace')] for d in range(DRAWS)) >= 2 for b in bugs)
        by_draw = [sum(int(completed[(b, d, 'focused_trace')]) - int(completed[(b, d, 'focused')]) for b in bugs) for d in range(DRAWS)]
        return {'bugs_with_two_trace_successes': repeated, 'net_trace_successes': sum(by_draw),
            'draw_differences': by_draw,
            'screen_passed': repeated >= 3 and sum(by_draw) >= 4 and all(v > 0 for v in by_draw)}
    lower, upper = extreme(False), extreme(True)
    return {'least_favorable': lower, 'most_favorable': upper,
        'all_completions_pass': lower['screen_passed'], 'no_completion_passes': not upper['screen_passed'],
        'missing_primary_cells': sum(v is None for v in cells.values()), 'fit_selector': False}


def interval(values):
    rng = random.Random(43140)
    draws = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(10000))
    return [draws[249], draws[9749]]


def summarize(output):
    if not ((output / 'pilot-completion.json').exists() or (output / 'interruption.json').exists()):
        raise ValueError('Do not inspect treatments before terminal state')
    checked = audit(output)
    frozen = read(output / 'manifest.json')['freeze']
    packet = frozen['packet']
    if packet['study'] != SNAPSHOT_TRACE_STUDY:
        raise ValueError('Expected the separately frozen region-information study')
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
        diagnostic = source['diagnostic'] if meta['arm'] == 'focused_trace' else None
        public_fraction = (public['passed_cases'] / public['total_cases'] if public else 0) if row else None
        cells.append({**meta, 'observed': row is not None, 'full_pass': row['full_pass'] if row else None,
            'artifact_valid': row['decoded']['artifact_valid'] if row else None,
            'public_pass': bool(public and public['passed']) if row else None,
            'false_public_acceptance': bool(public and public['passed'] and not row['full_pass']) if row else None,
            'net_public_regression': public_fraction < source['source_public_result']['passed_cases'] / source['source_public_result']['total_cases'] if row else None,
            'cost_usd': read(output / 'receipts' / (key + '.json'))['cost_usd'] if row or key in checked['paid_without_outcome'] else None,
            'committed_usd': checked['committed_by_attempt_usd'].get(key, '0'),
            'uncertain': key in checked['pending'], 'paid_without_outcome': key in checked['paid_without_outcome'],
            'source_prefix_usd': source['source_prefix_usd'],
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
        'reason': r['eligibility_reason'], 'checkpoint_kind': r['checkpoint_kind'],
        'snapshot_id': r['acquisition_snapshot']['snapshot_id'], 'diagnostic_available': r['diagnostic']['available'],
        'cells': [c for c in cells if c['task_index'] == i]} for i, r in enumerate(packet['tasks'])]
    contrasts, by_arm = {}, {r['arm']: r for r in table}
    for treatment, control in [('focused_trace', 'focused')]:
        a, b = by_arm[treatment], by_arm[control]
        values = [(sum(c['full_pass'] for c in t['cells'] if c['arm'] == treatment)
            - sum(c['full_pass'] for c in t['cells'] if c['arm'] == control)) / DRAWS for t in tasks if t['eligible']] if complete else []
        contrasts[treatment + '_minus_' + control] = {'primary': control == 'focused' and treatment == 'focused_trace',
            'selected_cell_difference_bounds': [a['success_bounds'][0] - b['success_bounds'][1], a['success_bounds'][1] - b['success_bounds'][0]],
            'mean_difference': sum(values) / len(values) if complete else None,
            'descriptive_bug_bootstrap_95': interval(values) if complete else None}
    robust = screen({(c['task_index'], c['draw'], c['arm']): c['full_pass'] for c in cells}, [t['task_index'] for t in tasks if t['eligible']])
    gate = ('inconclusive_accounting_cap_exceeded' if checked['cap_exceeded'] else
        'inconclusive_incomplete_bank' if not complete else
        'candidate_for_generated_failure_calibration' if robust['all_completions_pass'] else
        'no_completion_meets_development_screen' if robust['no_completion_passes'] else 'inconclusive_selected_cell_bounds')
    return {'study': packet['study'], 'model_results': True,
        'status': 'complete_frozen_region_development_probe' if complete else 'incomplete_frozen_region_development_probe',
        'packet_id': packet['packet_id'], 'freeze_id': frozen['freeze_id'], 'source_commit': frozen['source_commit'],
        'accounting': checked, 'study_limit_usd': frozen['authorized_limit_usd'], 'cumulative_limit_usd': frozen['config']['cumulative_limit_usd'],
        'arm_table': table, 'task_table': tasks, 'contrasts': contrasts, 'screen': robust, 'gate': gate, 'fit_selector': False,
        'acquisition_resources': {
            'actual_frozen_acquisitions': len(packet['tasks']),
            'actual_frozen_sandbox_executions': sum(t['diagnostic']['additional_executions'] for t in packet['tasks']),
            'actual_frozen_diagnostic_seconds': sum(t['diagnostic']['diagnostic_seconds'] for t in packet['tasks']),
            'generation_draws_condition_on_saved_acquisition': True,
            'original_artifact_generation_api_usd': '0',
            'diagnostic_reexecution_during_collection': False},
        'limitations': [
            'Eight exposed original buggy artifacts after public-test failure, two generation draws per arm; development only.',
            'These are not model-generated failed repairs and cannot replace final post-repair-failure policy evaluation.',
            'Both draws use the same actual frozen acquisition per bug; this tests generation repeatability conditional on that acquisition, not diagnostic stochasticity.',
            'All eight candidates and all 32 selected cells retained. No historical controls, pooling or filled missing requests.',
            'Primary focused_trace minus focused, with identical core feedback, solver settings and matched seeds.',
            'Equal per-call limits are not equal realized spending or equal total-resource budgets.',
            'Original source artifacts have no API generation charge; historical financial carry is not source-prefix generation cost.',
            'Frozen diagnostic acquisition is performed once per bug. Counterfactual deployment costs charge it on every planned treatment draw; cached research work is not rebilled.',
            'Source verification, diagnostic selection and execution, response public verification and evaluator-only research time are reported separately; local seconds are not dollars.',
            'Prompt projection and full deployment overhead remain outside this calibration and must be accounted for in a later policy runner.',
            'Incomplete banks have null mean/bootstrap and an inconclusive gate regardless of finite completion bounds; missingness is not assumed random.',
            'A complete-bank screen pass only permits a separate generated-failure calibration, never selector training.',
            'Bounded network cooldown may admit only the next never-admitted cell; no retry, resumption, successor, fallback or key rotation.',
            'Raw SSE bytes are not archived; saved metrics are not byte-level wire replay.',
            'Trace coverage is bounded, values may be omitted, and independent diagnostic acquisitions may contain stochastic differences.',
        ]}


def render(report):
    lines = ['# Frozen public-region trace development calibration', '',
        f"Status: **{report['status']}**. Gate: **{report['gate']}**. No selector trained.", '',
        f"Commitment: ${report['accounting']['study_committed_usd']} / ${report['study_limit_usd']}; cumulative ${report['accounting']['cumulative_committed_usd']} / ${report['cumulative_limit_usd']}.", '',
        '| Arm | Observed/planned | Full repairs | False acceptances | Regressions | Missing | Known API USD |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in report['arm_table']:
        lines.append(f"| {r['arm']} | {r['observed']}/{r['planned']} | {r['successes']} | {r['false_positives']} | {r['regressions']} | {r['missing']} | {r['known_usd']} |")
    lines += ['', 'Prespecified primary comparison:', '', '```json', json.dumps(report['contrasts'], indent=2), '```', '',
        'All eight original-bug sources, 32 selected cells, actual acquisition resources, deployment cost projections and completion extremes are retained in analysis.json.', '', '## Limits', '']
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
        export_evidence(args.input, args.output, summarize_fn=summarize, report_entrypoint='report_repair_region_information')
    print(json.dumps({'status': report['status'], 'gate': report['gate'], 'fit_selector': False}))


if __name__ == '__main__':
    main()
