"""Guard retrospective joins and the distinction between edits and evidence."""
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / (
    'experiments/python-repair/checkpoint-environment/results/'
    'spectrum-posthoc-20261030/reproduce.py'
)
spec = importlib.util.spec_from_file_location('spectrum_posthoc_audit', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_reordered_outcomes_join_by_identity_and_preserve_expected_exception():
    definitions = [{'id': 'a', 'raises': 'ValueError'}, {'id': 'b', 'expected': 2}]
    results = {'total_cases': 2, 'passed_cases': 1, 'passed': False, 'cases': [
        {'id': 'b', 'passed': False, 'observed': {'status': 'returned', 'value': 3}},
        {'id': 'a', 'passed': True, 'observed': {'status': 'exception', 'exception': 'ValueError'}}]}
    baseline = {'a': {'passed': False}, 'b': {'passed': True}}
    joined = audit.join_cases(definitions, results, baseline)
    assert joined[0]['id'] == 'a' and joined[0]['passed']
    assert joined[0]['raises'] == 'ValueError' and not joined[0]['baseline_passed']
    assert joined[1]['expected'] == 2 and joined[1]['observed']['value'] == 3
    assert joined[1]['baseline_passed'] and not joined[1]['passed']


def test_duplicate_case_identity_is_rejected():
    with pytest.raises(ValueError, match='Duplicate case ID'):
        audit.case_map([{'id': 'same'}, {'id': 'same'}])


def test_missing_or_mismatched_case_cannot_be_invented_as_failure():
    assert audit.join_cases([{'id': 'a'}], None) is None
    results = {'total_cases': 1, 'passed_cases': 0, 'passed': False,
               'cases': [{'id': 'wrong', 'passed': False}]}
    with pytest.raises(ValueError, match='Case identities differ'):
        audit.join_cases([{'id': 'a'}], results)


def test_source_insertion_does_not_claim_a_ranked_old_line_was_edited():
    change = audit.edits({'x.py': 'a = 1\nreturn_value = a\n'},
                         {'x.py': 'a = 1\nb = 2\nreturn_value = a\n'})[0]
    assert change['changed_old_lines'] == []
    assert change['insertions'] == [{'after_old_line': 1, 'new_lines': [2]}]
    assert not change['ast_identical']


def test_comments_do_not_count_as_semantic_ast_changes_and_syntax_is_unknown():
    assert audit.ast_same('a = 1\n', '# revised comment\na=1\n') is True
    assert audit.ast_same('a = 1\n', 'a = 1\n}') is None
