"""Qualify an original Python package component offline, retaining every outcome."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from vao.repair.cli import finish, source_manifest
from vao.repair.environment import RepairRun
from vao.repair.package_environment import PackageTask, PackageVerifier
from vao.repair.package_spectra import acquire, analyze, binding, triplet


def qualify(bundle, output):
    plan = json.loads((bundle / 'qualification-plan.json').read_text())
    for name, digest in plan['frozen_files_sha256'].items():
        if hashlib.sha256((bundle / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Qualification input differs from pre-execution plan')
    task = PackageTask.load(bundle)
    if task.task_hash != plan['task_hash']:
        raise ValueError('Task differs from pre-execution plan')
    reference = json.loads((bundle / 'reference.json').read_text())
    task.validate_artifact(reference)
    provenance = source_manifest(bundle)
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    verifier = PackageVerifier(task.public)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'freeze.json').write_text(json.dumps({'runtime': provenance, 'script_sha256': script_sha,
        'qualification_plan_sha256': hashlib.sha256((bundle / 'qualification-plan.json').read_bytes()).hexdigest()}, indent=2) + '\n')
    with zipfile.ZipFile(output / 'runtime.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        source_root = Path(__file__).resolve().parents[1] / 'src/vao'
        for name, digest in provenance['sha256'].items():
            if name.startswith('runtime/'):
                path = source_root / ('decisions/verification.py' if name == 'runtime/verification.py'
                                      else 'repair/' + Path(name).name)
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError('Runtime changed before snapshot')
                archive.writestr(name + '.txt', raw)
        archive.writestr('qualify_repair_package.py.txt', Path(__file__).read_bytes())
    probe = verifier.preflight()
    run = RepairRun(output / 'journal', task, verifier)
    artifacts = {'initial': run.initial, 'reference': run.snapshot(reference)}
    evaluations, checks = [], {}
    initial_public = None
    for label, artifact in artifacts.items():
        checks[label] = {}
        for channel in ('public', 'evaluator'):
            results = []
            for repeat in range(2):
                key = run.evaluate(artifact, channel)
                result = run.get(key)['result']
                evaluations.append({'label': label, 'channel': channel, 'repeat': repeat,
                                    'object': key, 'result': result})
                results.append(result)
            checks[label][channel] = {'passed': [r['passed'] for r in results],
                                      'repeatable': results[0]['cases'] == results[1]['cases']}
            if label == 'initial' and channel == 'public':
                initial_public = results[0]
    stable = all(r['repeatable'] for channels in checks.values() for r in channels.values())
    discriminates = all(checks['initial'][c]['passed'] == [False, False]
                        and checks['reference'][c]['passed'] == [True, True] for c in ('public', 'evaluator'))
    stored = {'binding': binding(task.public),
              'feedback': {k: initial_public[k] for k in ('passed', 'passed_cases', 'total_cases', 'cases')},
              'verifier_seconds': initial_public['verifier_seconds']}
    acquisition = diagnostic = projections = None
    if not stored['feedback']['passed']:
        acquisition = acquire(task.public, stored, verifier)
        diagnostic = analyze(task.public, stored, acquisition)
        projections = triplet(task.public, stored, acquisition)
        key = run.put({'kind': 'package_public_acquisition', 'task': task.task_hash,
                       'stored': stored, 'acquisition': acquisition, 'diagnostic': diagnostic,
                       'inert_projections': projections})
        run.record('public_acquisition', [key], {'mode': 'offline_engineering'})
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != script_sha:
        raise ValueError('Qualification script changed while executing')
    report = finish(run, bundle, provenance, {'task': task.public['task_id'], 'task_hash': task.task_hash,
        'probe': probe, 'checks': checks, 'evaluations': evaluations,
        'engineering_qualified': stable and discriminates, 'stored': stored,
        'acquisition': acquisition, 'diagnostic': diagnostic, 'inert_projections': projections,
        'qualification_case_executions': sum(r['result']['total_cases'] for r in evaluations),
        'diagnostic_case_executions': acquisition['additional_executions'] if acquisition else 0,
        'script_sha256': script_sha, 'evaluation_ready': False,
        'limits': plan['limits']})
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'qualify'), nargs='?', default='plan')
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'plan':
        task = PackageTask.load(args.bundle)
        result = {'task_hash': task.task_hash, 'mode': 'offline_plan_only', 'model_calls': 0}
    else:
        if not args.output:
            parser.error('qualify requires a fresh --output directory')
        report = qualify(args.bundle, args.output)
        result = {k: report[k] for k in ('task', 'engineering_qualified', 'qualification_case_executions',
                                        'diagnostic_case_executions', 'api_calls')}
        result['diagnostic_available'] = report['diagnostic']['available'] if report['diagnostic'] else False
    print(json.dumps(result, indent=2))
    return int(result.get('engineering_qualified') is False)


if __name__ == '__main__':
    raise SystemExit(main())
