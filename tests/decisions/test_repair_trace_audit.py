"""Audit evidence handling: missing tests, exception exits and complete arm coverage."""
from copy import deepcopy
from pathlib import Path
import json
import ast

import pytest

from vao.analysis.repair_trace_audit import bounded_values, structural_ast, summarize, syntax_id, trace_metrics, transitions


def test_markers_count_occurrences_without_inventing_hidden_types():
    data = {'a': {'omitted': 'object_or_depth_limit'},
        'b': {'items': [{'omitted': 'object_or_depth_limit'}, {'prefix': 'ab', 'length': 3}], 'length': 5},
        'c': {'items': [1, 2], 'length': 2}}
    assert dict(bounded_values(data)) == {'omitted:object_or_depth_limit': 2,
        'shortened_string': 1, 'shortened_container': 1}


def test_structural_identity_normalizes_empty_generic_metadata_but_not_syntax():
    legacy = ast.parse('def f(x): return x').body[0]
    legacy._fields = tuple(name for name in legacy._fields if name != 'type_params')
    modern = deepcopy(legacy)
    modern._fields = (*modern._fields, 'type_params')
    modern.type_params = []
    assert structural_ast(legacy) == structural_ast(modern)
    modern.type_params = [ast.Name(id='T', ctx=ast.Load())]
    assert structural_ast(legacy) != structural_ast(modern)
    assert syntax_id({'a.py': 'x=1'}) != syntax_id({'a.py': 'x=True'})
    assert syntax_id({'a.py': 'x=1'}) == syntax_id({'a.py': '# comment\nx = 1\n'})


def test_missing_evaluation_is_not_a_regression_and_case_order_is_irrelevant():
    original = {'cases': [{'id': 'a', 'passed': True}, {'id': 'b', 'passed': False}]}
    current = {'cases': [{'id': 'b', 'passed': True}, {'id': 'a', 'passed': False}]}
    assert transitions(original, None) is None
    assert transitions(original, current) == {'corrected': ['b'], 'regressed': ['a'],
        'still_failed': [], 'preserved_passes': []}
    with pytest.raises(ValueError, match='identities'):
        transitions(original, {'cases': [{'id': 'a', 'passed': True}]})
    with pytest.raises(ValueError, match='identities'):
        transitions(original, {'cases': original['cases'] * 2})


def test_return_event_does_not_overwrite_exception_status():
    observed = {'status': 'exception', 'exception': 'ValueError'}
    task = {'public': {'entrypoint': {'module': 'solution', 'function': 'solve'}},
        'diagnostic': {'available': True, 'case_id': 'test', 'untraced_observation': observed,
            'trace_result': {'observed': observed, 'trace': {'events': [
                {'file': 'solution.py', 'function': 'solve', 'line': 2, 'event': 'return', 'returned': None, 'locals': {}}],
                'events_seen': 2, 'events_dropped': 1, 'capture_limit_reached': False,
                'intact': True, 'limits': {'locals_per_event': 8}}}}}
    result = trace_metrics(task)
    assert result['entrypoint_return_events'] == 1
    assert result['observed_status'] == 'exception'
    assert result['trace_matches_untraced']
    other = deepcopy(task)
    other['diagnostic']['trace_result']['observed'] = {'status': 'returned', 'value': None}
    assert not trace_metrics(other)['trace_matches_untraced']


def test_terminal_archive_preserves_every_arm_source_and_response(tmp_path):
    source = Path(__file__).resolve().parents[2] / 'experiments/python-repair/checkpoint-environment/results/information-independent-20261026'
    result = summarize(source)
    assert result['source_candidates'] == 12
    assert result['eligible_sources'] == 8
    assert {k: v['observed'] for k, v in result['arms'].items()} == {'focused': 32, 'focused_trace': 32}
    assert {k: v['full_repairs'] for k, v in result['arms'].items()} == {'focused': 12, 'focused_trace': 8}
    assert result['summary']['observed'] == len(result['cells']) == 64
    assert result['summary']['unmeasured_public_transitions'] == 1
    assert result['summary']['false_public_acceptances'] == 4
    assert sum(not t['eligible'] for t in result['tasks']) == 4
    assert result == json.loads((source.parent / 'information-independent-posthoc-20261026/audit.json').read_text())
    # No extraction or candidate execution; reject changed archive before analysis.
    (tmp_path / 'evidence-manifest.json').write_bytes((source / 'evidence-manifest.json').read_bytes())
    (tmp_path / 'evidence.zip').write_bytes((source / 'evidence.zip').read_bytes() + b'tamper')
    with pytest.raises(ValueError, match='Archive hash'):
        summarize(tmp_path)
