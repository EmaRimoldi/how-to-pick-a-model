"""Reproduce source-screen provenance and planning arithmetic without network/model calls."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
from statistics import NormalDist
import zipfile

from vao.repair.exposure import normalize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def derive():
    plan_bytes = (HERE / 'source-plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    with zipfile.ZipFile(HERE / 'catalog-inputs.zip') as z:
        raw_tree, raw_old = z.read('tree.json'), z.read('prior-exposure-registry.json')
    if sha(raw_tree) != plan['catalog_sha256'] or sha(raw_old) != plan['prior_exposure_sha256']:
        raise ValueError('Pre-screen catalog or exposure boundary differs')
    tree, old = json.loads(raw_tree), json.loads(raw_old)
    if tree.get('truncated'):
        raise ValueError('Catalog was incomplete')
    entries = {e['path']: e for e in tree['tree']}
    rows = []
    for path, entry in sorted(entries.items()):
        if path.startswith('projects/') and path.endswith('/bug.info'):
            parts = path.split('/')
            rows.append({'id': normalize(parts[1] + '/' + parts[3]), 'bug_info': path,
                'bug_info_blob': entry['sha'], 'patch': path.rsplit('/', 1)[0] + '/bug_patch.txt',
                'project': parts[1]})
    if len(rows) != len({r['id'] for r in rows}) or len(rows) != 501:
        raise ValueError('Catalog IDs are duplicate or different')
    candidates = [r for r in rows if r['id'] not in old['known_exposed_ids']
                  and r['id'].split('/')[0] in old['known_exposed_projects']]
    candidates.sort(key=lambda row: sha(('spectrum-ablation-source-screen-v1:' + row['id']).encode()))
    if candidates != plan['ordered_candidates'] or len(candidates) != plan['candidate_count']:
        raise ValueError('Prospective candidate queue differs')
    inspections, summaries = [], []
    with zipfile.ZipFile(HERE / 'source-screen.zip') as z:
        manifest = json.loads(z.read('manifest.json'))
        if manifest['source_plan_sha256'] != sha(plan_bytes):
            raise ValueError('Downloads not bound to prospective queue')
        expected_paths = {path for r in candidates for path in
            (r['bug_info'], r['patch'], 'projects/' + r['project'] + '/project.info')}
        records = {r['path']: r for r in manifest['files']}
        if len(records) != len(manifest['files']) or set(records) != expected_paths:
            raise ValueError('Missing or extra source download')
        for path, row in records.items():
            data = z.read(path)
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if (row['status'] != 'downloaded_inert' or sha(data) != row['sha256']
                    or blob != row['git_blob'] or blob != entries[path]['sha']):
                raise ValueError('Pinned source bytes differ')
        for row in candidates:
            info = z.read(row['bug_info']).decode()
            patch = z.read(row['patch']).decode()
            metadata = dict(re.findall(r'^([A-Za-z_]+)="([^"]*)"', info, re.M))
            paths = re.findall(r'^diff --git a/(.+?) b/(.+)$', patch, re.M)
            summaries.append({'id': row['id'], 'buggy_commit': metadata['buggy_commit_id'],
                'fixed_commit': metadata['fixed_commit_id'], 'test_paths': metadata['test_file'].split(';'),
                'changed_paths': [{'before': a, 'after': b} for a, b in paths],
                'patch_lines': len(patch.splitlines()),
                'qualification': 'pending_source_environment_and_function_family_review'})
            inspections.append({'id': row['id'], 'level': 'patch_inspection',
                'bug_info_sha256': records[row['bug_info']]['sha256'],
                'patch_sha256': records[row['patch']]['sha256']})
    screen = {'kind': 'development_exposure_after_prospective_source_screen',
        'source_plan_sha256': sha(plan_bytes), 'source_archive_sha256': sha((HERE / 'source-screen.zip').read_bytes()),
        'benchmark_revision': plan['benchmark_revision'], 'inspections': inspections,
        'summaries': summaries, 'qualified_tasks': 0, 'api_model_calls': 0,
        'limits': ['Metadata and patch headers are not executable task qualification.',
            'These IDs are now development-exposed; all aliases and variants must stay out of final evaluation.',
            'Same-project or same-function candidates need clustering; 34 IDs do not prove 34 independent units.']}
    planning_rows = []
    z = NormalDist().inv_cdf(.975) + NormalDist().inv_cdf(.8)
    for effect in (.05, .10, .15):
        for discordance in (.2, .4, .8):
            for correlation in (0, .5, 1):
                draws = 3
                variance = (discordance - effect ** 2) * (1 + (draws - 1) * correlation) / draws
                planning_rows.append({'effect': effect, 'discordance': discordance,
                    'within_bug_correlation': correlation, 'draws_per_arm': draws,
                    'approximate_independent_bugs': math.ceil(z * z * variance / effect ** 2)})
    per_request = Decimal('32768') * Decimal('.12') / Decimal(1000000) + Decimal('4096') * Decimal('.80') / Decimal(1000000)
    carry, cap = Decimal('.25463059'), Decimal('.60')
    worst_calls = len(candidates) * (1 + 3 * 3)
    planning = {'kind': 'sensitivity_planning_not_sample_size_freeze',
        'design': 'One initial generation plus at most three arms x three repair draws per candidate.',
        'approximation': 'Normal approximation: n = ceil((z_0.975 + z_0.80)^2 * (q-delta^2) * (1+2*rho) / (3*delta^2)).',
        'assumptions': ['Hypothetical paired Bernoulli discordance q, common marginal effect delta and exchangeable within-bug correlation rho.',
            'Independent bug units; no allowance for project/function clustering, random trigger yield, verifier errors or multiplicity.',
            'Not fitted to previous arm outcomes. Neither 80% power nor nominal coverage is established for this future population.',
            'No numeric effect threshold, inference procedure or final cohort is frozen by this sensitivity table.'],
        'planning_rows': planning_rows, 'current_catalog_candidates': len(candidates),
        'candidate_project_counts': dict(sorted(Counter(r['id'].split('/')[0] for r in candidates).items())),
        'remaining_unopened_project_ids_in_catalog': sum(r['id'].split('/')[0] not in old['known_exposed_projects'] for r in rows),
        'maximum_calls_if_all_qualify_and_trigger': worst_calls,
        'historical_price_assumption_not_live_quote': {'input_per_million': '.12', 'output_per_million': '.80',
            'input_reservation': 32768, 'output_limit': 4096},
        'maximum_reservation_per_call_usd': str(per_request),
        'maximum_reservation_for_candidate_design_usd': str(per_request * worst_calls),
        'current_cumulative_commitment_usd': str(carry), 'current_cumulative_cap_usd': str(cap),
        'remaining_authorized_usd': str(cap - carry),
        'full_candidate_design_fits_current_ceiling': carry + per_request * worst_calls <= cap,
        'live_collection_enabled': False, 'api_model_calls': 0}
    return {'source-screen.json': screen, 'planning.json': planning}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    data = derive()
    for name, content in data.items():
        path = HERE / name
        if args.write:
            path.write_text(json.dumps(content, indent=2) + '\n')
        elif json.loads(path.read_text()) != content:
            raise ValueError('Saved derived preparation differs: ' + name)
    spec = importlib.util.spec_from_file_location('prepare_ablation', ROOT / 'scripts/prepare_spectrum_ablation.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    if json.loads((HERE / 'projections.json').read_text()) != module.prepare():
        raise ValueError('Inert triplet qualification differs')
    print(json.dumps({'candidate_ids_screened': len(data['source-screen.json']['inspections']),
        'qualified_tasks_at_initial_metadata_screen': 0, 'historical_engineering_checkpoints': 8,
        'inert_projections_verified': 24, 'api_model_calls': 0,
        'full_candidate_design_fits_current_ceiling': data['planning.json']['full_candidate_design_fits_current_ceiling']}, indent=2))


if __name__ == '__main__':
    main()
