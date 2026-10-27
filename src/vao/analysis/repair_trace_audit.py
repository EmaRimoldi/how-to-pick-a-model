"""Post hoc terminal-bank audit; inspect inert evidence, never execute candidates."""

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

from vao.analysis.repair_stagnation import classify
from vao.repair.environment import identity
from vao.repair.records import save


def structural_ast(node):
    """Versioned structural identity; ignore locations and absent generic parameters.

    Python 3.12 added empty type_params fields to existing function/class syntax.
    Do not let that metadata change identities of the same nongeneric program.
    Nonempty parameters remain significant. Literals are typed, including bytes,
    complex and Ellipsis; no candidate expression is executed.
    """
    if isinstance(node, ast.AST):
        return {'node': type(node).__name__, 'fields': {name: structural_ast(value)
            for name, value in ast.iter_fields(node) if not (name == 'type_params' and value == [])}}
    if isinstance(node, list):
        return [structural_ast(value) for value in node]
    return {'literal_type': type(node).__name__, 'representation': repr(node)}


def syntax_id(files):
    return identity({name: structural_ast(ast.parse(source)) for name, source in files.items()})


def bounded_values(value):
    """Count serialized marker occurrences, not distinct variables or runtime types."""
    result = Counter()
    if isinstance(value, dict):
        if 'omitted' in value:
            result['omitted:' + value['omitted']] += 1
        if 'prefix' in value and 'length' in value:
            result['shortened_string'] += 1
        if 'items' in value and 'length' in value and value['length'] > len(value['items']):
            result['shortened_container'] += 1
        for child in value.values():
            result.update(bounded_values(child))
    elif isinstance(value, list):
        for child in value:
            result.update(bounded_values(child))
    return result


def trace_metrics(task):
    diagnostic = task['diagnostic']
    if not diagnostic or not diagnostic['available']:
        return {'available': False}
    trace = diagnostic['trace_result']['trace']
    events = trace['events']
    entry = task['public']['entrypoint']
    entry_returns = [event for event in events if event['event'] == 'return'
        and event['file'] == entry['module'] + '.py' and event['function'] == entry['function']]
    markers = Counter()
    omitted_locals = set()
    for event in events:
        markers.update(bounded_values(event['locals']))
        if 'returned' in event:
            markers.update(bounded_values(event['returned']))
        for name, value in event['locals'].items():
            if isinstance(value, dict) and 'omitted' in value:
                omitted_locals.add((event['file'], event['function'], name, value['omitted']))
    return {
        'available': True, 'case_id': diagnostic['case_id'],
        'observed_status': diagnostic['untraced_observation']['status'],
        'trace_matches_untraced': diagnostic['untraced_observation'] == diagnostic['trace_result']['observed'],
        'events_kept': len(events), 'events_seen': trace['events_seen'],
        'events_dropped': trace['events_dropped'], 'capture_limit_reached': trace['capture_limit_reached'],
        'intact': trace['intact'], 'entrypoint_return_events': len(entry_returns),
        'exception_events': sum(e['event'] == 'exception' for e in events),
        'serialized_ascii_json_bytes': len(json.dumps(trace, ensure_ascii=True, allow_nan=False).encode()),
        'functions': sorted({e['function'] for e in events}),
        'marker_occurrences': dict(sorted(markers.items())),
        'omitted_local_slots': [dict(zip(('file', 'function', 'name', 'marker'), row)) for row in sorted(omitted_locals)],
        'events_at_local_slot_limit': sum(len(e['locals']) == trace['limits']['locals_per_event'] for e in events),
    }


def transitions(baseline, current):
    """Missing evaluation is not a failed test or a measured regression."""
    if current is None:
        return None
    before = {c['id']: c['passed'] for c in baseline['cases']}
    after = {c['id']: c['passed'] for c in current['cases']}
    if len(before) != len(baseline['cases']) or len(after) != len(current['cases']) or set(before) != set(after):
        raise ValueError('Public case identities differ or repeat')
    return {'corrected': sorted(k for k in before if not before[k] and after[k]),
        'regressed': sorted(k for k in before if before[k] and not after[k]),
        'still_failed': sorted(k for k in before if not before[k] and not after[k]),
        'preserved_passes': sorted(k for k in before if before[k] and after[k])}


def summarize(source):
    manifest = json.loads((source / 'evidence-manifest.json').read_text())
    raw = (source / 'evidence.zip').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['archive_sha256']:
        raise ValueError('Archive hash differs')
    with zipfile.ZipFile(source / 'evidence.zip') as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(manifest['files']):
            raise ValueError('Archive members differ')
        for name, expected in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError('Archive member hash differs')
        if 'collection/pilot-completion.json' not in names or 'collection/interruption.json' in names:
            raise ValueError('This audit requires a completed, uninterrupted bank')
        def read(name):
            return json.loads(archive.read('collection/' + name))
        packet = read('manifest.json')['freeze']['packet']
        requests = {r['metadata']['attempt_id']: r for r in packet['requests']}
        arms = sorted({r['metadata']['arm'] for r in packet['requests']})
        observations = [json.loads(line) for line in archive.read('collection/observations.jsonl').splitlines()]
        if len(requests) != len(packet['requests']) or len(observations) != len(requests) or {r['attempt_id'] for r in observations} != set(requests):
            raise ValueError('Incomplete or repeated request/observation identities')
        cells = []
        for row in observations:
            attempt = row['attempt_id']
            meta = requests[attempt]['metadata']
            if any(row[k] != meta[k] for k in ('arm', 'task_index', 'draw', 'task_hash')):
                raise ValueError('Observation metadata differs')
            def obj(key):
                value = read('cells/' + attempt + '/objects/' + key + '.json')
                if identity(value) != key:
                    raise ValueError('Object hash differs')
                return value
            task = packet['tasks'][row['task_index']]
            projected = json.loads(requests[attempt]['request']['messages'][1]['content'])
            if projected['files'] != task['public']['files']:
                raise ValueError('Prompt and source files differ')
            artifact = obj(row['artifact']) if row['artifact'] else None
            public = obj(row['public'])['result'] if row['public'] else None
            evaluator = obj(row['evaluator'])['result'] if row['evaluator'] else None
            category = classify(projected['files'], artifact['files'], projected['entrypoint']) if artifact else 'no_artifact'
            ast_id = None
            if artifact and category != 'unparseable':
                ast_id = syntax_id(artifact['files'])
            change = transitions(task['source_public_result'], public)
            full = bool(public and evaluator and public['passed'] and evaluator['passed'])
            if full != row['full_pass'] or bool(artifact) != row['decoded']['artifact_valid']:
                raise ValueError('Artifact/success classification differs')
            cells.append({'attempt_id': attempt, 'task_index': row['task_index'], 'arm': row['arm'],
                'draw': row['draw'], 'edit_category': category, 'ast_id': ast_id,
                'artifact_valid': bool(artifact), 'decoded_syntax_valid': row['decoded']['syntax_valid'], 'full_pass': full,
                'public_pass': public['passed'] if public else None,
                'false_public_acceptance': bool(public and public['passed'] and evaluator and not evaluator['passed']),
                'failed_public_observations': [{'id': c['id'], 'observed': c['observed']} for c in public['cases'] if not c['passed']] if public else None,
                'public_transitions': change,
                'evaluator_failed_cases': [c['id'] for c in evaluator['cases'] if not c['passed']] if evaluator else None})
        cells.sort(key=lambda c: (c['task_index'], c['draw'], c['arm']))
        tasks = [{'task_index': i, 'task': t['public']['task_id'], 'eligible': t['eligible'],
            'eligibility_reason': t['eligibility_reason'], 'source_full_pass': t['source_full_pass'],
            'source_public_failed_cases': [c['id'] for c in t['source_public_result']['cases'] if not c['passed']],
            'trace': trace_metrics(t)} for i, t in enumerate(packet['tasks'])]
    def group(scoped):
        return {'observed': len(scoped), 'valid': sum(c['artifact_valid'] for c in scoped),
            'edit_categories': dict(sorted(Counter(c['edit_category'] for c in scoped).items())),
            'distinct_asts': len({c['ast_id'] for c in scoped if c['ast_id']}),
            'full_repairs': sum(c['full_pass'] for c in scoped),
            'public_passes': sum(c['public_pass'] is True for c in scoped),
            'false_public_acceptances': sum(c['false_public_acceptance'] for c in scoped),
            'outputs_with_failed_load': sum(any(r['observed']['status'] == 'load_error' for r in c['failed_public_observations'] or []) for c in scoped),
            'outputs_with_failed_runtime_exception': sum(any(r['observed']['status'] == 'exception' for r in c['failed_public_observations'] or []) for c in scoped),
            'unmeasured_public_transitions': sum(c['public_transitions'] is None for c in scoped),
            'outputs_correcting_some_source_failure': sum(bool(c['public_transitions'] and c['public_transitions']['corrected']) for c in scoped),
            'outputs_regressing_any_source_pass': sum(bool(c['public_transitions'] and c['public_transitions']['regressed']) for c in scoped),
            'outputs_correcting_and_regressing': sum(bool(c['public_transitions'] and c['public_transitions']['corrected'] and c['public_transitions']['regressed']) for c in scoped),
            'outputs_fixing_selected_failure': sum(bool(c['public_transitions'] and tasks[c['task_index']]['trace'].get('case_id') in c['public_transitions']['corrected']) for c in scoped)}
    for task in tasks:
        task['arms'] = {arm: group([c for c in cells if c['task_index'] == task['task_index'] and c['arm'] == arm]) for arm in arms}
    traces = [t['trace'] for t in tasks if t['eligible']]
    return {'kind': 'post_hoc_trace_and_preservation_audit', 'api_calls': 0,
        'ast_identity_schema': 'typed-ast-fields-without-empty-type-params-v1',
        'archive_sha256': manifest['archive_sha256'], 'source_candidates': len(tasks),
        'eligible_sources': len(traces), 'summary': group(cells),
        'arms': {arm: group([c for c in cells if c['arm'] == arm]) for arm in arms},
        'trace_summary': {'available': sum(t['available'] for t in traces),
            'dropped_events': sum(t.get('events_dropped', 0) > 0 for t in traces),
            'capture_limit_reached': sum(t.get('capture_limit_reached', False) for t in traces),
            'entrypoint_return_observed': sum(t.get('entrypoint_return_events', 0) > 0 for t in traces),
            'has_value_markers': sum(bool(t.get('marker_occurrences')) for t in traces)},
        'tasks': tasks, 'cells': cells,
        'limitations': [
            'Post hoc development audit; no causal attribution, new efficacy gate or selector fit.',
            'All original candidates and all responses retained; primary report unchanged.',
            'Syntax difference is not semantic correctness; outputs are correlated within bugs.',
            'Return events may occur during exception unwinding; observed_status is authoritative.',
            'Omitted runtime types and values cannot be recovered from marker text.',
            'A full locals slot count does not establish omission; no count of unseen locals is recorded.',
            'Test transitions diagnose observed preservation, not the reason a model chose a patch.',
            'Evaluator outcomes are audit-only and must never enter deployable diagnostic prompts.',
        ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.input)
    save(args.output, result)
    print(json.dumps({k: result[k] for k in ('summary', 'arms', 'trace_summary')}, indent=2))


if __name__ == '__main__':
    main()
