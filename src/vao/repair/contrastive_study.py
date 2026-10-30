"""Fresh three-arm public-contrast calibration, separately frozen and funded."""
from dataclasses import asdict
from decimal import Decimal
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import random
import zipfile

from .contracts import CONTRASTIVE_TRACE_STUDY, provenance, public_feedback, study_settings
from .contrastive_diagnostics import acquire, project
from .diagnostics import binding, observe, project as focused_project, selected_failure
from .diagnostic_study import SOURCE, ARCHIVE_SHA, source_records, without_times
from .environment import RepairTask, canonical, identity
from .independent_information_study import HISTORY as OLD_HISTORY, archived_requests
from .independent_streaming import POLICY
from .records import save
from .verifier import RepairVerifier

ARMS = ('focused', 'single_trace', 'paired_trace')
DRAWS, SEED = 3, 43137
CARRY = Decimal('0.16495655')
PRIOR = 'experiments/python-repair/checkpoint-environment/results/information-independent-20261026'
PRIOR_ARCHIVE_SHA = '0c84d4fd10ce06b971b75340e7cb522c77410d278f439fcf1078680bb876377b'
HISTORY = {**OLD_HISTORY, PRIOR + '/evidence.zip': PRIOR_ARCHIVE_SHA}


def design():
    return {'arms': list(ARMS), 'draws_per_arm': DRAWS, 'seed': SEED,
        'primary': 'paired_trace_minus_focused', 'source_contract': 'json_current',
        'secondary': ['paired_trace_minus_single_trace', 'single_trace_minus_focused'],
        'screening': {'minimum_bugs_with_two_paired_successes': 3, 'minimum_net_paired_successes': 4,
            'positive_in_each_of_three_draws': True, 'all_binary_completions_must_pass': True},
        'fit_selector': False, 'historical_controls': False, 'exposed_development_checkpoints': True,
        'wire_limit_bytes': 8388608, 'transport_missing_policy': copy.deepcopy(POLICY),
        'public_pair_selection': 'same_shape_then_recursive_mean_normalized_leaf_levenshtein_256_v1',
        'trace_representation': 'lossless_adjacent_local_delta_if_smaller_else_raw_v1'}


def schedule(records):
    groups = [(i, d) for d in range(DRAWS) for i, r in enumerate(records) if r['eligible']]
    random.Random(SEED).shuffle(groups)
    orders = list(itertools.permutations(ARMS))
    random.Random(SEED + 1).shuffle(orders)
    return [(i, d, arm) for pos, (i, d) in enumerate(groups) for arm in orders[pos % 6]]


def planned_requests(records):
    settings, _ = study_settings(CONTRASTIVE_TRACE_STUDY)
    requests = []
    for index, draw, arm in schedule(records):
        record = records[index]
        public, state = record['public'], record['observation']
        request = (focused_project(public, public['files'], state, 'focused') if arm == 'focused'
            else project(public, public['files'], state, record['diagnostics'][arm]))
        request.update(mode='model_pilot', provider_call_enabled=True, remaining_budget_usd=str(settings.reserve))
        meta = {'study': CONTRASTIVE_TRACE_STUDY,
            'trajectory': f'{CONTRASTIVE_TRACE_STUDY}-task-{index:03d}-draw-{draw}',
            'phase': 'diagnostic_probe', 'depth': 1, 'draw': draw, 'arm': arm, 'contract': 'json_current',
            'task_index': index, 'task_hash': record['task_hash'], 'source_attempt_id': record['source_attempt_id']}
        meta['attempt_id'] = identity(meta)
        requests.append({'metadata': meta, 'request': request, 'provider_body': settings.body(request, meta)})
    return requests


def construct(records, verifier):
    settings, limit = study_settings(CONTRASTIVE_TRACE_STUDY)
    preflight = verifier.preflight()
    prepared = []
    for source in records:
        task = RepairTask.from_dicts(source['public'], source['evaluator'])
        state = observe(task.public, task.public['files'], verifier)
        if state['feedback'] != source['source_public_result']:
            raise ValueError('Original public feedback does not reproduce')
        diagnostics = {arm: acquire(task.public, task.public['files'], state, verifier, paired=arm == 'paired_trace')
            for arm in ('single_trace', 'paired_trace')}
        eligible = not state['feedback']['passed']
        prepared.append({**source, 'task_hash': task.task_hash, 'observation': state,
            'initial_public_result': {**state['feedback'], 'verifier_seconds': state['verifier_seconds']},
            'diagnostics': diagnostics, 'eligible': eligible,
            'eligibility_reason': 'public_failure' if eligible else 'public_pass_no_repair_trigger'})
    requests = planned_requests(prepared)
    maximum = settings.reserve * len(requests)
    if maximum > limit:
        raise ValueError('Allocation cannot cover every request reservation')
    packet = {'schema_version': 1, 'study': CONTRASTIVE_TRACE_STUDY, 'status': 'draft_not_authorized',
        'api_calls': 0, 'model_results': False, 'live_calls_enabled': False, 'monetary_authorization_usd': None,
        'provider_settings': asdict(settings), 'design': design(), 'source_archive_sha256': ARCHIVE_SHA,
        'source_result': SOURCE, 'prior_result': PRIOR, 'prior_archive_sha256': PRIOR_ARCHIVE_SHA,
        'source_provenance': provenance([RepairTask.from_dicts(r['public'], r['evaluator']) for r in prepared], CONTRASTIVE_TRACE_STUDY),
        'verifier_preflight': preflight, 'tasks': prepared, 'requests': requests, 'maximum_calls': len(requests),
        'maximum_new_reservations_usd': str(maximum), 'proposed_cap_usd': str(limit),
        'reservation_usd': str(settings.reserve), 'closed_pilot_commitment_usd': str(CARRY),
        'maximum_cumulative_commitment_usd': str(CARRY + maximum)}
    packet['packet_id'] = identity(packet)
    validate_packet(packet)
    return packet


def validate_packet(packet):
    settings, limit = study_settings(CONTRASTIVE_TRACE_STUDY)
    if (packet['study'] != CONTRASTIVE_TRACE_STUDY or packet['schema_version'] != 1
        or packet['packet_id'] != identity({k: v for k, v in packet.items() if k != 'packet_id'})
        or packet['status'] != 'draft_not_authorized' or packet['api_calls'] != 0 or packet['model_results']
        or packet['live_calls_enabled'] or packet['monetary_authorization_usd'] is not None):
        raise ValueError('Invalid offline contrastive packet')
    if (packet['design'] != design() or packet['provider_settings'] != asdict(settings)
        or packet['source_archive_sha256'] != ARCHIVE_SHA or packet['source_result'] != SOURCE
        or packet['prior_result'] != PRIOR or packet['prior_archive_sha256'] != PRIOR_ARCHIVE_SHA):
        raise ValueError('Design/settings/provenance changed')
    records = packet['tasks']
    if len(records) != 12 or sum(r['eligible'] for r in records) != 8:
        raise ValueError('Retain twelve sources with eight public failures')
    for record in records:
        task = RepairTask.from_dicts(record['public'], record['evaluator'])
        state = record['observation']
        eligible = selected_failure(task.public, task.public['files'], state) is not None
        if (record['task_hash'] != task.task_hash or record['eligible'] != eligible
            or state['feedback']['passed'] == eligible or state['feedback'] != record['source_public_result']
            or state['feedback'] != public_feedback(record['initial_public_result'])
            or record['eligibility_reason'] != ('public_failure' if eligible else 'public_pass_no_repair_trigger')):
            raise ValueError('Task, eligibility or public feedback changed')
        if set(record['diagnostics']) != {'single_trace', 'paired_trace'}:
            raise ValueError('Missing diagnostic control')
        for arm, d in record['diagnostics'].items():
            if (d['binding'] != binding(task.public, task.public['files'])
                or d['paired'] != (arm == 'paired_trace') or d['version'] != 'contrastive-public-trace-v2'):
                raise ValueError('Diagnostic binding or version changed')
    expected = planned_requests(records)
    if packet['requests'] != expected or len(expected) != 72 or packet['maximum_calls'] != 72:
        raise ValueError('Exact 72-cell schedule/projection changed')
    if len({r['metadata']['attempt_id'] for r in expected}) != 72 or len({identity(r['provider_body']) for r in expected}) != 72:
        raise ValueError('Repeated request')
    maximum = 72 * settings.reserve
    if (packet['maximum_new_reservations_usd'] != str(maximum) or packet['reservation_usd'] != str(settings.reserve)
        or packet['proposed_cap_usd'] != str(limit) or maximum > limit
        or packet['closed_pilot_commitment_usd'] != str(CARRY)
        or packet['maximum_cumulative_commitment_usd'] != str(CARRY + maximum)):
        raise ValueError('Financial projection changed')
    return {'maximum_calls': 72, 'retained_candidates': 12, 'eligible': 8}


def validate_origin(packet):
    originals = source_records()
    if len(originals) != len(packet['tasks']) or any(
        any(record.get(k) != v for k, v in original.items()) for original, record in zip(originals, packet['tasks'])):
        raise ValueError('Source candidates differ from the original bank')
    old_ids, old_bodies = set(), set()
    for name, expected in HISTORY.items():
        path = Path(name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Historical archive hash differs')
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                if member.startswith('collection/') and member.endswith('/manifest.json'):
                    for old in archived_requests(json.loads(z.read(member))):
                        old_ids.add(old['metadata']['attempt_id'])
                        old_bodies.add(identity(old['provider_body']))
    if old_ids & {r['metadata']['attempt_id'] for r in packet['requests']} or old_bodies & {identity(r['provider_body']) for r in packet['requests']}:
        raise ValueError('Historical planned request repeated')
    return {'historical_archives': len(HISTORY), 'historical_unique_bodies': len(old_bodies),
        'historical_overlap': 0, 'source_candidates_verified': len(originals)}


def validate_diagnostics(packet, verifier):
    for record in packet['tasks']:
        p, state = record['public'], record['observation']
        for arm, stored in record['diagnostics'].items():
            actual = acquire(p, p['files'], state, verifier, paired=arm == 'paired_trace')
            if canonical(without_times(actual)) != canonical(without_times(stored)):
                raise ValueError('Frozen public contrast does not reproduce')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    packet = construct(source_records(), RepairVerifier())
    origin = validate_origin(packet)
    save(args.output, packet)
    print(json.dumps({k: packet[k] for k in ('packet_id', 'maximum_calls', 'maximum_new_reservations_usd', 'proposed_cap_usd')}))
    print(json.dumps(origin))


if __name__ == '__main__':
    main()
