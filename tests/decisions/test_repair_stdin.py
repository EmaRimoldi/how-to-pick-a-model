"""Whole-program byte semantics and isolation, using synthetic engineering cases."""
import base64
import sys

import pytest

from vao.repair.stdin_verifier import StdinVerifier, compare_stdout

NATIVE = pytest.mark.skipif(sys.platform != 'darwin', reason='Native stdin backend needs macOS')


def observed(raw, code=0, status='exited'):
    return {'status': status, 'returncode': code, 'stdout_b64': base64.b64encode(raw).decode()}


def test_explicit_comparator_does_not_coerce_numbers_or_success_status():
    assert compare_stdout(observed(b'1 \t2\n'), b'1 2', mode='ascii_whitespace_tokens')
    assert not compare_stdout(observed(b'1 \t2\n'), b'1 2', mode='exact_bytes')
    assert not compare_stdout(observed(b'1.000000'), b'1', mode='ascii_whitespace_tokens')
    assert not compare_stdout(observed(b'NaN'), b'nan', mode='ascii_whitespace_tokens')
    assert not compare_stdout(observed(b'correct', 1), b'correct', mode='exact_bytes')
    assert not compare_stdout(observed(b'correct', 0, 'timeout'), b'correct', mode='exact_bytes')
    assert not compare_stdout({'status': 'exited', 'returncode': 0, 'stdout_b64': '!'}, b'', mode='exact_bytes')
    with pytest.raises(ValueError):
        compare_stdout(observed(b'1'), b'1', mode='float_coercion')


@NATIVE
def test_native_isolation_preflight():
    assert StdinVerifier().preflight()['source_writes_denied']


@NATIVE
def test_native_stdin_bytes_and_main_semantics_preserved():
    source = b'import os, sys\nassert __name__ == "__main__"\nassert len(sys.argv) == 1 and os.path.basename(sys.argv[0]) == "main.py"\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n'
    data = b' \t\r\n\x00\xfftrailing space '
    v = StdinVerifier()
    regular = v.invoke(source, data)
    covered = v.invoke(source, data, coverage=True)
    assert compare_stdout(regular['observed'], data, mode='exact_bytes')
    assert covered['observed'] == regular['observed']
    assert covered['coverage']['available']
    assert covered['coverage']['data']['version'] == 'stdin-main-line-coverage-v1'
    assert ['main.py', 4] in covered['coverage']['data']['lines']
    assert regular['candidate_executions'] == covered['candidate_executions'] == 1


@NATIVE
def test_native_fresh_state_and_system_exit_are_real_program_semantics():
    source = b'import os, sys\nfrom pathlib import Path\np=Path(os.environ["TMPDIR"])/"state"\nprint(p.exists())\np.write_text("created")\nsys.exit(0)\n'
    v = StdinVerifier()
    for _ in range(2):
        assert compare_stdout(v.invoke(source, b'')['observed'], b'False\n', mode='exact_bytes')
    failed = v.invoke(b'print("right")\nraise ValueError("broken")\n', b'')
    assert not compare_stdout(failed['observed'], b'right\n', mode='exact_bytes')
    assert b'ValueError' in base64.b64decode(failed['observed']['stderr_b64'])


@NATIVE
def test_native_time_output_and_coverage_failures_remain_failures():
    v = StdinVerifier(timeout=0.5)
    assert v.invoke(b'while True: pass\n', b'')['observed']['status'] == 'timeout'
    assert v.invoke(b'import sys\nsys.stdout.write("x"*1000000)\n', b'')['observed']['status'] == 'output_limit'
    disabled = StdinVerifier().invoke(b'import sys\nsys.settrace(None)\nprint(1)\n', b'', coverage=True)
    assert compare_stdout(disabled['observed'], b'1\n', mode='exact_bytes')
    assert not disabled['coverage']['available']


@NATIVE
def test_native_bounds_reject_before_starting_program():
    v = StdinVerifier()
    for source, data in [(b'', b''), (b'x'*262145, b''), (b'pass', b'x'*65537), ('pass', b'')]:
        with pytest.raises(ValueError):
            v.invoke(source, data)
