import sys

import pytest

from vao.repair.coverage_worker import Coverage, EVENT_LIMIT, LINE_LIMIT, VERSION
from vao.repair.diagnostics import binding, observe
from vao.repair.spectra import CoverageVerifier, acquire_spectrum, analyze_spectrum, valid_coverage

NATIVE = pytest.mark.skipif(sys.platform != "darwin", reason="OS-isolated candidate execution needs macOS")


def public():
    return {"schema_version": 1, "task_id": "synthetic", "instruction": "Return zero.",
            "files": {"solution.py": "def solve(x):\n    if x:\n        return 1\n    return 0\n"},
            "entrypoint": {"module": "solution", "function": "solve"}, "provenance": {},
            "public_cases": [{"id": "fail", "args": [True], "expected": 0},
                             {"id": "pass", "args": [False], "expected": 0}]}


def coverage(lines, events=None):
    return {"version": VERSION, "lines": [["solution.py", i] for i in lines],
            "line_events": events if events is not None else len(lines), "limit_reached": False,
            "intact": True, "event_limit": EVENT_LIMIT, "line_limit": LINE_LIMIT}


def acquisition():
    p = public()
    rows = []
    for case, value, lines in zip(p["public_cases"], [1, 0], [[2, 3], [2, 4]]):
        observed = {"status": "returned", "value": value}
        rows.append({"id": case["id"], "ordinary": observed, "stored_observed": observed,
                     "stored_passed": value == 0,
                     "coverage_result": {"available": True, "observed": observed, "coverage": coverage(lines)}})
    return {"binding": binding(p, p["files"]), "cases": rows, "additional_executions": 4, "seconds": 1}


def test_exact_ochiai_preserves_all_lines_and_ties():
    result = analyze_spectrum(public(), acquisition())
    assert [r["squared_exact"] for r in result["ranking"]] == [[1, 1], [1, 2], [0, 1]]
    assert result["ranking"][0]["locations"][0]["line"] == 3
    assert result["metrics"]["distinguishes_failing_executed_lines"]
    data = acquisition()
    data["cases"][1]["coverage_result"]["coverage"] = coverage([2, 3, 4])
    result = analyze_spectrum(public(), data)
    assert result["ranking"][0]["rank_min"] == 1
    assert result["ranking"][0]["rank_max"] == 2
    assert not result["metrics"]["distinguishes_failing_executed_lines"]


@pytest.mark.parametrize("change", ["mismatch", "truncated", "disabled", "label"])
def test_incomplete_or_inconsistent_cases_invalidate_whole_spectrum(change):
    data = acquisition()
    row = data["cases"][0]
    if change == "mismatch":
        row["ordinary"] = {"status": "returned", "value": 2}
    elif change == "label":
        row["stored_passed"] = True
    else:
        row["coverage_result"]["coverage"]["limit_reached" if change == "truncated" else "intact"] = change == "truncated"
    result = analyze_spectrum(public(), data)
    assert result["invalid_or_mismatched_cases"] == ["fail"]
    assert result["ranking"] is None and result["metrics"] is None
    assert result["public_cases"] == 2


@pytest.mark.parametrize("lines", [[["other.py", 2]], [["solution.py", 99]], [["solution.py", True]],
                                 [["solution.py", 2], ["solution.py", 2]], [["solution.py", -1]]])
def test_reject_bad_worker_locations(lines):
    data = coverage([2, 3])
    data["lines"] = lines
    assert not valid_coverage(data, public()["files"])


def test_missing_case_cannot_shrink_denominator():
    data = acquisition()
    data["cases"].pop()
    with pytest.raises(ValueError, match="complete public state"):
        analyze_spectrum(public(), data)


def test_event_cap_is_explicit_not_sampled_full_coverage():
    tracer = Coverage(["solution.py"])
    tracer.events = EVENT_LIMIT
    from types import SimpleNamespace
    import os
    frame = SimpleNamespace(f_code=SimpleNamespace(co_filename=os.path.abspath("solution.py")), f_lineno=2)
    tracer(frame, "line", None)
    result = tracer.export(True)
    assert result["limit_reached"] and result["line_events"] == EVENT_LIMIT + 1


@pytest.mark.parametrize("bank", ["public", "generated"])
def test_published_replay_and_archive_integrity(tmp_path, bank):
    import runpy
    import shutil
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    replay = runpy.run_path(str(root / "scripts/audit_repair_spectra.py"))["replay"]
    source = root / f"experiments/python-repair/checkpoint-environment/results/{bank}-spectra-20261029"
    report = replay(source)
    assert report["artifacts"] == report["available"] == 8
    assert report["distinguishes_failing_executed_lines"] == 7
    assert report["additional_executions"] == 96
    if bank == "generated":
        assert report["source_candidates"] == len(report["candidate_inventory"]) == 12
        assert report["no_public_trigger"] == 4
    target = tmp_path / "copy"
    shutil.copytree(source, target)
    (target / "analysis.json").write_text("{}")
    with pytest.raises(ValueError, match="archive changed"):
        replay(target)


def test_generated_source_keeps_twelve_and_uses_only_public_failure_trigger():
    import runpy
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    module = runpy.run_path(str(root / "scripts/audit_repair_spectra.py"))
    rows = module["source_inputs"]("generated")
    assert [r["id"] for r in rows] == list(module["GENERATED_SLUGS"])
    failed = [r for r in rows if not r["stored"]["feedback"]["passed"]]
    assert [r["id"] for r in failed] == list(module["GENERATED_FAILURES"])
    assert len(rows) == 12 and len(failed) == 8
    assert len({r["source_attempt_id"] for r in rows}) == 12
    for row in rows:
        assert set(row) == {"id", "public", "source_attempt_id", "source_artifact", "source_public_result", "stored"}
        assert row["public"]["provenance"] == {"kind": "previously_exposed_model_generated_candidate"}
        assert row["stored"]["binding"] == binding(row["public"], row["public"]["files"])


@NATIVE
def test_native_public_pair_replays_and_does_not_send_labels():
    p = public()
    verifier = CoverageVerifier()
    verifier.preflight()
    stored = observe(p, p["files"], verifier)
    result = analyze_spectrum(p, acquire_spectrum(p, stored, verifier))
    assert result["available"]
    assert result["ranking"][0]["locations"] == [{"file": "solution.py", "line": 3, "failing_covered": 1, "passing_covered": 0}]
    assert result["additional_executions"] == 4
    # Parent _execute sends only the actual input, not expected answers.
    files = {"solution.py": "import sys\ndef solve():\n    frame = sys._getframe()\n    while frame is not None:\n        if 'payload' in frame.f_locals:\n            return sorted(frame.f_locals['payload'])\n        frame = frame.f_back\n    return []\n"}
    r = verifier.coverage(files, p["entrypoint"], {"args": [], "expected": "PRIVATE_SENTINEL"})
    assert r["available"]
    assert r["observed"] == {"status": "returned", "value": ["args", "entrypoint", "kwargs"]}
    assert "PRIVATE_SENTINEL" not in str(r)


@NATIVE
def test_native_two_files_and_disabled_tracing():
    verifier = CoverageVerifier()
    files = {"solution.py": "def solve(x):\n    from helper import double\n    return double(x)\n",
             "helper.py": "def double(x):\n    return 2*x\n"}
    r = verifier.coverage(files, {"module": "solution", "function": "solve"}, {"args": [3]})
    assert r["available"] and r["observed"]["value"] == 6
    assert ["helper.py", 2] in r["coverage"]["lines"]
    files = {"solution.py": "import sys\ndef solve():\n    sys.settrace(None)\n    return 1\n"}
    r = verifier.coverage(files, {"module": "solution", "function": "solve"}, {"args": []})
    assert not r["available"]
