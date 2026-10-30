# /// script
# requires-python = ">=3.10"
# dependencies = ["tokenizers==0.22.2", "jinja2==3.1.6", "transformers==4.57.1"]
# ///
"""Re-tokenize six development artifacts and three saved prompts, entirely offline.

No model, candidate code, evaluator or network request is executed. The first
uv invocation may install the declared tools and their dependencies.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'src'))

from vao.repair.environment import canonical
from vao.repair.package_environment import PackageTask
from vao.repair.package_spectra import triplet
from vao.repair.pool import read_pool


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def audit_source_feasibility():
    manifest = json.loads((HERE / 'source-feasibility-manifest.json').read_text())
    path = HERE / 'source-feasibility.zip'
    if sha(path.read_bytes()) != manifest['archive_sha256']:
        raise ValueError('Source feasibility archive changed')
    with zipfile.ZipFile(path) as archive:
        if sorted(archive.namelist()) != sorted(manifest['entries']):
            raise ValueError('Source feasibility inventory changed')
        blobs = {name: archive.read(name) for name in manifest['entries']}
    if any(sha(blobs[name]) != digest for name, digest in manifest['entries'].items()):
        raise ValueError('Source feasibility record changed')
    plan = json.loads(blobs['plan.json'])
    roots = {r['repo']: r for r in json.loads(blobs['root-metadata.json'])}
    documents = json.loads(blobs['document-manifest.json'])
    if list(roots) != plan['repositories'] or len(documents) != 4:
        raise ValueError('Documentation source selection changed')
    for row in documents:
        raw = blobs[row['local']]
        root = roots[row['repo']]
        entry = next(e for e in root['root_entries'] if e['path'] == row['path'])
        git_blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if (row['path'] not in {'README.md', 'LICENSE'} or row['revision'] != root['revision']
                or git_blob != row['git_blob'] or git_blob != entry['sha']
                or sha(raw) != row['sha256'] or len(raw) != row['bytes']):
            raise ValueError('Documentation differs from pinned repository bytes')
    observations = json.loads(blobs['access-observations.json'])['observations']
    if len(observations) != 4 or any(r['method'] != 'HEAD' or r['data_archive_downloaded'] for r in observations):
        raise ValueError('Expected only the four recorded header checks')
    return {'verified_pinned_documents': 4, 'header_observations_retained': 4,
            'dataset_archive_contents_verified': False, 'new_model_calls': 0}


def measure():
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    from tokenizers import Tokenizer
    from transformers import AutoTokenizer

    source = json.loads((HERE / 'tokenizer-manifest.json').read_text())
    with zipfile.ZipFile(HERE / 'tokenizer-assets.zip') as archive:
        if sorted(archive.namelist()) != sorted(source['files']):
            raise ValueError('Tokenizer asset inventory changed')
        blobs = {name: archive.read(name) for name in source['files']}
    for name, info in source['files'].items():
        if sha(blobs[name]) != info['sha256'] or len(blobs[name]) != info['bytes']:
            raise ValueError('Pinned tokenizer bytes differ: ' + name)
    tokenizer = Tokenizer.from_str(blobs['tokenizer.json'].decode())
    with tempfile.TemporaryDirectory(prefix='local-token-capacity-') as temporary:
        for name, raw in blobs.items():
            Path(temporary, name).write_bytes(raw)
        official = AutoTokenizer.from_pretrained(temporary, local_files_only=True, trust_remote_code=False)
    config = json.loads(blobs['tokenizer_config.json'])
    environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
    separate = environment.from_string(blobs['chat_template.jinja'].decode())
    embedded = environment.from_string(config['chat_template'])

    def count(text):
        ids = tokenizer.encode(text, add_special_tokens=False).ids
        if official.encode(text, add_special_tokens=False) != ids:
            raise ValueError('Official tokenizer wrapper and raw backend disagree')
        if tokenizer.decode(ids, skip_special_tokens=False) != text:
            raise ValueError('Tokenization did not preserve the complete input')
        return {'utf8_bytes': len(text.encode()), 'text_sha256': sha(text.encode()),
                'tokens': len(ids), 'token_ids_sha256': sha(canonical(ids).encode())}

    eos = count(config['eos_token'])
    if eos['tokens'] != 1:
        raise ValueError('Unexpected end-of-turn token count')
    base = HERE.parent.parent
    bounded = base / 'development-ablation-components'
    package = base / 'development-package-black13'
    files = [bounded / 'pool.json', bounded / 'qualification.json',
             package / 'task.json', package / 'evaluator.json',
             package / 'reference.json', package / 'qualification.json']
    tasks = [(slug, task, reference) for slug, task, reference in read_pool(bounded)]
    tasks.append(('black-13', PackageTask.load(package),
                  json.loads((package / 'reference.json').read_text())))
    rows = []
    for slug, task, reference in tasks:
        task.validate_artifact(reference)
        variants = {}
        for name, sources in [('initial', task.public['files']), ('reference', reference)]:
            compact = count(canonical(sources))
            pretty = count(json.dumps(sources, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False))
            variants[name] = {'canonical_json': compact, 'indented_json': pretty,
                'max_measured_tokens_with_eos': max(compact['tokens'], pretty['tokens']) + 1}
        need = max(v['max_measured_tokens_with_eos'] for v in variants.values())
        rows.append({'id': slug, 'task_hash': task.task_hash, 'variants': variants,
                     'max_measured_tokens_with_eos': need,
                     'measured_variants_fit_output_caps': {str(cap): need <= cap for cap in (4096, 8192, 16384)}})

    saved = json.loads((package / 'qualification.json').read_text())
    projected = triplet(tasks[-1][1].public, saved['stored'], saved['acquisition'])
    if projected != saved['inert_projections']:
        raise ValueError('Package projections differ from published observations')
    prompts = {}
    for arm, request in projected.items():
        if request['provider_call_enabled'] is not False:
            raise ValueError('Expected inert requests')
        messages = request['messages']
        if [m['role'] for m in messages] != ['system', 'user']:
            raise ValueError('Unexpected message roles')
        a = separate.render(messages=messages, add_generation_prompt=True)
        b = embedded.render(messages=messages, add_generation_prompt=True)
        explicit = ''.join('<|im_start|>' + m['role'] + '\n' + m['content'] + '<|im_end|>\n'
                           for m in messages) + '<|im_start|>assistant\n'
        if a != b or a != explicit:
            raise ValueError('Two pinned templates and explicit no-tool framing disagree')
        if (official.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) != a
                or official.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
                != tokenizer.encode(a, add_special_tokens=False).ids):
            raise ValueError('Official chat-template rendering or tokenization differs')
        prompts[arm] = {'rendered': count(a),
                        'messages_sha256': sha(canonical(messages).encode()),
                        'fits_historical_input_reservation_32768': count(a)['tokens'] <= 32768}

    old = json.loads((HERE.parent / 'spectrum-ablation-preparation-20261030/planning.json').read_text())
    prices = old['historical_price_assumption_not_live_quote']
    per_call = (Decimal(prices['input_per_million']) * 32768 +
                Decimal(prices['output_per_million']) * 8192) / 1000000
    remaining = Decimal(old['remaining_authorized_usd'])
    return {'kind': 'local_token_capacity_audit_not_provider_receipt_or_model_trial',
            'model': source['model'], 'tokenizer_revision': source['revision'],
            'runtime': {n: importlib.metadata.version(n) for n in ('tokenizers', 'jinja2', 'transformers')},
            'tokenizer_source': source,
            'source_feasibility_audit': audit_source_feasibility(),
            'inputs_sha256': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in files},
            'components': rows, 'black13_inert_prompts': prompts,
            'prompt_audit_scope': 'Only the published Black/13 F/N/S triplet, not all future prompts or generated checkpoints',
            'fits_4096_all_measured_artifacts': all(r['measured_variants_fit_output_caps']['4096'] for r in rows),
            'fits_8192_all_measured_artifacts': all(r['measured_variants_fit_output_caps']['8192'] for r in rows),
            'candidate_output_limit_not_frozen': 8192,
            'maximum_measured_prompt_plus_candidate_output_tokens': max(v['rendered']['tokens'] for v in prompts.values()) + 8192,
            'hypothetical_reservations_not_authorized_allocation': {
                'prices_per_million_usd_not_live_quote': {k: prices[k] for k in ('input_per_million', 'output_per_million')},
                'input_reservation_tokens': 32768, 'output_reservation_tokens': 8192,
                'per_call_usd': str(per_call), 'calls_per_component_if_all_trigger': 10,
                'definition': 'One checkpoint attempt plus three arms times three draws; not a frozen study',
                'six_component_calls': 60, 'six_component_usd': str(per_call * 60),
                'prior_34_candidate_design_calls': 340, 'prior_34_candidate_design_usd': str(per_call * 340),
                'remaining_cumulative_authorization_usd': str(remaining),
                'six_component_design_fits_remaining_ceiling': per_call * 60 <= remaining},
            'new_model_calls': 0, 'new_upstream_executions': 0, 'new_api_spend_usd': '0',
            'live_collection_enabled': False, 'model_cohort_frozen': False,
            'limits': ['Measured reference length is not a lower bound on all correct solutions.',
                       'Two serializations do not bound every model response or prove format compliance.',
                       'Local tokenizer/template counts are not a provider billing receipt.',
                       'Identical output ceilings do not equal identical total resources.',
                       'Six exposed components in two projects are not the independent evaluation cohort.',
                       'Original buggy sources are not model-generated failed repair checkpoints.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Write a NEW measurement; default compares the published report')
    args = parser.parse_args()
    result = measure()
    if args.output:
        with args.output.open('x') as stream:
            stream.write(json.dumps(result, indent=2) + '\n')
    elif json.loads((HERE / 'analysis.json').read_text()) != result:
        raise ValueError('Recomputed token counts or resource arithmetic differ')
    print(json.dumps({'components': len(result['components']),
        'black13_reference_canonical_tokens': result['components'][-1]['variants']['reference']['canonical_json']['tokens'],
        'fits_4096': result['fits_4096_all_measured_artifacts'],
        'fits_8192': result['fits_8192_all_measured_artifacts'],
        'inert_prompts': len(result['black13_inert_prompts']), 'model_calls': 0}, indent=2))


if __name__ == '__main__':
    main()
