"""Original package imports and immutable context under the actual OS boundary."""
import sys

import pytest

from vao.repair.environment import RepairTask
from vao.repair.package_environment import PackageTask, PackageVerifier, validate_workspace

NATIVE = pytest.mark.skipif(sys.platform != 'darwin', reason='Native package execution needs macOS')


def saved_package():
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parents[2] / 'experiments/python-repair/checkpoint-environment/development-package-black13'
    return json.loads((base / 'task.json').read_text()), json.loads((base / 'qualification.json').read_text())


def test_package_projection_metadata_and_support_boundary_without_execution():
    import json
    from copy import deepcopy
    from types import SimpleNamespace
    from vao.repair.package_spectra import observe, triplet
    p, report = saved_package()
    p['provenance']['private_annotations'] = 'PRIVATE_EVALUATOR_SENTINEL_56327'
    requests = triplet(p, report['stored'], report['acquisition'])
    assert 'PRIVATE_EVALUATOR_SENTINEL_56327' not in str(requests)
    assert json.loads(requests['feedback']['messages'][1]['content'])['support_files'] == p['support_files']
    changed = deepcopy(p); changed['support_files']['adapter.py'] += '# changed\n'
    with pytest.raises(ValueError, match='Verifier immutable context'):
        observe(changed, SimpleNamespace(public=p))
    with pytest.raises(ValueError, match='current sources'):
        triplet(changed, report['stored'], report['acquisition'])


@pytest.mark.parametrize('tamper', ['execution_count', 'time', 'pass_flag', 'missing_case'])
def test_saved_package_rejects_forged_accounting_and_feedback(tamper):
    from vao.repair.package_spectra import triplet
    p, report = saved_package()
    if tamper == 'execution_count':
        report['acquisition']['additional_executions'] = 0
    elif tamper == 'time':
        report['acquisition']['seconds'] = float('nan')
    elif tamper == 'pass_flag':
        report['stored']['feedback']['cases'][0]['passed'] = True
    else:
        report['acquisition']['cases'].pop()
    with pytest.raises(ValueError):
        triplet(p, report['stored'], report['acquisition'])


def public():
    return {'schema_version': 2, 'task_id': 'synthetic/package', 'instruction': 'Return twice x.',
            'entrypoint': {'module': 'pkg.main', 'function': 'solve'},
            'files': {'pkg/main.py': 'from .helper import twice\ndef solve(x):\n    return twice(x)\n'},
            'support_files': {'pkg/__init__.py': '', 'pkg/helper.py': 'def twice(x):\n    return 2*x\n'},
            'public_cases': [{'id': 'public', 'args': [3], 'expected': 6}],
            'provenance': {'kind': 'synthetic_engineering_fixture'}}


def test_task_identity_includes_support_and_version_one_stays_narrow():
    p = public()
    hidden = {'cases': [{'id': 'hidden', 'args': [4], 'expected': 8}]}
    task = PackageTask.from_dicts(p, hidden)
    p['support_files']['pkg/helper.py'] += '# changed\n'
    assert task.task_hash != PackageTask.from_dicts(p, hidden).task_hash
    assert task.public['support_files']['pkg/helper.py'] != p['support_files']['pkg/helper.py']
    assert task.cases('evaluator') == hidden['cases']
    with pytest.raises(ValueError):
        RepairTask.from_dicts(task.public, hidden)
    with pytest.raises(ValueError):
        task.validate_artifact({**task.public['files'], **task.public['support_files']})
    with pytest.raises(ValueError):
        task.validate_artifact({'pkg/other.py': 'pass'})


def test_legacy_runner_cannot_drop_context_or_enable_package_model_calls(tmp_path):
    from vao.repair.environment import RepairRun
    p = public(); task = PackageTask.from_dicts(p, {'cases': p['public_cases']})
    with pytest.raises(ValueError, match='offline qualification'):
        RepairRun(tmp_path / 'forbidden', task, None, mode='model_pilot')
    assert not (tmp_path / 'forbidden').exists()
    run = RepairRun(tmp_path / 'offline', task, None)
    assert run.artifact(run.initial) == p['files']
    with pytest.raises(ValueError, match='collection/branch'):
        run.fork('irrelevant', 'continue', '1')
    with pytest.raises(ValueError, match='package_spectra'):
        run.request('irrelevant')
    with pytest.raises(ValueError, match='package verifier'):
        run.materialize(run.initial, 'forbidden')


@pytest.mark.parametrize('path', ['../escape.py', '/tmp/escape.py', 'pkg/../x.py', 'pkg//x.py',
                                 'pkg/./x.py', 'pkg\\x.py', 'pkg/link.txt', 'pkg/é.py',
                                 '__repair_worker.py', 'pkg/__repair_fake.py'])
def test_reject_unsafe_or_reserved_paths(path):
    with pytest.raises(ValueError):
        validate_workspace({path: 'pass'}, {'pkg/__init__.py': ''})


@pytest.mark.parametrize('files', [
    {'pkg/main.py': 'pass'},
    {'pkg.py': 'pass', 'pkg/__init__.py': ''},
    {'Pkg.py': 'pass', 'pkg/__init__.py': ''},
    {'pkg/__init__.py': '', 'pkg/Main.py': 'pass', 'pkg/main.py': 'pass'},
    {'pkg/__init__.py': '', 'Pkg/__init__.py': '', 'Pkg/main.py': 'pass'},
    {'big.py': 'x' * 262145},
])
def test_reject_ambiguous_missing_or_oversized_context(files):
    with pytest.raises(ValueError):
        validate_workspace(files, {})


def test_private_fields_and_external_entrypoints_rejected():
    p = public()
    p['evaluator_cases'] = []
    with pytest.raises(ValueError):
        PackageTask.from_dicts(p, {'cases': public()['public_cases']})
    p = public(); p['entrypoint']['module'] = 'os'
    with pytest.raises(ValueError):
        PackageTask.from_dicts(p, {'cases': p['public_cases']})


@NATIVE
def test_native_package_imports_source_protection_and_coverage():
    p = public(); verifier = PackageVerifier(p)
    assert verifier.preflight()['source_writes_denied']
    case = p['public_cases'][0]
    observed = verifier.invoke(p['files'], p['entrypoint'], case)
    covered = verifier.coverage(p['files'], p['entrypoint'], case)
    assert observed == {'status': 'returned', 'value': 6}
    assert covered['available'] and covered['observed'] == observed
    assert ['pkg/helper.py', 2] in covered['coverage']['lines']
    assert ['pkg/main.py', 3] in covered['coverage']['lines']
    with pytest.raises(ValueError):
        verifier.invoke({**p['files'], **p['support_files']}, p['entrypoint'], case)


@NATIVE
def test_native_expected_answers_absent_and_stale_process_state_not_reused():
    p = public()
    p['files']['pkg/main.py'] = '''import sys
COUNT = 0
def solve(x):
    global COUNT
    COUNT += 1
    frame = sys._getframe()
    while frame is not None:
        if 'payload' in frame.f_locals:
            return [COUNT, sorted(frame.f_locals['payload'])]
        frame = frame.f_back
'''
    verifier = PackageVerifier(p)
    case = {'args': [3], 'expected': 'PRIVATE_SENTINEL', 'id': 'PRIVATE_ID'}
    expected = {'status': 'returned', 'value': [1, ['args', 'coverage_files', 'entrypoint', 'kwargs']]}
    assert verifier.invoke(p['files'], p['entrypoint'], case) == expected
    covered = verifier.coverage(p['files'], p['entrypoint'], case)
    assert covered['available'] and covered['observed'] == expected
    assert 'PRIVATE' not in str(covered)


@NATIVE
def test_native_failure_states_remain_observations():
    p = public(); verifier = PackageVerifier(p, timeout=.3); entry = p['entrypoint']; case = {'args': [0]}
    assert verifier.invoke({'pkg/main.py': 'bad syntax!'}, entry, case)['status'] == 'load_error'
    assert verifier.invoke({'pkg/main.py': 'def solve(x):\n    while True: pass\n'}, entry, case)['status'] == 'timeout'
    source = {'pkg/main.py': 'import sys\ndef solve(x):\n    sys.settrace(None)\n    return 0\n'}
    covered = verifier.coverage(source, entry, case)
    assert not covered['available'] and covered['reason'] == 'incomplete_coverage'
    assert covered['observed'] == {'status': 'returned', 'value': 0}


@NATIVE
def test_native_package_triplets_bind_immutable_context_and_omit_private_metadata():
    import json
    from copy import deepcopy
    from vao.repair.package_spectra import acquire, analyze, observe, triplet
    p = public()
    p['public_cases'] = [{'id': 'fail', 'args': [3], 'expected': 0},
                         {'id': 'pass', 'args': [0], 'expected': 0}]
    p['provenance']['hidden_annotation'] = 'PRIVATE_SENTINEL'
    verifier = PackageVerifier(p)
    stored = observe(p, verifier)
    acquired = acquire(p, stored, verifier)
    result = analyze(p, stored, acquired)
    assert result['available'] and result['additional_executions'] == 4
    requests = triplet(p, stored, acquired)
    assert 'PRIVATE_SENTINEL' not in str(requests)
    assert all(r['provider_call_enabled'] is False for r in requests.values())
    payload = {a: json.loads(r['messages'][1]['content']) for a, r in requests.items()}
    assert payload['feedback']['support_files'] == p['support_files']
    locations = payload['neutral']['source_excerpts']['locations']
    assert any(not r['editable'] and r['file'] == 'pkg/helper.py' for r in locations)
    assert all(r['failing_covered'] == r['passing_covered'] == r['squared_ochiai'] == 'not supplied' for r in locations)
    changed = deepcopy(p); changed['support_files']['pkg/helper.py'] += '# stale\n'
    with pytest.raises(ValueError, match='Verifier immutable context'):
        observe(changed, verifier)
    with pytest.raises(ValueError, match='current sources'):
        triplet(changed, stored, acquired)
    broken = deepcopy(acquired); broken['cases'].pop()
    with pytest.raises(ValueError, match='omitted'):
        triplet(p, stored, broken)
    broken = deepcopy(acquired); broken['additional_executions'] = 0
    with pytest.raises(ValueError, match='resource accounting'):
        triplet(p, stored, broken)
    broken = deepcopy(acquired); broken['cases'][0]['coverage_result']['available'] = False
    req = triplet(p, stored, broken)
    for arm in ('neutral', 'scored'):
        assert json.loads(req[arm]['messages'][1]['content'])['source_excerpts']['locations'] is None


@NATIVE
@pytest.mark.parametrize('kind', ['hardlink', 'symlink'])
def test_native_source_protection_cannot_be_bypassed_with_scratch_alias(kind):
    p = public()
    p['files']['pkg/main.py'] = '''import os
from pathlib import Path
def solve(kind):
    target = Path('pkg/helper.py').resolve()
    alias = Path(os.environ['TMPDIR']) / 'alias.py'
    try:
        if kind == 'hardlink': os.link(target, alias)
        else: alias.symlink_to(target)
        alias.write_text('VALUE = 99')
    except PermissionError:
        return True
    return False
'''
    v = PackageVerifier(p)
    assert v.invoke(p['files'], p['entrypoint'], {'args': [kind]}) == {'status': 'returned', 'value': True}
