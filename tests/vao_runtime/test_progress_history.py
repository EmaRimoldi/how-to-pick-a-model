"""Exercise exhaustive checking, bounded parsing, and information boundaries offline."""

import json
import subprocess
import sys

import pytest

from vao.decisions.progress_history import (
    DOMAIN, Attempt, Task, branch_pair, checkpoint, development_tasks,
    interpret, parse_candidate, verify,
)


def test_reference_agrees_on_every_input_and_wrong_programs_fail():
    for task in development_tasks(count=32):
        tree = parse_candidate(task.reference_expression())
        # Independent computation of each case, including both branch regions.
        expected = [((task.a*x + task.b*y + task.c) if (x+y) % task.modulus < task.threshold
                     else ((x ^ task.mask) + task.e*y + task.f)) % 16 for x, y in DOMAIN]
        assert [interpret(tree, x, y) for x, y in DOMAIN] == expected
        assert verify(task, task.reference_expression())["passed"]
        wrong = verify(task, "31")
        assert wrong["failed_inputs"] == 256  # No automatic modulo repair.
        assert wrong["first_counterexample"] == {
            "x": 0, "y": 0, "expected": expected[0], "actual": 31}


def test_single_error_is_detected_even_when_all_other_inputs_pass():
    task = development_tasks()[0]
    expression = task.reference_expression()
    one_error = f"31 if x+y==30 else ({expression})"
    checked = verify(task, one_error)
    assert checked["failed_inputs"] == 1
    assert checked["first_counterexample"]["x"] == checked["first_counterexample"]["y"] == 15
    assert not checked["passed"]


@pytest.mark.parametrize("source", [
    "__import__('os').system('false')", "x.real", "[x for x in range(9)]", "lambda: x",
    "x**31", "x<<31", "x%y", "x%0", "True", "x<y", "True+1", "(x<y)+1",
    "1 if x else 2", "1 if 0<x<3 else 2", "32", "-1", "x/y", "", "z",
    "0 if x==x else __import__('os')", "("*1000 + "x" + ")"*1000,
    "x+"*100 + "x", "x"*2049,
])
def test_untrusted_constructs_rejected_including_unreachable_branches(source):
    checked = verify(development_tasks(count=1)[0], source)
    assert checked["status"] == "format_error"
    assert checked["failed_inputs"] is None
    assert not checked["passed"]


def test_generation_reproducible_and_semantic_identity_is_the_group_key():
    tasks = development_tasks(count=32)
    assert tasks == development_tasks(count=32)
    assert tasks != development_tasks(seed=7, count=32)
    assert len({t.task_id for t in tasks}) == 32
    # Both arms implement the same function; changing the condition changes no answer.
    t1 = Task(3, 1, 1, 2, 3, 0, 2, 3)
    t2 = Task(7, 4, 1, 2, 3, 0, 2, 3)
    assert t1.specification() != t2.specification()
    assert t1.task_id == t2.task_id


def test_branch_prompts_only_differ_by_current_candidate():
    task = development_tasks(count=1)[0]
    state = checkpoint(task, [Attempt("0", 150), Attempt("x", 200)], 1000)
    pair = branch_pair(state)
    keep, fresh = pair["continue"], pair["restart"]
    assert keep["checkpoint_id"] == fresh["checkpoint_id"] == state["checkpoint_id"]
    assert keep["remaining_nanousd"] == fresh["remaining_nanousd"] == 650
    assert keep["messages"][0] == fresh["messages"][0]
    payload = json.loads(keep["messages"][1]["content"])
    assert payload.pop("current_candidate") == "x"
    assert payload == json.loads(fresh["messages"][1]["content"])
    assert set(payload) == {"specification", "feedback"}
    assert payload["feedback"] == verify(task, "x")
    assert task.reference_expression() not in json.dumps(pair)
    assert "progress_history" not in json.dumps(pair)
    assert "task_id" not in json.dumps(pair)


def test_history_increment_cannot_change_current_state_or_solver_prompt():
    task = development_tasks(count=1)[0]
    left = checkpoint(task, [Attempt("0", 150), Attempt("x", 200)], 1000)
    right = checkpoint(task, [Attempt("31", 150), Attempt("x", 200)], 1000)
    assert left["baseline"] == right["baseline"]
    assert left["progress_history"] != right["progress_history"]
    assert left["checkpoint_id"] != right["checkpoint_id"]
    for action in ("continue", "restart"):
        assert branch_pair(left)[action]["messages"] == branch_pair(right)[action]["messages"]
    assert set(left["progress_history"][0]) == {"status", "failed_inputs", "cost_nanousd"}


def test_success_budget_and_invalid_cost_cannot_form_failed_checkpoint():
    task = development_tasks(count=1)[0]
    for attempts, budget in [([], 100), ([Attempt("x", -1)], 100),
                             ([Attempt("x", 100)], 100), ([Attempt("x", True)], 100),
                             ([Attempt(task.reference_expression(), 1), Attempt("x", 1)], 100)]:
        with pytest.raises(ValueError):
            checkpoint(task, attempts, budget)


def test_offline_cli_has_no_live_mode_and_does_not_overwrite(tmp_path):
    command = [sys.executable, "scripts/prepare_progress_history.py"]
    plan = json.loads(subprocess.check_output(command, text=True))
    assert plan["api_calls"] == 0 and not plan["live_collection_implemented"]
    output = tmp_path / "development"
    summary = json.loads(subprocess.check_output(command + ["--output", str(output)], text=True))
    assert summary["reference_checks"] == 2048
    assert summary["model_responses"] == summary["actual_api_cost_usd"] == 0
    fixtures = json.loads((output / "fixtures.json").read_text())
    assert all(row["split"] == "development" for row in fixtures)
    original = (output / "fixtures.json").read_bytes()
    retry = subprocess.run(command + ["--output", str(output)], capture_output=True)
    assert retry.returncode != 0
    assert (output / "fixtures.json").read_bytes() == original
    assert subprocess.run(command + ["--live"], capture_output=True).returncode != 0
