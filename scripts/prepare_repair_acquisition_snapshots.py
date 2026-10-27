"""Freeze public diagnostic observations and inert matched prompts, without APIs."""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import time

from vao.repair.acquisition_snapshot import acquire_once, projected, runtime
from vao.repair.diagnostics import observe
from vao.repair.environment import canonical, identity
from vao.repair.pool import read_pool, sha256
from vao.repair.records import save
from vao.repair.region_verifier import RegionRepairVerifier


def prepare(pools, output):
    candidates = [(pool, slug, task) for pool in pools for slug, task, _ in read_pool(pool)]
    if len({slug for _, slug, _ in candidates}) != len(candidates):
        raise ValueError('Repeated source slug across selected pools')
    before = runtime()
    pool_hashes = {str(pool): sha256(pool/'pool.json') for pool in pools}
    output.mkdir(parents=True, exist_ok=False)
    verifier = RegionRepairVerifier()
    preflight = verifier.preflight()
    rows = []
    for pool, slug, task in candidates:
        started = time.monotonic()
        target = output/slug
        target.mkdir()
        public = task.public
        state = observe(public, public['files'], verifier)
        save(target/'public.json', public)
        save(target/'observation.json', state)
        frozen = acquire_once(target/'acquisition', public, public['files'], state, verifier)
        requests = {arm: projected(target/'acquisition', public, public['files'], state, arm,
                                   expected_runtime=before) for arm in ('focused', 'focused_trace')}
        x, y = [json.loads(requests[arm]['messages'][1]['content']) for arm in ('focused', 'focused_trace')]
        y.pop('runtime_diagnostic')
        if x != y or requests['focused']['messages'][0] != requests['focused_trace']['messages'][0]:
            raise ValueError('Control/treatment core information differs')
        save(target/'requests.json', requests)
        sizes = {arm: sum(len(m['content'].encode()) for m in r['messages']) + 4096 for arm, r in requests.items()}
        row = {'id': slug, 'pool_sha256': pool_hashes[str(pool)], 'task_hash': task.task_hash,
               'snapshot_id': frozen['snapshot_id'], 'eligible_public_failure': not state['feedback']['passed'],
               'available': frozen['diagnostic']['available'],
               'shared_public_verification_seconds': state['verifier_seconds'],
               'shared_public_verification_calls': len(public['public_cases']),
               'diagnostic_seconds': frozen['diagnostic']['diagnostic_seconds'],
               'diagnostic_additional_executions': frozen['diagnostic']['additional_executions'],
               'preparation_seconds_including_io_and_projection': time.monotonic()-started,
               'messages_sha256': {arm: identity(r['messages']) for arm, r in requests.items()},
               'conservative_message_byte_plus_framing_allowance': sizes,
               'same_core_information': True, 'provider_call_enabled': False}
        save(target/'summary.json', row)
        rows.append(row)
        print(json.dumps({k: row[k] for k in ('id', 'eligible_public_failure', 'available', 'conservative_message_byte_plus_framing_allowance')}), flush=True)
    if runtime() != before or pool_hashes != {str(p): sha256(p/'pool.json') for p in pools}:
        raise ValueError('Acquisition runtime or pool changed during preparation')
    # Planning arithmetic only. No settings registered, allocation made or request sent.
    proposed_calls = 4 * sum(r['eligible_public_failure'] for r in rows)
    reserve = (Decimal('0.12')*40960 + Decimal('0.80')*8192)/1000000
    report = {'version': 'offline-acquisition-snapshot-preparation-v1', 'pools': pool_hashes,
              'runtime': before, 'preflight': preflight, 'api_calls': 0, 'live_calls_enabled': False,
              'candidates': len(rows), 'eligible': sum(r['eligible_public_failure'] for r in rows),
              'available': sum(r['available'] for r in rows), 'records': rows,
              'planning_only': {'calls_at_two_arms_two_draws': proposed_calls,
                               'input_reservation_ceiling': 40960, 'output_token_ceiling': 8192,
                               'price_ceilings_usd_per_million': ['0.12','0.80'],
                               'per_call_reserve_usd': str(reserve),
                               'maximum_request_reserves_usd': str(proposed_calls*reserve),
                               'messages_fit_conservative_ceiling': all(max(r['conservative_message_byte_plus_framing_allowance'].values())<=40960 for r in rows),
                               'not_a_token_count_or_live_price_quote': True},
              'limits': ['Original buggy artifacts after failing public tests, not model-generated failed repairs.',
                         'Published development data; no held-out inference or selector training.',
                         'Frozen actual trace bytes, not a claim that new execution reproduces intermediate values.',
                         'Paired preparation acquires treatment evidence offline; a deployed control would not acquire it.',
                         'Charge cached diagnostics per hypothetical deployment; no equal-total-budget claim.']}
    save(output/'summary.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pool', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.pool, args.output)
    print(json.dumps({k: result[k] for k in ('candidates','eligible','available','api_calls','planning_only')}, indent=2))


if __name__ == '__main__':
    main()
