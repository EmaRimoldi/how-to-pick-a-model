"""Terminal-only difficulty report retaining all six initial attempts."""
import argparse
import json
from pathlib import Path

from vao.repair.contract_collection import audit, read
from vao.repair.contracts import COVERAGE_PREFIX_STUDY
from vao.repair.records import rows, save


def summarize(output):
    if not any((output / name).exists() for name in ('pilot-completion.json', 'interruption.json')):
        raise ValueError('Initial outcomes may be read only after terminal collection')
    checked = audit(output)
    frozen = read(output / 'manifest.json')['freeze']; packet = frozen['packet']
    if packet['study'] != COVERAGE_PREFIX_STUDY:
        raise ValueError('Not the declared initial-repair study')
    observed = {r['attempt_id']: r for r in rows(output / 'observations.jsonl')}
    cells = []
    for planned in sorted(packet['requests'], key=lambda r: r['metadata']['task_index']):
        meta = planned['metadata']; key = meta['attempt_id']; row = observed.get(key)
        public = evaluator = None
        if row and row['artifact']:
            root = output / 'cells' / key / 'objects'
            public = read(root / (row['public'] + '.json'))['result']
            evaluator = read(root / (row['evaluator'] + '.json'))['result']
        failed = sum(not r['passed'] for r in public['cases']) if public else None
        cells.append({'task_index': meta['task_index'], 'task': packet['tasks'][meta['task_index']]['public']['task_id'],
            'attempt_id': key, 'observed': row is not None, 'artifact_valid': row['decoded']['artifact_valid'] if row else None,
            'syntax_valid': row['decoded']['syntax_valid'] if row else None,
            'public_pass': public['passed'] if public else None, 'failed_public_cases': failed,
            'full_pass': row['full_pass'] if row else None,
            'false_public_acceptance': bool(public and public['passed'] and not evaluator['passed']) if row else None,
            'eligible_recovery_checkpoint': public is not None and not public['passed'],
            'cost_usd': row['cost_usd'] if row else None,
            'committed_usd': checked['committed_by_attempt_usd'].get(key, '0')})
    complete = checked['sealed'] and not checked['cap_exceeded']
    multiple = sum(c['eligible_recovery_checkpoint'] and c['failed_public_cases'] >= 2 for c in cells)
    eligible = sum(c['eligible_recovery_checkpoint'] for c in cells)
    gate = ('eligible_for_prespecified_recovery_stage' if multiple >= 3 else 'insufficient_failure_coverage_headroom') if complete else 'inconclusive_incomplete_prefix'
    successes = sum(c['full_pass'] is True for c in cells); missing = sum(not c['observed'] for c in cells)
    return {'study': COVERAGE_PREFIX_STUDY, 'status': 'complete_initial_calibration' if complete else 'incomplete_initial_calibration',
        'model_results': True, 'accounting': checked, 'source_commit': frozen['source_commit'],
        'freeze_id': frozen['freeze_id'], 'packet_id': packet['packet_id'], 'tasks': cells,
        'full_successes': successes, 'missing': missing, 'selected_task_success_bounds': [successes / 6, (successes + missing) / 6],
        'eligible_recovery_checkpoints': eligible, 'multiple_public_failure_checkpoints': multiple, 'gate': gate,
        'maximum_recovery_requests_if_permitted': 9 * eligible if gate == 'eligible_for_prespecified_recovery_stage' else 0,
        'fit_selector': False, 'diagnostic_benefit_established': False,
        'limits': ['Six purposively selected development bugs, one initial draw; no held-out claim.',
            'Eligibility uses decoded artifacts and public failures only, never private correctness.',
            'Missing and malformed outputs remain in the six-task denominator.',
            'Passing the difficulty gate permits only the separate prespecified recovery stage.',
            'The selector and equal-total-resource policy benefit remain unestablished.']}


def render(report):
    lines = ['# Natural-failure difficulty calibration', '', f"Status: **{report['status']}**. Gate: **{report['gate']}**.", '',
        f"Full repairs: {report['full_successes']}/6; missing: {report['missing']}. Natural recovery checkpoints: {report['eligible_recovery_checkpoints']}; with multiple public failures: {report['multiple_public_failure_checkpoints']}.", '',
        f"Cumulative commitment: ${report['accounting']['cumulative_committed_usd']} / $0.60, including historical reserves.", '',
        '| Task | Observed | Full repair | Public failures | Public false acceptance | Recovery checkpoint |',
        '| --- | --- | --- | --- | --- | --- |']
    for c in report['tasks']:
        lines.append(f"| {c['task']} | {c['observed']} | {c['full_pass']} | {c['failed_public_cases']} | {c['false_public_acceptance']} | {c['eligible_recovery_checkpoint']} |")
    lines += ['', *report['limits'], '', 'No diagnostic-benefit claim and no selector training.', '']
    return '\n'.join(lines)


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
        from .contract_diagnostic import export_evidence
        export_evidence(args.input, args.output, summarize_fn=summarize, report_entrypoint='report_repair_coverage_prefix')
    print(json.dumps({'status': report['status'], 'gate': report['gate'], 'fit_selector': False}))


if __name__ == '__main__':
    main()
