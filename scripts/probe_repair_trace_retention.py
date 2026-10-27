"""Offline matched trace audit on exposed sources; no providers or model results.

Run on macOS from the repository root. Output is exclusive; previous reports
are never overwritten. Expected answers are used only for parent-side scoring.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import time

from vao.repair.environment import canonical, identity
from vao.repair.pool import read_pool
from vao.repair.region_verifier import RegionRepairVerifier
from vao.repair.verifier import RepairVerifier

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'experiments/python-repair/checkpoint-environment'
STATEFUL = BASE / 'results/stateful-trace-feasibility-20261027'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stateful_artifacts():
    """Reconstruct published adapters from inert source, never import upstream."""
    def extract(path, names):
        text = path.read_text()
        lines, pieces = text.splitlines(True), []
        for node in ast.parse(text).body:
            name = getattr(node, 'name', None)
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                name = getattr(node.targets[0], 'id', None)
            if name in names:
                pieces.append(''.join(lines[node.lineno-1:node.end_lineno]))
        if len(pieces) != len(names):
            raise ValueError('Incomplete upstream extraction')
        return '\n\n'.join(pieces)
    header = '''import json
import copy
import warnings
from collections.abc import MutableMapping
from importlib import import_module
from types import SimpleNamespace
# Exact Python3 semantics for the two six APIs used by these preserved classes.
six=SimpleNamespace(string_types=(str,), iteritems=lambda mapping:iter(mapping.items()))
'''
    wrapper = '''
def solve(defaults, base, updates):
    component = BaseSettings(defaults, priority='default')
    settings = BaseSettings({'COMPONENT': component})
    if base is not None:
        settings.set('COMPONENT_BASE', base, priority='project')
    for key, value, priority in updates:
        component.set(key, value, priority)
    result = settings._getcomposite('COMPONENT')
    return [[key, result[key], result.getpriority(key)] for key in sorted(result)]
'''
    names = {'SETTINGS_PRIORITIES', 'get_settings_priority', 'SettingsAttribute', 'BaseSettings', '_DictProxy'}
    previous = json.loads((STATEFUL/'probe-results.json').read_text())
    cases = json.loads((STATEFUL/'probe-inputs.json').read_text())['cases']
    for version in ('buggy', 'fixed'):
        files = {'solution.py': header + extract(STATEFUL/'exceptions.txt', {'ScrapyDeprecationWarning'})
                 + '\n\n' + extract(STATEFUL/(version+'.txt'), names) + wrapper}
        if identity(files) != previous['variants'][version]['source_sha256']:
            raise ValueError('Stateful adapter differs from the published feasibility probe')
        yield 'scrapy-026', version, files, {'module': 'solution', 'function': 'solve'}, cases


def inputs():
    yield from stateful_artifacts()
    for slug, task, reference in read_pool(BASE/'development-broader'):
        for version, files in [('buggy', task.public['files']), ('fixed', reference)]:
            yield slug, version, files, task.public['entrypoint'], task.public['public_cases']


def manifest():
    paths = [Path(__file__), ROOT/'src/vao/repair/region_trace_worker.py',
             ROOT/'src/vao/repair/region_verifier.py', ROOT/'src/vao/repair/trace_worker.py',
             ROOT/'src/vao/repair/verifier.py', ROOT/'src/vao/repair/worker.py',
             ROOT/'src/vao/repair/environment.py', ROOT/'src/vao/repair/pool.py',
             ROOT/'src/vao/decisions/verification.py', BASE/'development-broader/pool.json',
             STATEFUL/'probe-inputs.json', STATEFUL/'probe-results.json',
             STATEFUL/'buggy.txt', STATEFUL/'fixed.txt', STATEFUL/'exceptions.txt']
    return {str(p.relative_to(ROOT)): digest(p) for p in paths}


def metric(trace_result):
    trace = trace_result.get('trace', {})
    events = trace.get('events', [])
    return {'available': trace_result['available'], 'reason': trace_result['reason'],
            'events': len(events), 'events_seen': trace.get('events_seen'),
            'trace_json_bytes': len(canonical(trace).encode()),
            'selected_event_bytes': sum(len(json.dumps(e, ensure_ascii=True, allow_nan=False).encode()) for e in events),
            'function_names': sorted({e['function'] for e in events}),
            'capture_limit_reached': trace.get('capture_limit_reached'),
            'buffer_limit_reached': trace.get('buffer_limit_reached'),
            'retention': trace.get('retention'),
            'omitted_object_values': sum(v == {'omitted': 'object_or_depth_limit'}
                                         for e in events for v in e['locals'].values())}


def run(output, repeats):
    before = manifest()
    selected = list(inputs())
    output.mkdir(parents=True, exist_ok=False)
    old, new = RepairVerifier(), RegionRepairVerifier()
    preflight = old.preflight()
    records, details = [], []
    for slug, version, files, entry, cases in selected:
        for case in cases:
            index = len(records)
            methods = {'ordinary': lambda: old.invoke(files, entry, case),
                       'tail': lambda: old.trace(files, entry, case),
                       'balanced': lambda: new.trace(files, entry, case)}
            timings, results = {k: [] for k in methods}, {k: [] for k in methods}
            orders = []
            for repeat in range(repeats):
                names = list(methods)
                offset = (index + repeat) % 3
                names = names[offset:] + names[:offset]
                orders.append(names)
                for name in names:
                    start = time.perf_counter()
                    result = methods[name]()
                    timings[name].append(time.perf_counter()-start)
                    results[name].append(result)
            deterministic = all(all(r == values[0] for r in values) for values in results.values())
            ordinary, tail, balanced = (results[k][0] for k in ('ordinary', 'tail', 'balanced'))
            match = all(results['ordinary'][i] == results['tail'][i].get('observed')
                        == results['balanced'][i].get('observed') for i in range(repeats))
            observations_stable = all(r == ordinary for r in results['ordinary'])
            passed = ((ordinary.get('status') == 'returned' and canonical(ordinary.get('value')) == canonical(case['expected']))
                      if 'expected' in case else ordinary == {'status': 'exception', 'exception': case['raises']})
            row = {'task': slug, 'variant': version, 'case': case['id'], 'artifact_sha256': identity(files),
                   'input_sha256': identity([case['args'], case.get('kwargs', {})]), 'passed': passed,
                   'ordinary_trace_agreement': match, 'repeat_deterministic': deterministic,
                   'ordinary_observations_stable': observations_stable,
                   'metrics': {k: metric(results[k][0]) for k in ('tail', 'balanced')},
                   'timing_seconds': timings, 'execution_orders': orders}
            if slug == 'scrapy-026':
                # Post-execution audit only. Neither trace worker receives this name or a fix.
                row['known_target_audit'] = {k: sum(e['function'] == '_getcomposite' for e in results[k][0].get('trace', {}).get('events', []))
                                             for k in ('tail', 'balanced')}
            records.append(row)
            details.append({'task': slug, 'variant': version, 'case': case['id'], 'results': results})
        print(json.dumps({'completed': slug, 'variant': version, 'case_comparisons': len(records)}), flush=True)
    if manifest() != before:
        raise ValueError('Runtime or input sources changed during probe')
    payload = (json.dumps(details, indent=2)+'\n').encode()
    with (output/'traces.json.gz').open('xb') as stream:
        stream.write(gzip.compress(payload, mtime=0))
    all_times = {k: [v for r in records for v in r['timing_seconds'][k]] for k in ('ordinary', 'tail', 'balanced')}
    target = [r for r in records if r['task'] == 'scrapy-026' and r['variant'] == 'buggy' and not r['passed']]
    summary = {'kind': 'offline_trace_retention_engineering', 'api_calls': 0, 'model_results': False,
               'heldout_cases_used': 0, 'source_manifest': before, 'preflight': preflight,
               'selected_cases': len(records), 'repeats': repeats, 'sandbox_executions': len(records)*3*repeats,
               'all_observations_match': all(r['ordinary_trace_agreement'] for r in records),
               'all_repeats_deterministic': all(r['repeat_deterministic'] for r in records),
               'all_ordinary_observations_stable': all(r['ordinary_observations_stable'] for r in records),
               'nondeterministic_trace_cases': [':'.join(r[k] for k in ('task','variant','case')) for r in records if not r['repeat_deterministic']],
               'available': {k: sum(r['metrics'][k]['available'] for r in records) for k in ('tail', 'balanced')},
               'capture_limit_cases': {k: sum(bool(r['metrics'][k]['capture_limit_reached']) for r in records) for k in ('tail', 'balanced')},
               'balanced_buffer_limit_cases': sum(bool(r['metrics']['balanced']['buffer_limit_reached']) for r in records),
               'known_target_failing_cases_represented': {k: sum(r['known_target_audit'][k] > 0 for r in target) for k in ('tail', 'balanced')},
               'timing_seconds': {k: {'total': sum(v), 'median': statistics.median(v), 'samples': len(v)} for k, v in all_times.items()},
               'trace_archive_sha256': digest(output/'traces.json.gz'), 'records': records,
               'limitations': ['Exposed development cases, not model-efficacy or generalization evidence.',
                               'All original public and four previously published engineering inputs retained; evaluator inputs unused.',
                               'Local timings include process startup; no token, dollar, or peak-memory measurement.',
                               'Sandbox execution counts exclude the separate one-call preflight.',
                               'Traces may contain process-specific hashes/set iteration; preserve these observations rather than normalize or label deterministic.',
                               'Same output cap does not mean equal acquisition cost; larger capture buffer is charged separately.',
                               'Objects remain omitted; function presence does not prove useful state is visible.',
                               'Known fault method used only to audit coverage after execution, never to choose retained events.',
                               'Fewer retained events in a function can lose useful detail; no general dominance claim.']}
    (output/'report.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('records', 'source_manifest', 'limitations')}, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    report = run(args.output, args.repeats)
    return int(not report['all_observations_match'] or not report['all_ordinary_observations_stable']
               or any(count != report['selected_cases'] for count in report['available'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
