"""Audit original package bytes, every saved test and public-only projections."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile

from vao.repair.environment import audit_run, canonical
from vao.repair.package_environment import PackageTask
from vao.repair.package_spectra import analyze, binding, triplet
from vao.repair.spectra import score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    plan = json.loads((HERE / 'qualification-plan.json').read_text())
    for name, digest in {**plan['frozen_files_sha256'],
                         **json.loads((HERE / 'evidence-manifest.json').read_text())}.items():
        if sha(HERE / name) != digest:
            raise ValueError('Frozen input/evidence differs: ' + name)
    task = PackageTask.load(HERE)
    if task.task_hash != plan['task_hash']:
        raise ValueError('Task identity differs')
    public = task.public
    reference = json.loads((HERE / 'reference.json').read_text())
    task.validate_artifact(reference)
    with zipfile.ZipFile(HERE / 'upstream-sources.zip') as z:
        records = json.loads(z.read('manifest.json'))['files']
        for row in records:
            raw = z.read(row['local_path'])
            if row['status'] != 'downloaded_inert' or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Pinned upstream content differs')
            if row['role'] in ('buggy', 'fixed'):
                files = public['files'] if row['role'] == 'buggy' else reference
                content = files.get(row['path'], public['support_files'].get(row['path']))
                if content != raw.decode():
                    raise ValueError('Original package source was adapted')
        upstream_example = z.read('context/tests/data/python37.py.txt').decode().split('# output')[0]
        if upstream_example.rstrip() != public['public_cases'][0]['args'][0].rstrip():
            raise ValueError('Upstream regression input no longer matches')
    if {canonical(c['args']) for c in public['public_cases']} & {canonical(c['args']) for c in task.cases('evaluator')}:
        raise ValueError('Public and evaluator inputs overlap')
    report = json.loads((HERE / 'qualification.json').read_text())
    with tempfile.TemporaryDirectory(prefix='package-black13-audit-') as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(HERE / 'qualification-evidence.zip') as z:
            if len(z.namelist()) != len(set(z.namelist())):
                raise ValueError('Duplicate evidence entry')
            for name in z.namelist():
                path = (root / name).resolve()
                if not path.is_relative_to(root.resolve()):
                    raise ValueError('Unsafe evidence path')
                path.parent.mkdir(exist_ok=True, parents=True)
                path.write_bytes(z.read(name))
        if json.loads((root / 'qualification.json').read_text()) != report:
            raise ValueError('Published report differs from raw archive')
        if json.loads((root / 'journal/completion.json').read_text()) != report:
            raise ValueError('Report differs from journal completion')
        if audit_run(root / 'journal') != report['audit']:
            raise ValueError('Journal integrity differs')
        for name, digest in report['provenance']['sha256'].items():
            path = (root / 'frozen-runtime' / (Path(name).name + '.txt')
                    if name.startswith('runtime/') else HERE / Path(name).name)
            if sha(path) != digest:
                raise ValueError('Executed runtime/fixture differs')
        if sha(root / 'frozen-runtime/qualify_repair_package.py.txt') != report['script_sha256']:
            raise ValueError('Executed qualification script differs')
        expected_keys = {(a, c, i) for a in ('initial', 'reference') for c in ('public', 'evaluator') for i in (0, 1)}
        rows = report['evaluations']
        if len(rows) != 8 or {(r['label'], r['channel'], r['repeat']) for r in rows} != expected_keys:
            raise ValueError('Missing or duplicate evaluation')
        grouped = {}
        for row in rows:
            obj = json.loads((root / 'journal/objects' / (row['object'] + '.json')).read_text())
            if obj['result'] != row['result'] or obj['task'] != task.task_hash or obj['channel'] != row['channel']:
                raise ValueError('Report evaluation differs from journal')
            artifact = json.loads((root / 'journal/objects' / (obj['artifact'] + '.json')).read_text())
            if artifact['files'] != (public['files'] if row['label'] == 'initial' else reference):
                raise ValueError('Evaluation used another source artifact')
            cases = task.cases(row['channel']); result = row['result']
            if [x['id'] for x in cases] != [x['id'] for x in result['cases']]:
                raise ValueError('Missing or reordered case observation')
            flags = []
            for case, observation in zip(cases, result['cases'], strict=True):
                flag = score(case, observation['observed'])
                if flag != observation['passed']:
                    raise ValueError('Incorrect saved case label')
                flags.append(flag)
            if result['passed_cases'] != sum(flags) or result['total_cases'] != len(cases) or result['passed'] != all(flags):
                raise ValueError('Incorrect saved totals')
            grouped.setdefault((row['label'], row['channel']), []).append(result)
        for (label, channel), repeats in grouped.items():
            expected = [label == 'reference'] * 2
            check = {'passed': [x['passed'] for x in repeats], 'repeatable': repeats[0]['cases'] == repeats[1]['cases']}
            if check != {'passed': expected, 'repeatable': True} or check != report['checks'][label][channel]:
                raise ValueError('Qualification gate or repeatability differs')
        initial = grouped['initial', 'public'][0]
        if report['stored']['binding'] != binding(public) or report['stored']['feedback'] != {
                k: initial[k] for k in ('passed', 'passed_cases', 'total_cases', 'cases')}:
            raise ValueError('Acquisition does not bind the saved initial public observation')
    if analyze(public, report['stored'], report['acquisition']) != report['diagnostic']:
        raise ValueError('Public spectrum differs')
    if triplet(public, report['stored'], report['acquisition']) != report['inert_projections']:
        raise ValueError('F/N/S package projections differ')
    if (report['qualification_case_executions'] != 64 or report['diagnostic_case_executions'] != 16
            or report['qualification_case_executions'] != sum(r['result']['total_cases'] for r in rows)
            or report['diagnostic_case_executions'] != report['acquisition']['additional_executions']
            or not report['engineering_qualified'] or report['api_calls'] != 0):
        raise ValueError('Execution or qualification accounting differs')
    return report


def compare(old, new):
    for key in ('checks', 'engineering_qualified', 'inert_projections'):
        if old[key] != new[key]:
            raise ValueError('Independent replay differs: ' + key)
    for a, b in zip(old['evaluations'], new['evaluations'], strict=True):
        if any(a[k] != b[k] for k in ('label', 'channel', 'repeat')) or a['result']['cases'] != b['result']['cases']:
            raise ValueError('Independent case observation differs')
    if old['acquisition']['cases'] != new['acquisition']['cases']:
        raise ValueError('Independent coverage replay differs')
    if any(old['diagnostic'][k] != new['diagnostic'][k] for k in ('ranking', 'metrics', 'available')):
        raise ValueError('Independent spectrum replay differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sandbox', action='store_true')
    args = parser.parse_args()
    old = audit()
    if args.sandbox:
        spec = importlib.util.spec_from_file_location('qualify_package', ROOT / 'scripts/qualify_repair_package.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='package-black13-replay-') as tmp:
            new = module.qualify(HERE, Path(tmp) / 'qualification')
            compare(old, new)
    print(json.dumps({'package_components': 1, 'qualification_case_executions_verified': 64,
                      'diagnostic_case_executions_verified': 16, 'original_upstream_files_verified': 11,
                      'inert_projections': 3, 'sandbox_replay': args.sandbox, 'model_calls': 0}, indent=2))


if __name__ == '__main__':
    main()
