"""Check checkpoint identity, matched interventions, oracle boundaries and OS isolation."""

import json
from pathlib import Path
import sys

import pytest

from vao.repair.environment import RepairRun, RepairTask, audit_run, canonical, validate_files
from vao.repair.verifier import RepairVerifier


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "experiments/python-repair/checkpoint-environment/fixtures/record-normalization"


class StubVerifier:
    """Inject deterministic outcomes to test storage without executing source."""

    def check(self, files, entrypoint, cases):
        passed = files["solution.py"] == "fixed"
        return {"passed": passed, "passed_cases": len(cases) if passed else 0,
                "total_cases": len(cases), "verifier_seconds": .125,
                "cases": [{"id": c["id"], "passed": passed,
                           "observed": {"status": "returned", "value": 0}} for c in cases]}


@pytest.fixture
def task():
    return RepairTask.from_dicts({"schema_version": 1, "task_id": "development/test",
        "instruction": "Return the input", "entrypoint": {"module": "solution", "function": "solve"},
        "files": {"solution.py": "initial"}, "public_cases": [{"id": "public", "args": [1], "expected": 1}],
        "provenance": {"kind": "synthetic_engineering_fixture"}},
        {"cases": [{"id": "EVALUATOR_ONLY_CANARY", "args": [97], "expected": 97}]})


@pytest.fixture
def run(tmp_path, task):
    return RepairRun(tmp_path / "run", task, StubVerifier())


def checkpoint(run, source="partial", parent=None):
    artifact = run.snapshot({"solution.py": source})
    public = run.evaluate(artifact, "public")
    return run.checkpoint(artifact, public, parent)


def test_continue_and_restart_share_feedback_but_restore_different_code(run):
    cp = checkpoint(run)
    requests = {}
    for action, expected in [("continue", "partial"), ("restart", "initial")]:
        branch = run.fork(cp, action, "0.01")
        request = run.request(branch)
        requests[action] = request
        workspace = run.materialize(run.get(branch)["starting_artifact"], action)
        assert (workspace / "solution.py").read_text() == expected
    left = json.loads(requests["continue"]["messages"][1]["content"])
    right = json.loads(requests["restart"]["messages"][1]["content"])
    assert left.pop("files") != right.pop("files")
    assert left == right
    assert requests["continue"]["messages"][0] == requests["restart"]["messages"][0]
    assert requests["continue"]["remaining_budget_usd"] == requests["restart"]["remaining_budget_usd"]
    assert run.artifact(run.get(cp)["artifact"]) == {"solution.py": "partial"}


def test_history_and_evaluator_data_never_enter_solver_requests(run):
    first = checkpoint(run)
    second = checkpoint(run, parent=first)
    run.evaluate(run.get(second)["artifact"], "evaluator")
    one = run.request(run.fork(first, "continue", "0.01"))
    two = run.request(run.fork(second, "continue", "0.01"))
    assert one == two  # Same current state, different histories.
    assert len(run.get(second)["history"]) == 2
    for marker in ("EVALUATOR_ONLY_CANARY", "verifier_seconds", "history", "provenance", "evaluator"):
        assert marker not in canonical(two)


def test_checkpoint_rejects_private_or_wrong_artifact_verification(run):
    other = run.snapshot({"solution.py": "partial"})
    with pytest.raises(ValueError, match="matching public"):
        run.checkpoint(other, run.evaluate(run.initial, "public"))
    with pytest.raises(ValueError, match="matching public"):
        run.checkpoint(other, run.evaluate(other, "evaluator"))


def test_public_pass_terminates_without_consulting_evaluator(run):
    cp = checkpoint(run, "fixed")
    with pytest.raises(ValueError, match="public pass"):
        run.fork(cp, "restart", "0.01")
    with pytest.raises(ValueError, match="terminates"):
        checkpoint(run, parent=cp)


def test_rollback_restores_exact_prior_artifact_and_refuses_overwrite(run):
    first = checkpoint(run, "useful")
    checkpoint(run, "regression", parent=first)
    artifact = run.get(first)["artifact"]
    workspace = run.materialize(artifact, "rollback")
    (workspace / "solution.py").write_text("changed locally")
    assert run.artifact(artifact) == {"solution.py": "useful"}
    with pytest.raises(FileExistsError):
        run.materialize(artifact, "rollback")
    with pytest.raises(ValueError):
        run.materialize(artifact, "../outside")


@pytest.mark.parametrize("name", ["../x.py", "/tmp/x.py", "sub/x.py", "x\\y.py", ".env", "test.txt", "__repair_worker.py"])
def test_workspace_rejects_paths_and_runner_overrides(name):
    with pytest.raises(ValueError):
        validate_files({name: "pass"})


@pytest.mark.parametrize("budget", ["0", "-1", "NaN", "Infinity"])
def test_branch_rejects_invalid_planning_budget(run, budget):
    with pytest.raises(ValueError):
        run.fork(checkpoint(run), "continue", budget)


def test_task_and_store_defend_against_mutation_and_cross_task_objects(run, task, tmp_path):
    public = task.public
    public["files"]["solution.py"] = "mutated"
    assert task.public["files"]["solution.py"] == "initial"
    public = task.public
    public["task_id"] = "different"
    other = RepairRun(tmp_path / "other", RepairTask.from_dicts(public, json.loads(task.evaluator_json)), StubVerifier())
    foreign = run.put(other.get(other.initial))
    with pytest.raises(ValueError, match="another task"):
        run.artifact(foreign)
    with pytest.raises(ValueError, match="editable"):
        run.snapshot({"different.py": "pass"})


def test_audit_detects_object_tampering_missing_refs_and_event_truncation(run):
    checkpoint(run)
    expected = audit_run(run.root)
    (run.root / "completion.json").write_text(json.dumps({"audit": expected}))
    path = run.root / "objects" / (run.initial + ".json")
    original = path.read_bytes()
    path.write_text('{}')
    with pytest.raises(ValueError, match="Corrupt stored"):
        audit_run(run.root)
    path.write_bytes(original)
    path.unlink()
    with pytest.raises(ValueError, match="Missing referenced"):
        audit_run(run.root)
    path.write_bytes(original)
    sorted((run.root / "events").glob("*.json"))[-1].unlink()
    with pytest.raises(ValueError, match="completion"):
        audit_run(run.root)


def test_create_never_reuses_an_existing_run(run, task):
    with pytest.raises(FileExistsError):
        RepairRun(run.root, task, StubVerifier())


def test_completed_run_cannot_execute_or_mutate(run, monkeypatch):
    (run.root / "completion.json").write_text(json.dumps({"audit": audit_run(run.root)}))
    monkeypatch.setattr(run.verifier, "check", lambda *args: pytest.fail("Sealed run executed code"))
    with pytest.raises(ValueError, match="sealed"):
        run.evaluate(run.initial, "public")
    with pytest.raises(ValueError, match="sealed"):
        run.snapshot({"solution.py": "new"})
    with pytest.raises(ValueError, match="sealed"):
        run.materialize(run.initial, "new")


@pytest.mark.parametrize("reference_ok,unstable,eligible", [(True, False, True), (False, False, False), (True, True, False)])
def test_qualification_gate_keeps_rejected_tasks(tmp_path, task, monkeypatch, reference_ok, unstable, eligible):
    from vao.repair import cli
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "task.json").write_text(task.public_json)
    (bundle / "evaluator.json").write_text(task.evaluator_json)
    (bundle / "reference.json").write_text(json.dumps({"solution.py": "fixed"}))

    class Verifier(StubVerifier):
        count = 0

        def preflight(self):
            return {"test_stub": True}

        def check(self, files, entrypoint, cases):
            self.count += 1
            files = {"solution.py": "fixed" if files["solution.py"] == "fixed" and reference_ok else "initial"}
            result = super().check(files, entrypoint, cases)
            if unstable and self.count == 2:
                result["cases"][0]["observed"]["value"] = 2
            return result

    monkeypatch.setattr(cli, "RepairVerifier", Verifier)
    result = cli.qualify(bundle, tmp_path / "qualification")
    assert result["engineering_qualified"] is eligible
    assert not result["evaluation_ready"] and not result["model_results"]
    assert result["api_calls"] == 0
    assert (tmp_path / "qualification/completion.json").exists()
    assert audit_run(tmp_path / "qualification")["status"] == "verified"


def test_source_drift_leaves_run_unsealed(run, monkeypatch):
    from vao.repair import cli
    provenance = cli.source_manifest(BUNDLE)
    monkeypatch.setattr(cli, "source_manifest", lambda bundle: {"sha256": "changed"})
    with pytest.raises(ValueError, match="changed"):
        cli.finish(run, BUNDLE, provenance, {})
    assert not (run.root / "completion.json").exists()


def test_schema_requires_nonempty_suites_and_unambiguous_expectations(task):
    for evaluator in ({"cases": []}, {"cases": [{"id": "x", "args": [], "expected": 1, "raises": "ValueError"}]}):
        with pytest.raises(ValueError):
            RepairTask.from_dicts(task.public, evaluator)


def test_parent_scores_results_instead_of_trusting_candidate_pass_flags(monkeypatch):
    verifier = object.__new__(RepairVerifier)
    monkeypatch.setattr(verifier, "invoke", lambda *args: {"status": "returned", "value": {"passed": True}})
    result = verifier.check({"x.py": "pass"}, {}, [{"id": "x", "args": [], "expected": 1}])
    assert result["passed"] is False
    monkeypatch.setattr(verifier, "invoke", lambda *args: {"status": "returned", "value": True})
    assert not verifier.check({"x.py": "pass"}, {}, [{"id": "x", "args": [], "expected": 1}])["passed"]


def test_unsupported_platform_has_no_unrestricted_fallback(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="sandbox-exec"):
        RepairVerifier()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox integration")
def test_fixture_progress_and_reference_suites_in_real_sandbox():
    task = RepairTask.load(BUNDLE)
    verifier = RepairVerifier()
    assert verifier.preflight()["network_denied"]
    sources = json.loads((BUNDLE / "scripted-attempts.json").read_text())
    counts = [verifier.check(files, task.public["entrypoint"], task.cases("public"))["passed_cases"]
              for files in [task.public["files"], *sources.values()]]
    assert counts == [1, 5, 4]
    reference = json.loads((BUNDLE / "reference.json").read_text())
    assert all(verifier.check(reference, task.public["entrypoint"], task.cases(c))["passed"]
               for c in ("public", "evaluator"))


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox integration")
def test_hidden_expected_answer_is_not_in_child_input_and_timeout_is_recorded():
    verifier = RepairVerifier(timeout=.5)
    # The worker passes only args/kwargs. Inspecting its caller cannot find expectations.
    code = "import inspect\ndef solve():\n return 'expected' in inspect.currentframe().f_back.f_locals['payload']\n"
    result = verifier.check({"solution.py": code}, {"module": "solution", "function": "solve"},
                            [{"id": "evaluator", "args": [], "expected": False}])
    assert result["passed"]
    result = verifier.check({"solution.py": "def solve():\n while True: pass\n"},
                            {"module": "solution", "function": "solve"},
                            [{"id": "loop", "args": [], "expected": 1}])
    assert result["cases"][0]["observed"]["status"] == "timeout"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox integration")
def test_two_file_workspace_imports_and_syntax_errors():
    verifier = RepairVerifier()
    files = {"solution.py": "from helper import answer\ndef solve(): return answer\n", "helper.py": "answer = 42\n"}
    case = [{"id": "answer", "args": [], "expected": 42}]
    assert verifier.check(files, {"module": "solution", "function": "solve"}, case)["passed"]
    result = verifier.check({"solution.py": "def broken("}, {"module": "solution", "function": "solve"}, case)
    assert result["cases"][0]["observed"] == {"status": "load_error", "exception": "SyntaxError"}


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox integration")
@pytest.mark.parametrize("source,status", [
    ("def solve(): return {1, 2}\n", "non_json_output"),
    ("raise TypeError()\ndef solve(): return 1\n", "load_error"),
])
def test_load_and_serialization_errors_cannot_satisfy_expected_exceptions(source, status):
    verifier = RepairVerifier()
    result = verifier.check({"solution.py": source}, {"module": "solution", "function": "solve"},
                            [{"id": "expects_call_error", "args": [], "raises": "TypeError"}])
    assert not result["passed"]
    assert result["cases"][0]["observed"]["status"] == status
