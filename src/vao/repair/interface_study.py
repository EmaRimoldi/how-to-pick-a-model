"""Prepare four matched interface conditions after the closed trace study."""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import zipfile

from .contracts import INTERFACE_STUDY, provenance, public_feedback, request, study_settings
from .diagnostic_study import ARCHIVE_SHA, SOURCE, source_records
from .environment import RepairTask, canonical, identity
from .records import save
from .verifier import RepairVerifier

ARMS = ('original', 'claim_removed', 'helpers_explicit', 'both')
FACTORS = {'original': (False, False), 'claim_removed': (True, False),
           'helpers_explicit': (False, True), 'both': (True, True)}
CLAIM = '; upstream definitions are unchanged.'
PERMISSION = (' Every supplied function, class and helper may be changed when needed to satisfy '
              'the specification and public tests. Preserve the external callable\'s name, '
              'arguments and return contract.')
DRAWS, SEED = 4, 43126
CARRY = Decimal('0.04058467')
PRIOR = 'experiments/python-repair/checkpoint-environment/results/information-stopped-20261026'
PRIOR_ARCHIVE_SHA = 'f6e6cad5035268a5015fa4db35943f67201e72480020d0efb3d6b2221486c0fe'


def design():
    return {'arms': list(ARMS), 'factors': {k: list(v) for k, v in FACTORS.items()},
        'draws_per_arm': DRAWS, 'seed': SEED, 'primary': 'both_minus_original',
        'screening': {'minimum_bugs_with_two_both_successes': 3,
                      'minimum_net_both_successes': 4, 'positive_in_each_two_draw_half': True},
        'fit_selector': False}


def remove_claim(files):
    """Remove a single exact comment clause; retain attribution and AST/line count."""
    updated, count = {}, 0
    for name, source in files.items():
        lines = source.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith('# Adapted from ') and line.rstrip('\r\n').endswith(CLAIM):
                lines[i] = line.replace(CLAIM, '.', 1)
                count += 1
        updated[name] = ''.join(lines)
        if ast.dump(ast.parse(source)) != ast.dump(ast.parse(updated[name])):
            raise ValueError('Claim removal changed executable syntax')
    if count != 1:
        raise ValueError('Expected exactly one declared provenance clause')
    return updated


def project(record, arm):
    if arm not in ARMS:
        raise ValueError('Undeclared interface condition')
    task = RepairTask.from_dicts(record['public'], record['evaluator'])
    settings, _ = study_settings(INTERFACE_STUDY)
    projected = request(task, record['source_public_result'], 'json_current', settings)
    payload = json.loads(projected['messages'][1]['content'])
    remove, explicit = FACTORS[arm]
    if remove:
        payload['files'] = remove_claim(payload['files'])
    if explicit:
        projected['messages'][0]['content'] += PERMISSION
    projected['messages'][1]['content'] = canonical(payload)
    return projected


def schedule(records):
    pairs = [(i, draw) for draw in range(DRAWS) for i, r in enumerate(records) if r['eligible']]
    random.Random(SEED).shuffle(pairs)
    # Each bug sees each condition at each within-block position exactly once.
    orders = [ARMS[i:] + ARMS[:i] for i in range(len(ARMS))]
    return [(i, draw, arm) for i, draw in pairs for arm in orders[(i + draw) % len(ARMS)]]


def planned_requests(records):
    settings, _ = study_settings(INTERFACE_STUDY)
    planned = []
    for index, draw, arm in schedule(records):
        record = records[index]
        task = RepairTask.from_dicts(record['public'], record['evaluator'])
        projected = project(record, arm)
        meta = {'study': INTERFACE_STUDY, 'trajectory': f'{INTERFACE_STUDY}-task-{index:03d}-draw-{draw}',
            'phase': 'interface_probe', 'depth': 1, 'draw': draw, 'arm': arm, 'contract': 'json_current',
            'task_index': index, 'task_hash': task.task_hash, 'source_attempt_id': record['source_attempt_id']}
        meta['attempt_id'] = identity(meta)
        planned.append({'metadata': meta, 'request': projected, 'provider_body': settings.body(projected, meta)})
    return planned


def construct(records, verifier):
    settings, limit = study_settings(INTERFACE_STUDY)
    preflight = verifier.preflight()
    prepared = []
    for record in records:
        task = RepairTask.from_dicts(record['public'], record['evaluator'])
        result = verifier.check(task.public['files'], task.public['entrypoint'], task.public['public_cases'])
        if public_feedback(result) != record['source_public_result']:
            raise ValueError('Source public feedback no longer reproduces')
        remove_claim(task.public['files'])  # Qualify both representations even for public passes.
        eligible = not result['passed']
        prepared.append({**record, 'task_hash': task.task_hash, 'initial_public_result': result,
            'eligible': eligible, 'eligibility_reason': 'public_failure' if eligible else 'public_pass_no_repair_trigger'})
    tasks = [RepairTask.from_dicts(r['public'], r['evaluator']) for r in prepared]
    planned = planned_requests(prepared)
    maximum = len(planned) * settings.reserve
    packet = {'schema_version': 1, 'study': INTERFACE_STUDY, 'status': 'draft_not_authorized',
        'api_calls': 0, 'model_results': False, 'live_calls_enabled': False,
        'monetary_authorization_usd': None, 'provider_settings': asdict(settings), 'design': design(),
        'source_archive_sha256': ARCHIVE_SHA, 'source_result': SOURCE,
        'prior_archive_sha256': PRIOR_ARCHIVE_SHA, 'prior_result': PRIOR,
        'source_provenance': provenance(tasks, INTERFACE_STUDY), 'verifier_preflight': preflight,
        'tasks': prepared, 'requests': planned, 'maximum_calls': len(planned),
        'maximum_new_reservations_usd': str(maximum), 'proposed_cap_usd': str(limit),
        'reservation_usd': str(settings.reserve), 'closed_pilot_commitment_usd': str(CARRY),
        'maximum_cumulative_commitment_usd': str(CARRY + maximum)}
    packet['packet_id'] = identity(packet)
    validate_packet(packet)
    return packet


def validate_packet(packet):
    settings, limit = study_settings(INTERFACE_STUDY)
    if (packet['study'] != INTERFACE_STUDY or packet['schema_version'] != 1
            or packet['packet_id'] != identity({k: v for k, v in packet.items() if k != 'packet_id'})
            or packet['status'] != 'draft_not_authorized' or packet['api_calls'] != 0
            or packet['model_results'] or packet['live_calls_enabled'] or packet['monetary_authorization_usd'] is not None):
        raise ValueError('Invalid offline interface packet')
    if (packet['design'] != design() or packet['provider_settings'] != asdict(settings)
            or packet['source_archive_sha256'] != ARCHIVE_SHA or packet['source_result'] != SOURCE
            or packet['prior_archive_sha256'] != PRIOR_ARCHIVE_SHA or packet['prior_result'] != PRIOR):
        raise ValueError('Interface design, provider or origin differs')
    records = packet['tasks']
    if len(records) != 12 or sum(r['eligible'] for r in records) != 8:
        raise ValueError('Expected twelve source candidates and eight public failures')
    for r in records:
        task = RepairTask.from_dicts(r['public'], r['evaluator'])
        eligible = not r['source_public_result']['passed']
        if (task.task_hash != r['task_hash'] or r['eligible'] != eligible
                or public_feedback(r['initial_public_result']) != r['source_public_result']
                or r['eligibility_reason'] != ('public_failure' if eligible else 'public_pass_no_repair_trigger')):
            raise ValueError('Changed task, initial feedback or eligibility')
        remove_claim(task.public['files'])
    planned = planned_requests(records)
    if packet['requests'] != planned or len(planned) != 128 or packet['maximum_calls'] != 128:
        raise ValueError('Exact factorial requests or ordering changed')
    if len({r['metadata']['attempt_id'] for r in planned}) != 128 or len({identity(r['provider_body']) for r in planned}) != 128:
        raise ValueError('Repeated request identity or provider body')
    maximum = len(planned) * settings.reserve
    if (packet['maximum_new_reservations_usd'] != str(maximum) or maximum > limit
            or packet['reservation_usd'] != str(settings.reserve) or packet['proposed_cap_usd'] != str(limit)
            or packet['closed_pilot_commitment_usd'] != str(CARRY)
            or packet['maximum_cumulative_commitment_usd'] != str(CARRY + maximum)):
        raise ValueError('Interface accounting projection differs')
    return {'maximum_calls': 128, 'retained_candidates': 12, 'eligible': 8}


def validate_origin(packet):
    original = source_records(Path(SOURCE))
    for source, record in zip(original, packet['tasks']):
        if any(record[k] != v for k, v in source.items()):
            raise ValueError('Checkpoint differs from immutable 27B source')
    old_ids, old_bodies = set(), set()
    for directory, expected in ((SOURCE, ARCHIVE_SHA), (PRIOR, PRIOR_ARCHIVE_SHA)):
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
