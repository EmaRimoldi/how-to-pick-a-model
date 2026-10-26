"""Check diagnostic information boundaries, matched controls and real traces."""

import json
import sys

import pytest

from vao.repair.diagnostics import acquire, observe, project
from vao.repair.environment import canonical
from vao.repair.trace_worker import compact
from vao.repair.verifier import RepairVerifier


def public_task(code="def solve(x):\n    y = x + 1\n    return y\n"):
    return {"schema_version": 1, "task_id": "engineering/trace", "instruction": "Return x",
            "entrypoint": {"module": "solution", "function": "solve"},
            "files": {"solution.py": code}, "public_cases": [{"id": "public", "args": [2], "expected": 2}],
            "provenance": {"kind": "engineering", "private_metadata_canary": "DO_NOT_PROJECT"}}


class StubVerifier:
    def check(self, files, entrypoint, cases):
        return {"passed": False, "passed_cases": 0, "total_cases": 1, "verifier_seconds": .1,
                "cases": [{"id": cases[0]["id"], "passed": False,
                           "observed": {"status": "returned", "value": 3}}]}

    def invoke(self, *args):
        return {"status": "returned", "value": 3}

    def trace(self, *args):
        return {"available": True, "observed": self.invoke(), "trace": {"events": []}}


def test_controls_keep_exact_core_information_and_no_private_metadata():
    public = public_task()
    verifier = StubVerifier()
    state = observe(public, public["files"], verifier)
    diagnosis = acquire(public, public["files"], state, verifier)
    requests = {arm: project(public, public["files"], state, arm, diagnosis)
                for arm in ("raw", "focused", "focused_trace")}
    payloads = {arm: json.loads(r["messages"][1]["content"]) for arm, r in requests.items()}
    selected = payloads["focused"].pop("focused_public_failure")
    assert selected["case"] == public["public_cases"][0]
    assert payloads["focused_trace"].pop("focused_public_failure") == selected
    assert payloads["focused_trace"].pop("runtime_diagnostic")["available"]
    assert payloads["raw"] == payloads["focused"] == payloads["focused_trace"]
    for r in requests.values():
        assert not r["provider_call_enabled"]
        assert "DO_NOT_PROJECT" not in canonical(r)
        assert "verifier_seconds" not in canonical(r)


def test_changed_workspace_or_private_payload_rejected():
    public = public_task()
    state = observe(public, public["files"], StubVerifier())
    with pytest.raises(ValueError, match="different public state"):
        project(public, {"solution.py": "def solve(x): return x"}, state, "raw")
    public["evaluator_cases"] = [{"id": "SECRET", "args": [99], "expected": 99}]
    with pytest.raises(ValueError, match="public task schema"):
        observe(public, public["files"], StubVerifier())


def test_public_pass_cannot_trigger_a_probe_even_if_hidden_tests_would_fail(monkeypatch):
    public = public_task()
    verifier = StubVerifier()
    state = observe(public, public["files"], verifier)
    state["feedback"].update({"passed": True, "passed_cases": 1})
    state["feedback"]["cases"][0]["passed"] = True
    monkeypatch.setattr(verifier, "trace", lambda *a: pytest.fail("No public failure"))
    monkeypatch.setattr(verifier, "invoke", lambda *a: pytest.fail("No public failure"))
    result = acquire(public, public["files"], state, verifier)
    assert result["reason"] == "no_public_failure" and result["additional_executions"] == 0


def test_observation_mismatch_is_preserved_without_sending_trace(monkeypatch):
    public = public_task()
    verifier = StubVerifier()
    state = observe(public, public["files"], verifier)
    monkeypatch.setattr(verifier, "trace", lambda *a: {"available": True,
        "observed": {"status": "returned", "value": 4}, "trace": {"events": ["MISMATCH_CANARY"]}})
    diagnostic = acquire(public, public["files"], state, verifier)
    assert not diagnostic["available"] and diagnostic["additional_executions"] == 2
    result = project(public, public["files"], state, "focused_trace", diagnostic)
    assert "MISMATCH_CANARY" not in canonical(result)


def test_trace_compaction_never_uses_candidate_repr_or_container_overrides():
    class Hostile(list):
        def __repr__(self):
            raise AssertionError("repr executed")

        def __getitem__(self, index):
            raise AssertionError("getitem executed")

    assert compact(Hostile()) == {"omitted": "object_or_depth_limit"}
    recursive = []
    recursive.append(recursive)
    assert "depth_limit" in canonical(compact(recursive))
    assert compact(2 ** 1000) == {"omitted": "large_integer"}
    assert compact(float("nan")) == {"omitted": "nonfinite_float"}


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox integration")
def test_real_trace_captures_intermediate_values_and_preserves_result():
    public = public_task()
    verifier = RepairVerifier()
    state = observe(public, public["files"], verifier)
    diagnosis = acquire(public, public["files"], state, verifier)
    assert diagnosis["available"]
    trace = diagnosis["trace_result"]["trace"]
    assert any(e["locals"].get("y") == 3 for e in trace["events"])
    assert all(e["file"] == "solution.py" for e in trace["events"])
    assert diagnosis["trace_result"]["observed"] == {"status": "returned", "value": 3}


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox integration")
def test_real_trace_never_receives_expected_answers_and_records_exceptions():
    verifier = RepairVerifier()
    source = "import inspect\ndef solve(x):\n    assert 'expected' not in inspect.currentframe().f_back.f_locals['payload']\n    raise ValueError('not traced as a message')\n"
    result = verifier.trace({"solution.py": source}, {"module": "solution", "function": "solve"},
                            {"args": [2], "expected": "EVALUATOR_SENTINEL"})
    assert result["available"] and result["observed"] == {"status": "exception", "exception": "ValueError"}
    assert any(e.get("exception") == "ValueError" for e in result["trace"]["events"])
    assert "EVALUATOR_SENTINEL" not in canonical(result)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox integration")
def test_real_trace_limits_and_disabled_instrumentation():
    verifier = RepairVerifier()
    entry = {"module": "solution", "function": "solve"}
    source = "def solve(x):\n    values = ['x' * 10000] * 100\n    for i in range(1000):\n        x += 1\n    return x\n"
    result = verifier.trace({"solution.py": source}, entry, {"args": [0]})
    assert result["observed"] == {"status": "returned", "value": 1000}
    assert len(result["trace"]["events"]) <= 32 and len(canonical(result["trace"]).encode()) <= 16384
    assert result["trace"]["capture_limit_reached"]
    result = verifier.trace({"solution.py": "import sys\ndef solve(x):\n    sys.settrace(None)\n    return x\n"}, entry, {"args": [0]})
    assert not result["available"] and result["reason"] == "tracing_disabled"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox integration")
def test_real_trace_timeout_is_unavailable_not_a_repair_fact():
    verifier = RepairVerifier(timeout=.2)
    result = verifier.trace({"solution.py": "def solve():\n    while True: pass\n"},
                            {"module": "solution", "function": "solve"}, {"args": []})
    assert not result["available"] and result["worker_result"]["status"] == "timeout"
