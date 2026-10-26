"""Prespecified descriptive report for the terminal output-contract diagnostic."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

from vao.repair.contracts import CONTRACTS, TRACE_STUDY, INTERFACE_STUDY, SOLVER_STUDY, QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY
from vao.repair.contract_collection import ROOT, audit, read
from vao.repair.records import rows, save


def summarize(output: Path):
    if not ((output / 'pilot-completion.json').exists() or (output / 'interruption.json').exists()):
        raise ValueError('Do not inspect outcomes of an active collection')
    checked = audit(output)
    frozen = read(output / 'manifest.json')['freeze']
    packet = frozen['packet']
    if packet['study'] == SOLVER_STUDY:
        raise ValueError('Use the solver-compatibility report, not the historical contract gate')
    if packet['study'] in (TRACE_STUDY, QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY):
        raise ValueError('Use the public-trace information report, not the historical contract gate')
    if packet['study'] == INTERFACE_STUDY:
        raise ValueError('Use the interface-cue report, not the historical contract gate')
    observed = {r['attempt_id']: r for r in rows(output / 'observations.jsonl')}
    cells = []
    for planned in packet['requests']:
        meta = planned['metadata']; key = meta['attempt_id']
        row = observed.get(key)
        # Missing response/local score remains unknown, not a false model outcome.
        cells.append({'attempt_id': key, 'task_index': meta['task_index'], 'contract': meta['contract'],
            'observed': row is not None, 'full_pass': row['full_pass'] if row else None,
            'artifact_valid': row['decoded']['artifact_valid'] if row else None,
            'syntax_valid': row['decoded']['syntax_valid'] if row else None,
            'declared_entrypoint': row['decoded']['declared_entrypoint'] if row else None,
            'ready_source': bool(row['decoded']['artifact_valid'] and row['decoded']['syntax_valid'] and row['decoded']['declared_entrypoint']) if row else None,
            'committed_usd': checked['committed_by_attempt_usd'].get(key, '0'),
            'cost_usd': read(output / 'receipts' / (key + '.json'))['cost_usd'] if key in observed or key in checked['paid_without_outcome'] else None,
            'uncertain_call': key in checked['pending'], 'paid_without_outcome': key in checked['paid_without_outcome']})
    table = []
    complete = checked['sealed'] and not checked['cap_exceeded']
    for contract in CONTRACTS:
        scoped = [r for r in cells if r['contract'] == contract]
        successes = sum(r['full_pass'] is True for r in scoped)
        missing = sum(not r['observed'] for r in scoped)
        ready = sum(r['ready_source'] is True for r in scoped)
        ready_failed = sum(r['ready_source'] is True and r['full_pass'] is False for r in scoped)
        table.append({'contract': contract, 'tasks': len(scoped), 'observed': len(scoped) - missing,
            'missing': missing, 'artifact_valid': sum(r['artifact_valid'] is True for r in scoped),
            'syntax_valid': sum(r['syntax_valid'] is True for r in scoped),
            'declared_entrypoint': sum(r['declared_entrypoint'] is True for r in scoped),
            'ready_source': ready, 'ready_but_unsolved': ready_failed, 'full_successes': successes,
            'selected_task_success_bounds': [successes / len(scoped), (successes + missing) / len(scoped)],
            'known_charges_usd': str(sum((Decimal(r['cost_usd']) for r in scoped if r['cost_usd'] is not None), Decimal(0))),
            'committed_usd': str(sum((Decimal(r['committed_usd']) for r in scoped), Decimal(0))),
            'engineering_eligible': (successes >= 3 and ready >= 10 and ready_failed >= 2) if complete else None})
    if sum((Decimal(t['committed_usd']) for t in table), Decimal(0)) != Decimal(checked['study_committed_usd']):
        raise ValueError('Per-contract accounting fails to reproduce study total')
    eligible = [t for t in table if t['engineering_eligible']]
    eligible.sort(key=lambda t: (-t['full_successes'], Decimal(t['known_charges_usd']), CONTRACTS.index(t['contract'])))
    task_table = [{'task_index': index, 'task': task['public']['task_id'],
                   'cells': [next(r for r in cells if r['task_index'] == index and r['contract'] == c) for c in CONTRACTS]}
                  for index, task in enumerate(packet['tasks'])]
    return {'study': packet['study'], 'model_results': True,
        'status': 'development_diagnostic_complete' if complete else 'incomplete_development_diagnostic',
        'accounting': checked, 'tasks': len(task_table), 'packet_id': packet['packet_id'],
        'freeze_id': frozen['freeze_id'], 'source_commit': frozen['source_commit'],
        'study_limit_usd': frozen['authorized_limit_usd'], 'cumulative_limit_usd': frozen['config']['cumulative_limit_usd'],
        'contract_table': table, 'task_table': task_table,
        'engineering_candidate_for_future_calibration': eligible[0]['contract'] if eligible else None,
        'gate': ('candidate_for_future_recovery_calibration' if eligible else 'no_contract_meets_engineering_checks') if complete else 'inconclusive_incomplete_bank',
        'fit_selector': False,
        'limitations': ['Already inspected development bugs, one draw per contract: no held-out inference, confidence claim or p-values.',
            'Text mode changes both prompt wording and provider JSON constraints; effects cannot be attributed to wording alone.',
            'Container validity is not comparable across encodings. Syntax plus a declared entrypoint also does not prove correctness.',
            'Missing-cell bounds concern these selected tasks only, not unobserved task populations.',
            'The engineering gate requires a complete bank. All three contracts remain reported even when none qualifies.',
            'Equal per-call allowance is not equal actual spending. Local verification and inference timings remain in saved records.',
            'A candidate passing the practical checks still needs new recovery data and replicated action complementarity before fitting a selector.']}


def render(report):
    lines = ['# Output-contract development diagnostic', '',
        f"Status: **{report['status']}**. Gate: **{report['gate']}**. No selector trained.", '',
        f"Known study charges: ${report['accounting']['settled_usd']}; study commitment including reserves: ${report['accounting']['study_committed_usd']} / ${report['study_limit_usd']}.",
        f"Prior repair commitment: ${report['accounting']['carried_committed_usd']}; cumulative: ${report['accounting']['cumulative_committed_usd']} / ${report['cumulative_limit_usd']}.", '',
        '| Contract | Observed / tasks | Ready source | Ready, unsolved | Full successes | Missing-task bounds | Known API charges | Commitment |',
        '| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |']
    for r in report['contract_table']:
        lo, hi = r['selected_task_success_bounds']
        lines.append(f"| {r['contract']} | {r['observed']}/{r['tasks']} | {r['ready_source']} | {r['ready_but_unsolved']} | {r['full_successes']} | [{lo:.3f}, {hi:.3f}] | {r['known_charges_usd']} | {r['committed_usd']} |")
    lines += ['', 'Ready source means a valid file artifact, parseable Python and a top-level declared entrypoint; full success additionally requires both public and evaluator tests. Bounds are worst/best assignments to missing cells, not confidence intervals.', '',
        '| Task | Current JSON | Example JSON | Python text |', '| --- | --- | --- | --- |']
    for t in report['task_table']:
        labels = ['missing' if not r['observed'] else ('pass' if r['full_pass'] else ('tests fail' if r['ready_source'] else 'unusable source')) for r in t['cells']]
        lines.append('| ' + t['task'] + ' | ' + ' | '.join(labels) + ' |')
    lines += ['', 'Candidate for a separately reviewed future recovery calibration: ' + str(report['engineering_candidate_for_future_calibration']) + '.', '', '## Limits', '']
    lines.extend('- ' + item for item in report['limitations'])
    return '\n'.join(lines) + '\n'


def export_evidence(source: Path, output: Path, *, summarize_fn=None, report_entrypoint='report_repair_contract_probe'):
    """Export audited terminal records and inert, hash-verified source snapshots."""
    (summarize_fn or summarize)(source)  # Includes terminal-only, receipt and ledger validation.
    source_manifest = read(source / 'manifest.json')
    frozen = source_manifest['freeze']
    commit = frozen['source_commit']
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Invalid frozen source commit')
    entries = {}
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('Evidence cannot contain symlinks')
        if path.is_file():
            if path.suffix not in ('.json', '.jsonl'):
                raise ValueError('Only inert JSON evidence can be exported')
            entries['collection/' + path.relative_to(source).as_posix()] = path.read_bytes()
    snapshots = [(commit, frozen['packet']['source_provenance']['sources'])]
    if 'continuation' in source_manifest:
        successor = source_manifest['continuation']
        snapshots.append((successor['source_commit'], successor['source_provenance']['sources']))
    for source_revision, sources in snapshots:
        if not re.fullmatch(r'[a-f0-9]{40}', source_revision):
            raise ValueError('Invalid frozen continuation commit')
        for name, expected in sources.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe frozen source path')
            content = subprocess.run(['git', 'show', f'{source_revision}:src/vao/{name}'], cwd=ROOT,
                                     capture_output=True, check=True).stdout
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError('Committed source differs from frozen source hash')
            entries[f'frozen-sources/{source_revision}/{name}.txt'] = content
    if any(re.search(rb'sk-or-v1-[a-f0-9]{64}', content) for content in entries.values()):
        raise ValueError('Credential-shaped content prevents export')
    archive = output / 'evidence.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, content)
    manifest = {'leaf': 'collection', 'source_commit': commit,
        'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'files': {name: hashlib.sha256(content).hexdigest() for name, content in sorted(entries.items())},
        'source_format': 'Frozen source snapshots are inert .txt files; model outputs remain JSON data.',
        'reproduction': f'Verify hashes, extract into a fresh directory, then run the installed {report_entrypoint} entry point with --input <extracted>/collection and a fresh --output. All analysis and Markdown fields must match; no model calls are made.'}
    save(output / 'evidence-manifest.json', manifest)
    return manifest


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
        export_evidence(args.input, args.output)
    print(json.dumps({'status': report['status'], 'gate': report['gate'], 'fit_selector': False}, indent=2))


if __name__ == '__main__':
    main()
