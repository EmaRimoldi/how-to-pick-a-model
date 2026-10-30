"""Generate or check the numerical stdin pilot design, without any model call."""
import argparse
import base64
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import zipfile

from vao.repair.environment import canonical
from vao.repair.stdin_pilot import plan, parse_artifact

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'experiments/python-repair/checkpoint-environment'
BANK = BASE / 'results/stdin-ablation-preparation-20261030'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build_design():
    manifest = json.loads((BANK / 'manifest.json').read_text())
    if sha((BANK / 'evidence.zip').read_bytes()) != manifest['archive_sha256']:
        raise ValueError('Offline evidence changed')
    with zipfile.ZipFile(BANK / 'evidence.zip') as z:
        blobs = {n: z.read(n) for n in z.namelist()}
    if {n: sha(b) for n, b in blobs.items()} != manifest['members']:
        raise ValueError('Evidence members changed')
    preparation = json.loads(blobs['monitoring/plan.json'])
    rows = [json.loads(line) for line in blobs['monitoring/records.jsonl'].splitlines()]
    result = plan(preparation['tasks'], preparation['all_original_group_decisions'], manifest['archive_sha256'])
    result['protocol_sha256'] = sha((BASE / 'STDIN-PILOT-PROTOCOL.md').read_bytes())
    metadata_raw = (BANK / 'gemma-endpoints-observation.json').read_bytes()
    endpoint = next(e for e in json.loads(metadata_raw)['data']['endpoints'] if e['tag'] == 'parasail/bf16')
    if (endpoint['model_id'] != result['solver']['model'] or endpoint['provider_name'] != 'Parasail'
            or endpoint['quantization'].lower() != 'bf16'
            or Decimal(endpoint['pricing']['prompt']) != Decimal('0.00000004')
            or Decimal(endpoint['pricing']['completion']) != Decimal('0.00000005')):
        raise ValueError('Recorded endpoint does not support proposed pricing/identity')
    result['recorded_provider_metadata'] = {'sha256': sha(metadata_raw),
        'url': 'https://openrouter.ai/api/v1/models/google/gemma-3-4b-it/endpoints',
        'observed_utc': '2026-10-30T11:55:29.860702+00:00',
        'availability_probe': False, 'must_recheck_before_live_freeze': True}
    payloads = []
    for task, row in zip(preparation['tasks'], rows, strict=True):
        if task['problem_id'] != row['problem_id']:
            raise ValueError('Prepared group order changed')
        for arm, request in row['requests'].items():
            size = sum(len(m['content'].encode()) for m in request['messages'])
            payloads.append({'problem_id': task['problem_id'], 'arm': arm, 'utf8_content_bytes': size,
                             'byte_plus_framing_reservation': size + 4096,
                             'messages_sha256': sha(canonical(request['messages']).encode())})
    qualification = BASE / 'results/fixeval-source-qualification-20261030/evidence.zip'
    if sha(qualification.read_bytes()) != preparation['qualification_archive_sha256']:
        raise ValueError('Source qualification changed')
    with zipfile.ZipFile(qualification) as z:
        source_plan = json.loads(z.read('qualification-freeze.json'))
    sizes = []
    for group in source_plan['groups']:
        for pair in group['pairs']:
            for role, source in pair['sources'].items():
                if source is None:
                    continue
                artifact = {'main.py': base64.b64decode(source['source_b64'], validate=True).decode('utf-8')}
                wire = canonical(artifact)
                if parse_artifact(wire) != artifact:
                    raise ValueError('Declared output contract cannot preserve a selected original source')
                sizes.append({'problem_id': group['problem_id'], 'pair_index': pair['pair_index'], 'role': role,
                              'json_utf8_bytes': len(wire.encode())})
    result['capacity_observations'] = {
        'original_human_state_prompts': payloads, 'source_json_sizes': sizes,
        'maximum_observed_prompt_reservation': max(p['byte_plus_framing_reservation'] for p in payloads),
        'maximum_known_source_json_utf8_bytes': max(s['json_utf8_bytes'] for s in sizes),
        'gemma_tokenizer_measured': False, 'generated_checkpoint_capacity_guaranteed': False,
        'all_observed_human_prompts_fit_proposed_admission': all(p['byte_plus_framing_reservation'] <= result['solver']['input_reservation'] for p in payloads)}
    result['resolution_not_power_analysis'] = [
        {'eligible_groups': m, 'one_draw_one_checkpoint_rate_step': 1/m,
         'aggregate_one_cell_rate_step': 1/(3*m), 'one_checkpoint_all_draws_rate_step': 1/m,
         'minimum_total_net_repairs_for_ten_points': math.ceil(3*m/10)} for m in range(6, 12)]
    result['launch_requirements_still_open'] = [
        'Tested whole-program collector binding dynamic generated checkpoints and public-only requests.',
        'Complete receipts, charge reservations and independent raw-response/test/projection audit.',
        'Source commit, exact runtime, provider metadata and single-use declared allocation freeze.',
        'No live call is authorized by this numerical-design artifact alone.']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BANK / 'pilot-design.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(); result = build_design()
    if args.check:
        if json.loads(args.output.read_text()) != result:
            raise ValueError('Recorded pilot design differs')
    else:
        with args.output.open('x') as f:
            f.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': len(result['roster']), 'maximum_calls': len(result['slots']),
                      'maximum_reservations_usd': result['budget']['maximum_all_reservations_usd'],
                      'maximum_observed_prompt_admission': result['capacity_observations']['maximum_observed_prompt_reservation'],
                      'maximum_known_source_json_utf8_bytes': result['capacity_observations']['maximum_known_source_json_utf8_bytes'],
                      'provider_call_enabled': False, 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
