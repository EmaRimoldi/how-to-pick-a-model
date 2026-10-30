"""Prepare a coding-solver compatibility control on fixed failed checkpoints."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import zipfile

from .contracts import SOLVER_STUDY, provenance, public_feedback, request, study_settings
from .diagnostic_study import ARCHIVE_SHA, SOURCE, source_records
from .environment import RepairTask, identity
from .records import save
from .verifier import RepairVerifier

DRAWS, SEED = 4, 43128
CARRY = Decimal('0.05126739')
PRIOR = 'experiments/python-repair/checkpoint-environment/results/interface-stopped-20261026'
PRIOR_ARCHIVE_SHA = 'cecb09caa99ce851d1ca1df1f5e6bf719ea43fcdd166f5428af52da30dc0eb59'


def design():
    return {'arms': ['direct_repair'], 'draws_per_checkpoint': DRAWS, 'seed': SEED,
        'primary': 'full_public_and_evaluator_repair',
        'screening': {'minimum_repeated_bugs': 3, 'success_in_each_two_draw_half_per_bug': True},
        'fit_selector': False, 'causal_model_comparison': False}


def planned_requests(records):
    settings, _ = study_settings(SOLVER_STUDY)
    schedule = [(i, draw) for draw in range(DRAWS) for i, r in enumerate(records) if r['eligible']]
    random.Random(SEED).shuffle(schedule)
    planned = []
    for index, draw in schedule:
        record = records[index]
        task = RepairTask.from_dicts(record['public'], record['evaluator'])
        projected = request(task, record['source_public_result'], 'json_current', settings)
        meta = {'study': SOLVER_STUDY, 'trajectory': f'{SOLVER_STUDY}-task-{index:03d}-draw-{draw}',
            'phase': 'solver_probe', 'depth': 1, 'draw': draw, 'arm': 'direct_repair', 'contract': 'json_current',
            'task_index': index, 'task_hash': task.task_hash, 'source_attempt_id': record['source_attempt_id']}
        meta['attempt_id'] = identity(meta)
        planned.append({'metadata': meta, 'request': projected, 'provider_body': settings.body(projected, meta)})
    return planned


def construct(records, verifier):
    settings, limit = study_settings(SOLVER_STUDY)
    preflight = verifier.preflight()
    prepared = []
    for record in records:
        task = RepairTask.from_dicts(record['public'], record['evaluator'])
        result = verifier.check(task.public['files'], task.public['entrypoint'], task.public['public_cases'])
        if public_feedback(result) != record['source_public_result']:
            raise ValueError('Source public feedback no longer reproduces')
        eligible = not result['passed']
        prepared.append({**record, 'task_hash': task.task_hash, 'initial_public_result': result,
            'eligible': eligible, 'eligibility_reason': 'public_failure' if eligible else 'public_pass_no_repair_trigger'})
    tasks = [RepairTask.from_dicts(r['public'], r['evaluator']) for r in prepared]
    planned = planned_requests(prepared)
    maximum = len(planned) * settings.reserve
    packet = {'schema_version': 1, 'study': SOLVER_STUDY, 'status': 'draft_not_authorized',
        'api_calls': 0, 'model_results': False, 'live_calls_enabled': False,
        'monetary_authorization_usd': None, 'provider_settings': asdict(settings), 'design': design(),
        'source_archive_sha256': ARCHIVE_SHA, 'source_result': SOURCE,
        'prior_archive_sha256': PRIOR_ARCHIVE_SHA, 'prior_result': PRIOR,
        'source_provenance': provenance(tasks, SOLVER_STUDY), 'verifier_preflight': preflight,
        'tasks': prepared, 'requests': planned, 'maximum_calls': len(planned),
        'maximum_new_reservations_usd': str(maximum), 'proposed_cap_usd': str(limit),
        'reservation_usd': str(settings.reserve), 'closed_pilot_commitment_usd': str(CARRY),
        'maximum_cumulative_commitment_usd': str(CARRY + maximum)}
    packet['packet_id'] = identity(packet)
    validate_packet(packet)
    return packet


def validate_packet(packet):
    settings, limit = study_settings(SOLVER_STUDY)
    if (packet['study'] != SOLVER_STUDY or packet['schema_version'] != 1
            or packet['packet_id'] != identity({k: v for k, v in packet.items() if k != 'packet_id'})
            or packet['status'] != 'draft_not_authorized' or packet['api_calls'] != 0
            or packet['model_results'] or packet['live_calls_enabled'] or packet['monetary_authorization_usd'] is not None):
        raise ValueError('Invalid offline solver packet')
    if (packet['design'] != design() or packet['provider_settings'] != asdict(settings)
            or packet['source_archive_sha256'] != ARCHIVE_SHA or packet['source_result'] != SOURCE
            or packet['prior_archive_sha256'] != PRIOR_ARCHIVE_SHA or packet['prior_result'] != PRIOR):
        raise ValueError('Solver design, provider or origin differs')
    records = packet['tasks']
    if len(records) != 12 or sum(r['eligible'] for r in records) != 8:
        raise ValueError('Expected twelve source candidates and eight public failures')
    if len({r['source_attempt_id'] for r in records}) != 12:
        raise ValueError('Source candidates must be distinct')
    for r in records:
        task = RepairTask.from_dicts(r['public'], r['evaluator'])
        eligible = not r['source_public_result']['passed']
        if (task.task_hash != r['task_hash'] or r['eligible'] != eligible
                or public_feedback(r['initial_public_result']) != r['source_public_result']
                or r['eligibility_reason'] != ('public_failure' if eligible else 'public_pass_no_repair_trigger')):
            raise ValueError('Changed task, initial feedback or eligibility')
    planned = planned_requests(records)
    if packet['requests'] != planned or len(planned) != 32 or packet['maximum_calls'] != 32:
        raise ValueError('Exact solver requests or ordering changed')
    if len({r['metadata']['attempt_id'] for r in planned}) != 32 or len({identity(r['provider_body']) for r in planned}) != 32:
        raise ValueError('Repeated request identity or provider body')
    maximum = len(planned) * settings.reserve
    if (packet['maximum_new_reservations_usd'] != str(maximum) or maximum > limit
            or packet['reservation_usd'] != str(settings.reserve) or packet['proposed_cap_usd'] != str(limit)
            or packet['closed_pilot_commitment_usd'] != str(CARRY)
            or packet['maximum_cumulative_commitment_usd'] != str(CARRY + maximum)):
        raise ValueError('Solver accounting projection differs')
    return {'maximum_calls': 32, 'retained_candidates': 12, 'eligible': 8}


def validate_origin(packet):
    from .interface_study import PRIOR as TRACE_SOURCE, PRIOR_ARCHIVE_SHA as TRACE_SHA
    original = source_records(Path(SOURCE))
    for source, record in zip(original, packet['tasks']):
        if any(record[k] != v for k, v in source.items()):
            raise ValueError('Checkpoint differs from immutable 27B source')
    old_ids, old_bodies = set(), set()
    for directory, expected in ((SOURCE, ARCHIVE_SHA), (TRACE_SOURCE, TRACE_SHA), (PRIOR, PRIOR_ARCHIVE_SHA)):
        path = Path(directory) / 'evidence.zip'
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Historical archive changed')
        with zipfile.ZipFile(path) as archive:
            previous = json.loads(archive.read('collection/manifest.json'))['freeze']['packet']['requests']
        old_ids.update(r['metadata']['attempt_id'] for r in previous)
        old_bodies.update(identity(r['provider_body']) for r in previous)
    if (old_ids & {r['metadata']['attempt_id'] for r in packet['requests']}
            or old_bodies & {identity(r['provider_body']) for r in packet['requests']}):
        raise ValueError('Fresh draws must not repeat any old admitted or missing request')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    packet = construct(source_records(), RepairVerifier())
    validate_origin(packet)
    save(args.output, packet)
    print(json.dumps({k: packet[k] for k in ('packet_id', 'maximum_calls', 'maximum_new_reservations_usd', 'proposed_cap_usd')}))


if __name__ == '__main__':
    main()
