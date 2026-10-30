"""Qualify inert F/N/S projections on exposed checkpoints; never collect models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from vao.repair.environment import identity, canonical
from vao.repair.spectrum_ablation import triplet

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'experiments/python-repair/checkpoint-environment/results/spectrum-screen-20261030'
EXPECTED = 'e855df951a5400104de294b083d6779f1e5ca014dac1a7cb854829d187a9650d'


def prepare():
    archive = SOURCE / 'evidence.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('Historical engineering input archive changed')
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('collection/manifest.json'))
    old = manifest['freeze']['plan']
    rows = []
    for record in old['records']:
        # An explicit boundary: no evaluator, historical arm outcome, cached
        # diagnostic ranking, source fix or source identifier enters the builder.
        requests = triplet(record['public'], record['stored'], record['acquisition'])
        payloads = {a: json.loads(r['messages'][1]['content']) for a, r in requests.items()}
        rows.append({'source_id': record['id'], 'requests': requests,
            'request_hashes': {a: identity(r) for a, r in requests.items()},
            'message_utf8_bytes': {a: len(canonical(r['messages']).encode()) for a, r in requests.items()},
            'location_count': len(payloads['scored']['source_excerpts']['locations'] or []),
            'acquisition_available': payloads['scored']['source_excerpts']['available'],
            'acquisition_executions_per_neutral_or_scored_action': record['acquisition']['additional_executions']})
    if len(rows) != 8 or len(old['candidate_inventory']) != 12:
        raise ValueError('Engineering bank differs')
    return {'schema_version': 1, 'kind': 'offline_projection_qualification_not_new_task_experiment',
        'source_archive_sha256': EXPECTED, 'candidate_inventory': old['candidate_inventory'],
        'source_checkpoints': len(rows), 'inert_requests': 3 * len(rows), 'rows': rows,
        'api_calls': 0, 'candidate_executions': 0, 'historical_outcomes_reused_as_controls': False,
        'new_bug_manifest_frozen': False, 'live_collection_enabled': False,
        'limits': ['Previously exposed inputs test software invariants only, not the new research hypothesis.',
                   'No tokenizer/padding assumption: UTF-8 bytes are not token counts.',
                   'Both neutral and scored actions require coverage; missing whole acquisitions are retained.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = prepare()
    if args.check:
        if json.loads(args.output.read_text()) != result:
            raise ValueError('Saved projection qualification differs')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as handle:
            handle.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('source_checkpoints', 'inert_requests', 'api_calls',
        'candidate_executions', 'new_bug_manifest_frozen', 'live_collection_enabled')}, indent=2))


if __name__ == '__main__':
    main()
