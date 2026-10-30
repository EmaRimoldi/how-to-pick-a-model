"""Audit five bounded source components; execute candidates only with --sandbox."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from vao.repair.environment import audit_run, canonical
from vao.repair.pool import audit_sources, qualify_pool, read_pool

HERE = Path(__file__).resolve().parent
PREPARATION = HERE.parent / 'results/spectrum-ablation-preparation-20261030'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unpack(path, target):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive member')
        for name in names:
            dest = (target / name).resolve()
            if not dest.is_relative_to(target.resolve()):
                raise ValueError('Archive path escapes temporary directory')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.read(name))


def audit():
    manifest = json.loads((HERE / 'evidence-manifest.json').read_text())
    for name, digest in manifest.items():
        if sha(HERE / name) != digest:
            raise ValueError('Evidence hash differs: ' + name)
    plan = json.loads((HERE / 'qualification-plan.json').read_text())
    if sha(HERE / 'pool.json') != plan['pool_sha256']:
        raise ValueError('Pool differs from pre-execution plan')
    if sha(HERE / 'upstream-sources.zip') != plan['upstream_archive_sha256']:
        raise ValueError('Upstream bytes differ from pre-execution plan')
    review = json.loads((PREPARATION / 'feasibility-review.json').read_text())
    if sha(PREPARATION / 'feasibility-review.json') != plan['source_review_sha256']:
        raise ValueError('Source review changed after qualification')
    if (sha(PREPARATION / 'source-plan.json') != review['source_plan_sha256']
            or sha(PREPARATION / 'source-screen.json') != review['source_screen_sha256']):
        raise ValueError('Source review is not bound to the prospective queue')
    queue = json.loads((PREPARATION / 'source-plan.json').read_text())['ordered_candidates']
    if [r['id'] for r in review['decisions']] != [r['id'] for r in queue]:
        raise ValueError('Reviewed candidates missing or reordered')
    expected = [r['id'] for r in review['decisions'] if r['route'] == 'bounded_component_candidate']
    if expected != plan['candidate_order']:
        raise ValueError('Qualified component selection differs from source review')
    pool = json.loads((HERE / 'pool.json').read_text())
    if [r['provenance']['benchmark_id'] for r in pool['tasks']] != expected:
        raise ValueError('Pool order differs from prospective component plan')
    if any(r['wrappers']['buggy'] != r['wrappers']['fixed'] for r in pool['tasks']):
        raise ValueError('Bug and fix use different adapters')
    tasks = read_pool(HERE)
    report = json.loads((HERE / 'qualification.json').read_text())
    if report['pool_sha256'] != plan['pool_sha256']:
        raise ValueError('Qualification refers to another pool')
    checked_cases, checked_suites = 0, 0
    with tempfile.TemporaryDirectory(prefix='ablation-source-audit-') as tmp:
        root = Path(tmp)
        unpack(HERE / 'upstream-sources.zip', root / 'upstream')
        source_audit = audit_sources(HERE, root / 'upstream')
        unpack(HERE / 'qualification-evidence.zip', root / 'evidence')
        evidence = root / 'evidence'
        if json.loads((evidence / 'qualification.json').read_text()) != report:
            raise ValueError('Published qualification differs from archive')
        for name, digest in report['runtime']['sha256'].items():
            if name.startswith('runtime/'):
                if sha(evidence / 'frozen-runtime' / (Path(name).name + '.txt')) != digest:
                    raise ValueError('Executed runtime snapshot differs')
        if [r['id'] for r in report['tasks']] != [slug for slug, _, _ in tasks]:
            raise ValueError('Qualification dropped or reordered components')
        for (slug, task, fixed), row in zip(tasks, report['tasks'], strict=True):
            run = evidence / 'runs' / slug
            if audit_run(run) != row['audit'] or sha(run / 'completion.json') != row['completion_sha256']:
                raise ValueError('Qualification journal changed')
            completion = json.loads((run / 'completion.json').read_text())
            if completion['task_hash'] != task.task_hash or completion['checks'] != row['checks']:
                raise ValueError('Completion belongs to another task or checks')
            objects = {p.stem: json.loads(p.read_text()) for p in (run / 'objects').glob('*.json')}
            labels = {}
            for key, obj in objects.items():
                if obj['kind'] != 'artifact':
                    continue
                if obj['files'] == task.public['files']:
                    labels[key] = 'initial'
                elif obj['files'] == fixed:
                    labels[key] = 'reference'
                else:
                    raise ValueError('Unexpected qualification artifact')
            observed = defaultdict(list)
            for obj in objects.values():
                if obj['kind'] != 'evaluation':
                    continue
                if obj['task'] != task.task_hash:
                    raise ValueError('Evaluation belongs to another task')
                label, channel = labels[obj['artifact']], obj['channel']
                cases = task.cases(channel)
                result = obj['result']
                if [c['id'] for c in result['cases']] != [c['id'] for c in cases]:
                    raise ValueError('Missing or extra case observation')
                flags = []
                for expected_case, saved in zip(cases, result['cases'], strict=True):
                    actual = saved['observed']
                    flag = (actual.get('status') == 'returned' and
                            canonical(actual.get('value')) == canonical(expected_case['expected']))
                    if flag != saved['passed']:
                        raise ValueError('Saved pass flag disagrees with expected output')
                    flags.append(flag)
                compact = {k: result[k] for k in ('passed_cases', 'total_cases', 'cases')}
                if (result['passed_cases'] != sum(flags) or result['total_cases'] != len(cases)
                        or result['passed'] != all(flags) or compact != row['outcomes'][label][channel]):
                    raise ValueError('Qualification summary disagrees with observations')
                observed[label, channel].append(result['cases'])
                checked_cases += len(cases)
                checked_suites += 1
            if set(observed) != {(a, c) for a in ('initial', 'reference') for c in ('public', 'evaluator')}:
                raise ValueError('Qualification missing an artifact/suite')
            for (label, channel), repeats in observed.items():
                if len(repeats) != 2 or repeats[0] != repeats[1]:
                    raise ValueError('Qualification lacks two identical repetitions')
                passes = [all(c['passed'] for c in rep) for rep in repeats]
                if passes != ([False, False] if label == 'initial' else [True, True]):
                    raise ValueError('Original and reference do not discriminate')
                if row['checks'][label][channel] != {'passed': passes, 'repeatable': True}:
                    raise ValueError('Saved qualification checks differ')
            if not row['engineering_qualified'] or not completion['engineering_qualified']:
                raise ValueError('Qualification status differs')
    return {'reviewed_candidate_ids': len(queue), 'qualified_bounded_components': len(tasks),
            'full_upstream_bugs_qualified': 0, 'verified_source_files': source_audit['full_files_verified'],
            'verified_suites': checked_suites, 'verified_case_executions': checked_cases,
            'model_calls': 0, 'model_cohort_frozen': False}, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sandbox', action='store_true', help='Re-execute all components in native macOS isolation')
    args = parser.parse_args()
    result, old = audit()
    if args.sandbox:
        with tempfile.TemporaryDirectory(prefix='ablation-components-replay-') as tmp:
            new = qualify_pool(HERE, Path(tmp) / 'qualification')
            for previous, replayed in zip(old['tasks'], new['tasks'], strict=True):
                if previous['outcomes'] != replayed['outcomes'] or previous['checks'] != replayed['checks']:
                    raise ValueError('Independent sandbox replay differs')
            result['sandbox_replay_discrepancies'] = 0
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
