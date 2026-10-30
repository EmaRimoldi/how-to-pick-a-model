"""Distinguish literal copying from wrapper edits without claiming equivalence."""
from vao.analysis.repair_stagnation import classify


def test_edit_classification_keeps_real_helper_changes_and_other_modules():
    entry = {'module': 'solution', 'function': 'solve'}
    source = {'solution.py': 'def helper(x):\n    return x - 1\ndef solve(x):\n    return helper(x)\n'}
    assert classify(source, source, entry) == 'exact_copy'
    comments = {'solution.py': '# commentary\n' + source['solution.py']}
    assert classify(source, comments, entry) == 'format_or_comment_only'
    wrapper = {'solution.py': source['solution.py'].replace('return helper(x)', 'return helper(x) + 1')}
    assert classify(source, wrapper, entry) == 'entrypoint_only_syntax_change'
    helper = {'solution.py': source['solution.py'].replace('x - 1', 'x')}
    assert classify(source, helper, entry) == 'other_syntax_change'
    assert classify(source, {'solution.py': 'def broken('}, entry) == 'unparseable'
    first = {**source, 'second.py': 'def solve(x):\n    return x - 1\n'}
    second = {**source, 'second.py': 'def solve(x):\n    return x\n'}
    assert classify(first, second, entry) == 'other_syntax_change'
