"""Terminal-only coding-solver compatibility report; no selector or model comparison."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import random

from vao.repair.contract_collection import audit, read
from vao.repair.contracts import SOLVER_STUDY
from vao.repair.solver_study import DRAWS
from vao.repair.records import rows, save
from .contract_diagnostic import export_evidence
from .repair_stagnation import classify


def interval(values):
    rng = random.Random(43129)
    sampled = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(10000))
    return [sampled[249], sampled[9749]]


def summarize(output):
    if not any((output / name).exists() for name in ('pilot-completion.json', 'interruption.json')):
        raise ValueError('Do not inspect active treatment outcomes')
    checked = audit(output)
    frozen = read(output / 'manifest.json')['freeze']
    packet = frozen['packet']
    if packet['study'] != SOLVER_STUDY:
        raise ValueError('Expected solver-compatibility study')
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
                category = classify(source['public']['files'], artifact, source['public']['entrypoint'])
        receipt = read(output / 'receipts' / (key + '.json')) if row or key in checked['paid_without_outcome'] else None
        cells.append({**meta, 'observed': row is not None, 'full_pass': row['full_pass'] if row else None,
            'usable_source': all(row['decoded'][k] for k in ('artifact_valid', 'syntax_valid', 'declared_entrypoint')) if row else None,
            'edit_category': category, 'public_pass': public, 'public_fraction': fraction,
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
    success = sum(c['full_pass'] is True for c in cells)
    missing = sum(not c['observed'] for c in cells)
    complete = checked['sealed'] and not checked['cap_exceeded']
    tasks = []
    for i, record in enumerate(packet['tasks']):
        scoped = [c for c in cells if c['task_index'] == i]
        half_successes = [sum(c['full_pass'] is True for c in scoped if c['draw'] in half) for half in ({0, 1}, {2, 3})]
        half_unknowns = [sum(not c['observed'] for c in scoped if c['draw'] in half) for half in ({0, 1}, {2, 3})]
        tasks.append({'task_index': i, 'task': record['public']['task_id'], 'eligible': record['eligible'],
            'reason': record['eligibility_reason'], 'source_full_pass': record['source_full_pass'],
            'cells': scoped, 'full_successes': sum(c['full_pass'] is True for c in scoped),
            'half_successes': half_successes, 'half_unknowns': half_unknowns,
            'repeated_success_observed': bool(scoped) and all(half_successes),
            'repeated_success_possible': bool(scoped) and all(a + b for a, b in zip(half_successes, half_unknowns))})
    lower = sum(t['repeated_success_observed'] for t in tasks)
    upper = sum(t['repeated_success_possible'] for t in tasks)
    gate = ('candidate_for_separate_intervention_calibration' if lower >= 3 else 'no_repeated_solver_compatibility_demonstrated') if complete else 'inconclusive_incomplete_bank'
    categories = ('exact_copy', 'format_or_comment_only', 'entrypoint_only_syntax_change', 'other_syntax_change', 'unparseable', 'no_artifact')
    table = {'planned': len(cells), 'observed': len(cells) - missing, 'successes': success, 'missing': missing,
        'success_bounds': [success / len(cells), (success + missing) / len(cells)],
        'mean_success': success / len(cells) if complete else None,
        'descriptive_bug_bootstrap_95': interval([t['full_successes'] / DRAWS for t in tasks if t['eligible']]) if complete else None,
        'usable_sources': sum(c['usable_source'] is True for c in cells),
        'public_passes': sum(c['public_pass'] is True for c in cells),
        'false_positives': sum(c['public_false_positive'] is True for c in cells),
        'regressions': sum(c['public_regression'] is True for c in cells),
        'public_improvements': sum(c['public_improvement'] is True for c in cells),
        'edit_categories': {k: sum(c['edit_category'] == k for c in cells) for k in categories},
        'known_usd': str(sum((Decimal(c['cost_usd']) for c in cells if c['cost_usd'] is not None), Decimal(0))),
        'committed_usd': str(sum((Decimal(c['committed_usd']) for c in cells), Decimal(0))),
        'counterfactual_prefix_usd': str(sum((Decimal(c['counterfactual_prefix_usd']) for c in cells), Decimal(0))),
        'source_public_verification_seconds_if_deployed': sum(c['source_public_verification_seconds_per_deployment'] for c in cells),
        'response_verification_seconds': sum(c['response_verification_seconds'] for c in cells if c['observed']),
        'provider_elapsed_seconds': sum(c['provider_elapsed_seconds'] for c in cells if c['provider_elapsed_seconds'] is not None)}
    if Decimal(table['committed_usd']) != Decimal(checked['study_committed_usd']):
        raise ValueError('Cell accounting differs from study commitment')
    return {'study': SOLVER_STUDY, 'model_results': True,
        'status': 'complete_development_solver_probe' if complete else 'incomplete_development_solver_probe',
        'provider_settings': packet['provider_settings'],
        'packet_id': packet['packet_id'], 'freeze_id': frozen['freeze_id'], 'source_commit': frozen['source_commit'],
        'accounting': checked, 'study_limit_usd': frozen['authorized_limit_usd'], 'cumulative_limit_usd': frozen['config']['cumulative_limit_usd'],
        'summary': table, 'task_table': tasks, 'gate': gate, 'repeated_bug_count_bounds': [lower, upper],
        'fit_selector': False, 'causal_model_comparison': False,
        'limitations': ['One model/endpoint configuration on eight previously exposed failure checkpoints, with four draws; twelve source records retained.',
            'Historical Gemma responses are not concurrent paired controls. Model, provider, precision, seeds and time differ; no scaling or model-causality claim.',
            'This checks solver compatibility, not action complementarity, acquisition benefit or an equal-budget policy advantage.',
            'No trace, reference patch, expected hidden value or extra editing cue is supplied. Original instructions and raw public feedback are unchanged.',
            'Incomplete banks keep all selected cells and finite missingness bounds; mean/bootstrap/gate remain unavailable.',
            'Complete-bank bootstrap intervals resample eight bugs and are descriptive, not evidence for an untouched population.',
            'Every counted repair passes public and evaluator suites; this does not prove correctness on all possible inputs.',
            'Prefix cost is counted once per counterfactual deployment and not rebilled into the actual ledger. Local runtime and provider latency are separate.',
            'A passed screen permits only a separately frozen intervention study. No automatic selector fitting or further calls.']}


def render(report):
    s = report['summary']
    lines = ['# Coding-solver compatibility control', '',
        f"Status: **{report['status']}**. Gate: **{report['gate']}**. No selector trained.", '',
        f"Responses: {s['observed']}/{s['planned']}; full repairs: {s['successes']}; missing: {s['missing']}.", '',
        f"Study commitment: ${report['accounting']['study_committed_usd']} / ${report['study_limit_usd']}; cumulative: ${report['accounting']['cumulative_committed_usd']} / ${report['cumulative_limit_usd']}.", '',
        '| Development checkpoint | Eligible | Received | Full repairs | First / second half successes |',
        '| --- | --- | ---: | ---: | --- |']
    for t in report['task_table']:
        lines.append(f"| {t['task']} | {t['eligible']} | {sum(c['observed'] for c in t['cells'])} | {t['full_successes']} | {t['half_successes']} |")
    lines += ['', '## Descriptive summary', '', '```json', json.dumps(s, indent=2), '```', '', '## Limitations', '']
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
        export_evidence(args.input, args.output, summarize_fn=summarize, report_entrypoint='report_repair_solver_study')
    print(json.dumps({'status': report['status'], 'gate': report['gate'], 'fit_selector': False}))


if __name__ == '__main__':
    main()
