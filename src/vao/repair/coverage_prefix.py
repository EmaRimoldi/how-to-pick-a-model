"""Six prospective initial repairs; natural checkpoints only, no recovery dispatch."""
import argparse
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import zipfile

from .contracts import COVERAGE_PREFIX_STUDY, provenance, public_feedback, study_settings
from .contrastive_study import HISTORY as PRIOR_HISTORY
from .diagnostics import observe, project, selected_failure
from .environment import RepairTask, identity
from .independent_information_study import archived_requests
from .pool import read_pool
from .records import save
from .verifier import RepairVerifier

BUNDLE = Path('experiments/python-repair/checkpoint-environment')
POOL = BUNDLE / 'development-broader'
POOL_SHA = 'a391412193749cf6b3c20472cdb703f27fc97c222edcea4b6a77165bfa8e006b'
PROTOCOL = BUNDLE / 'FAILURE-COVERAGE-PROTOCOL.md'
CARRY = Decimal('0.20640271')
HISTORY = {**PRIOR_HISTORY, str(BUNDLE / 'results/contrastive-calibration-20261026/evidence.zip'):
    '3205581a96e28f215cae5b23122cda831888c231ccd1a2b04b1eb69af61ac1a6'}


def design():
    return {'stage': 'initial_repair', 'tasks': 6, 'initial_draws': 1, 'seed': 43138,
        'wire_limit_bytes': 8388608, 'retries': 0, 'resume_allowed': False,
        'next_stage': {'arms': ['direct', 'first', 'all'], 'draws_per_arm': 3, 'seed': 43139,
            'maximum_calls': 54, 'minimum_bugs_with_multiple_public_failures': 3,
            'complete_prefix_required': True, 'allocation_cap_usd': '0.35',
            'primary': 'all_minus_first', 'required_secondary': 'all_minus_direct',
            'minimum_bugs_with_two_all_successes': 3, 'positive_in_every_draw_against_both_controls': True},
        'fit_selector': False, 'held_out_evaluation': False}


def planned_requests(records):
    settings, _ = study_settings(COVERAGE_PREFIX_STUDY)
    order = list(range(6)); random.Random(43138).shuffle(order)
    result = []
    for index in order:
        record = records[index]; p = record['public']
        request = project(p, p['files'], record['observation'], 'focused')
        request.update(mode='model_pilot', provider_call_enabled=True, remaining_budget_usd=str(settings.reserve))
        meta = {'study': COVERAGE_PREFIX_STUDY, 'trajectory': f'coverage-prefix-task-{index:03d}',
            'phase': 'initial_repair', 'depth': 1, 'contract': 'json_current',
            'task_index': index, 'task_hash': record['task_hash']}
        meta['attempt_id'] = identity(meta)
        result.append({'metadata': meta, 'request': request, 'provider_body': settings.body(request, meta)})
    return result


def construct(tasks, verifier):
    if len(tasks) != 6:
        raise ValueError('Retain all six predefined development tasks')
    settings, limit = study_settings(COVERAGE_PREFIX_STUDY)
    preflight = verifier.preflight()
    records = []
    for task in tasks:
        state = observe(task.public, task.public['files'], verifier)
        if state['feedback']['passed']:
            raise ValueError('Native buggy source no longer fails the public suite')
        records.append({'public': task.public, 'evaluator': json.loads(task.evaluator_json),
            'task_hash': task.task_hash, 'observation': state,
            'initial_public_result': {**state['feedback'], 'verifier_seconds': state['verifier_seconds']}})
    protocol = PROTOCOL.read_text()
    packet = {'schema_version': 1, 'study': COVERAGE_PREFIX_STUDY, 'status': 'draft_not_authorized',
        'api_calls': 0, 'model_results': False, 'live_calls_enabled': False, 'monetary_authorization_usd': None,
        'design': design(), 'provider_settings': asdict(settings), 'pool_sha256': POOL_SHA,
        'protocol_text': protocol, 'protocol_sha256': hashlib.sha256(protocol.encode()).hexdigest(),
        'source_provenance': provenance(tasks, COVERAGE_PREFIX_STUDY), 'verifier_preflight': preflight,
        'tasks': records, 'requests': planned_requests(records), 'maximum_calls': 6,
        'reservation_usd': str(settings.reserve), 'maximum_new_reservations_usd': str(6 * settings.reserve),
        'proposed_cap_usd': str(limit), 'closed_pilot_commitment_usd': str(CARRY),
        'maximum_cumulative_commitment_usd': str(CARRY + 6 * settings.reserve)}
    packet['packet_id'] = identity(packet)
    validate_packet(packet)
    return packet


def validate_packet(packet):
    settings, limit = study_settings(COVERAGE_PREFIX_STUDY)
    if (packet['packet_id'] != identity({k: v for k, v in packet.items() if k != 'packet_id'})
        or packet['study'] != COVERAGE_PREFIX_STUDY or packet['schema_version'] != 1
        or packet['status'] != 'draft_not_authorized' or packet['api_calls'] != 0
        or packet['model_results'] or packet['live_calls_enabled'] or packet['monetary_authorization_usd'] is not None):
        raise ValueError('Invalid offline initial-repair packet')
    if (packet['design'] != design() or packet['provider_settings'] != asdict(settings)
        or packet['pool_sha256'] != POOL_SHA or len(packet['tasks']) != 6
        or hashlib.sha256(packet['protocol_text'].encode()).hexdigest() != packet['protocol_sha256']):
        raise ValueError('Protocol, cohort or settings changed')
    tasks = []
    for r in packet['tasks']:
        t = RepairTask.from_dicts(r['public'], r['evaluator']); tasks.append(t)
        state = r['observation']
        if (t.task_hash != r['task_hash'] or state['feedback'] != public_feedback(r['initial_public_result'])
            or selected_failure(t.public, t.public['files'], state) is None or state['feedback']['passed']):
            raise ValueError('Native task or original public feedback differs')
    if (packet['source_provenance']['tasks'] != [t.task_hash for t in tasks]
        or packet['source_provenance']['design'] != design()
        or packet['requests'] != planned_requests(packet['tasks'])
        or len({identity(r['provider_body']) for r in packet['requests']}) != 6):
        raise ValueError('Exact initial-repair request schedule changed')
    expected = {'maximum_calls': 6, 'reservation_usd': str(settings.reserve),
        'maximum_new_reservations_usd': str(6 * settings.reserve), 'proposed_cap_usd': str(limit),
        'closed_pilot_commitment_usd': str(CARRY), 'maximum_cumulative_commitment_usd': str(CARRY + 6 * settings.reserve)}
    if any(packet[k] != v for k, v in expected.items()) or 6 * settings.reserve > limit:
        raise ValueError('Initial-repair allocation or historical carry changed')
    return {'maximum_calls': 6, 'recovery_calls_enabled': False}


def validate_origin(packet):
    if hashlib.sha256((POOL / 'pool.json').read_bytes()).hexdigest() != POOL_SHA:
        raise ValueError('Original development pool changed')
    tasks = [t for _, t, _ in read_pool(POOL)]
    if ([t.task_hash for t in tasks] != [r['task_hash'] for r in packet['tasks']]
        or PROTOCOL.read_text() != packet['protocol_text']):
        raise ValueError('Protocol or source tasks differ from reviewed files')
    old_ids, old_bodies = set(), set()
    for name, expected in HISTORY.items():
        path = Path(name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Historical evidence archive changed')
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                if member.startswith('collection/') and member.endswith('/manifest.json'):
                    for r in archived_requests(json.loads(z.read(member))):
                        old_ids.add(r['metadata']['attempt_id']); old_bodies.add(identity(r['provider_body']))
    if (old_ids & {r['metadata']['attempt_id'] for r in packet['requests']}
        or old_bodies & {identity(r['provider_body']) for r in packet['requests']}):
        raise ValueError('Initial request repeats a historical planned request')
    return {'historical_unique_bodies': len(old_bodies), 'overlap': 0, 'source_tasks': len(tasks)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    packet = construct([t for _, t, _ in read_pool(POOL)], RepairVerifier())
    checked = validate_origin(packet)
    save(args.output, packet)
    print(json.dumps({'packet_id': packet['packet_id'], 'maximum_calls': 6,
        'maximum_new_reservations_usd': packet['maximum_new_reservations_usd'], **checked}))


if __name__ == '__main__':
    main()
