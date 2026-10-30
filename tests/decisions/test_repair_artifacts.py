from vao.analysis.repair_artifacts import same_ast


def test_comment_and_layout_changes_are_not_new_program_structure():
    before = {'solution.py': '# comment\ndef solve(x):\n    return x + 1\n'}
    after = {'solution.py': 'def solve(x): return (x + 1)\n'}
    assert same_ast(before, after) is True
    assert same_ast(before, {'solution.py': 'def solve(x): return x + 2\n'}) is False


def test_syntax_errors_are_uncomparable_not_no_ops():
    assert same_ast({'solution.py': 'def solve('}, {'solution.py': 'def solve('}) is None
    assert same_ast({'one.py': 'x=1'}, {'two.py': 'x=1'}) is False
