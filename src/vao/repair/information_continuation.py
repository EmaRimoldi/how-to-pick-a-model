"""One reviewed exception for only the original trace probe's unsent requests.

The original zero-response segment is immutable. There is no recursive resume,
retry, replacement cell, changed prompt, new seed or additional budget.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import zipfile

from . import contract_collection as cc
from .contracts import TRACE_STUDY, provenance, task_from_record
from .environment import identity
from .pilot import file_hashes, source_commit
from .provider import dollars
from .records import rows, save

CLAIM = TRACE_STUDY + '-never-admitted-once'
REFERENCE = Path('experiments/python-repair/checkpoint-environment/results/information-interrupted-20261026')
ARCHIVE_SHA = 'f4241d9d1905a29e00b9c89a301570c72695fcf5605adc60a23b120948001e88'


def reference_files():
    manifest = cc.read(REFERENCE / 'evidence-manifest.json')
    archive = REFERENCE / 'evidence.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA or manifest['archive_sha256'] != ARCHIVE_SHA:
        raise ValueError('Published interrupted evidence changed')
    with zipfile.ZipFile(archive) as zipped:
        if len(zipped.namelist()) != len(set(zipped.namelist())) or set(zipped.namelist()) != set(manifest['files']):
            raise ValueError('Published archive membership differs')
        for name, digest in manifest['files'].items():
            if hashlib.sha256(zipped.read(name)).hexdigest() != digest:
                raise ValueError('Published archive member changed')
    return {name.removeprefix('collection/'): digest for name, digest in manifest['files'].items()
            if name.startswith('collection/')}


def parent_evidence(parent):
    if any(p.is_symlink() for p in parent.rglob('*')) or file_hashes(parent) != reference_files():
        raise ValueError('Parent must exactly match the published immutable interruption')
    manifest = cc.read(parent / 'manifest.json')
    if 'continuation' in manifest or not (parent / 'interruption.json').exists():
        raise ValueError('Only the original interrupted run may have this one successor')
    packet, limit, carried = cc.validate_freeze(manifest['freeze'])
    checked = cc.audit(parent)
    first = packet['requests'][0]['metadata']['attempt_id']
    if (packet['study'] != TRACE_STUDY or checked['observations'] != 0
            or checked['admissions'] != 1 or checked['settled_usd'] != '0'
            or checked['cap_exceeded'] or checked['sealed'] or len(packet['requests']) != 96
            or checked['pending'] != {first: '0.0032768'}
            or checked['study_committed_usd'] != '0.0032768'
            or checked['cumulative_committed_usd'] != '0.02539395'):
        raise ValueError('Expected exactly the original zero-response one-admission interruption')
    return manifest['freeze'], checked


def validate_config(config):
    if (config.get('status') != 'authorized_manual_never_admitted_exception'
            or config.get('live_calls_enabled') is not True or config.get('claim') != CLAIM
            or config.get('study_limit_usd') != '0.34' or config.get('cumulative_limit_usd') != '0.60'
            or config.get('minimum_request_interval_seconds') != 10
            or not isinstance(config.get('authorization_reference'), str)
            or not config['authorization_reference'].strip()):
        raise ValueError('A recorded bounded operational exception is required')


def freeze(parent, config, output):
    validate_config(config)
    original, checked = parent_evidence(parent)
    packet = original['packet']
    tasks = [task_from_record(t) for t in packet['tasks']]
    remaining = packet['requests'][1:]
    record = {'schema_version': 1, 'claim': CLAIM, 'created_at': datetime.now(timezone.utc).isoformat(),
        'source_commit': source_commit(), 'source_provenance': provenance(tasks, TRACE_STUDY),
        'parent_run': str(parent.resolve()), 'parent_archive_sha256': ARCHIVE_SHA,
        'parent_file_hashes': file_hashes(parent), 'original_freeze': original, 'config': config,
        'allowed_attempt_ids': [r['metadata']['attempt_id'] for r in remaining],
        'excluded_attempt_ids': list(checked['pending']),
        'allowed_requests_sha256': identity(remaining),
        'remaining_segment_limit_usd': str(Decimal('.34') - dollars(checked['study_committed_usd'])),
        'carried_cumulative_usd': checked['cumulative_committed_usd'],
        'retained_original_study_commitment_usd': checked['study_committed_usd'],
        'maximum_new_reservations_usd': str(95 * Decimal('.0032768')),
        'fit_selector': False, 'automatic_resume_allowed': False}
    record['continuation_id'] = identity(record)
    validate_continuation(record, parent, current=True)
    save(output, record)
    return record


def validate_continuation(record, parent, *, current=False):
    if (record.get('schema_version') != 1 or record.get('claim') != CLAIM
            or record.get('continuation_id') != identity({k: v for k,v in record.items() if k != 'continuation_id'})
            or record.get('parent_archive_sha256') != ARCHIVE_SHA
            or record.get('fit_selector') is not False or record.get('automatic_resume_allowed') is not False):
        raise ValueError('Continuation identity or scope changed')
    validate_config(record['config'])
    original, checked = parent_evidence(parent)
    if record['original_freeze'] != original or record['parent_file_hashes'] != file_hashes(parent):
        raise ValueError('Continuation rewrites its original evidence')
    packet = original['packet']
    remaining = packet['requests'][1:]
    if (record['allowed_attempt_ids'] != [r['metadata']['attempt_id'] for r in remaining]
            or record['excluded_attempt_ids'] != list(checked['pending'])
            or record['allowed_requests_sha256'] != identity(remaining)):
        raise ValueError('Only the exact original never-admitted requests, in order, are allowed')
    limit = Decimal('.34') - dollars(checked['study_committed_usd'])
    carried = dollars(checked['cumulative_committed_usd'])
    if (record['remaining_segment_limit_usd'] != str(limit)
            or record['carried_cumulative_usd'] != str(carried)
            or record['retained_original_study_commitment_usd'] != checked['study_committed_usd']
            or record['maximum_new_reservations_usd'] != str(95 * Decimal('.0032768'))
            or carried + limit > Decimal('.60') or 95 * Decimal('.0032768') > limit):
        raise ValueError('Prior reserves must be carried exactly once within both original caps')
    if current:
        tasks = [task_from_record(t) for t in packet['tasks']]
        if source_commit() != record['source_commit'] or provenance(tasks, TRACE_STUDY) != record['source_provenance']:
            raise ValueError('Continuation source differs from reviewed freeze')
        from .diagnostic_study import validate_origin
        validate_origin(packet)
    return packet, limit, carried, remaining


def audit_continuation(output, manifest):
    record = manifest['continuation']
    packet, limit, carried, requests = validate_continuation(record, output / 'parent')
    if manifest['freeze'] != record['original_freeze']:
        raise ValueError('Analysis must preserve the original full 96-request freeze')
    segment = cc._audit_records(output, packet, limit, carried, requests)
    parent = cc.audit(output / 'parent')
    if set(segment['committed_by_attempt_usd']) & set(parent['committed_by_attempt_usd']):
        raise ValueError('Continuation repeated an admitted request')
    study_total = dollars(parent['study_committed_usd']) + dollars(segment['study_committed_usd'])
    result = {**segment, 'admissions': parent['admissions'] + segment['admissions'],
        'planned_calls': 96, 'pending': {**parent['pending'], **segment['pending']},
        'committed_by_attempt_usd': {**parent['committed_by_attempt_usd'], **segment['committed_by_attempt_usd']},
        'study_committed_usd': str(study_total), 'carried_committed_usd': parent['carried_committed_usd'],
        'sealed': False, 'segment_sealed': segment['sealed'],
        'segment_admissions': segment['admissions'], 'segment_planned_calls': 95,
        'retained_original_missing_calls': 1,
        'cap_exceeded': segment['cap_exceeded'] or study_total > Decimal('.34')}
    if dollars(result['cumulative_committed_usd']) != dollars(result['carried_committed_usd']) + study_total:
        raise ValueError('Aggregate ledger fails carry-once reconciliation')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'live'))
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'freeze':
        if not args.config: parser.error('freeze requires the recorded exception config')
        result = freeze(args.input, cc.read(args.config), args.output)
        print(json.dumps({k: result[k] for k in ('continuation_id', 'remaining_segment_limit_usd', 'maximum_new_reservations_usd')}))
    else:
        record = cc.read(args.input)
        print(json.dumps(cc.collect(record['original_freeze'], args.output, continuation=record), indent=2))


if __name__ == '__main__':
    main()
