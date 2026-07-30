from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "experiments" / "four-term-packed-validation" / "sai3.py"
SPEC = importlib.util.spec_from_file_location("sai3", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
SAI3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SAI3
SPEC.loader.exec_module(SAI3)


def test_reference_and_wrong_shards_are_separated() -> None:
    for mode in range(3):
        task = SAI3.generate_task(seed=17, split="development", mode=mode, index=0)
        assert SAI3.verify_code(task, task["references"][mode])["passed"]
        for shard in range(3):
            if shard != mode:
                assert not SAI3.verify_code(task, task["references"][shard])["passed"]


def test_reference_audit_passes_generator_gate() -> None:
    tasks = SAI3.generate_tasks(seed=23, split="development", tasks_per_mode=4)
    audits = [SAI3.audit_task(task, deterministic_reruns=3) for task in tasks]
    assert all(audit["gate_passed"] for audit in audits)
    assert min(audit["mutation_score"] for audit in audits) >= 0.95


def test_reflection_and_multi_contract_code_is_rejected() -> None:
    reflection = """\
def adapt(client, payload):
    method = getattr(client, payload['method'])
    return method(value=payload['value'])
"""
    multi_contract = """\
def adapt(client, payload):
    try:
        return client.first(value=payload['value'])
    except AttributeError:
        return client.second(value=payload['value'])
"""
    assert not SAI3.check_policy(reflection).ok
    assert not SAI3.check_policy(multi_contract).ok


def test_unbounded_or_expensive_constructs_are_rejected() -> None:
    loop = """\
def adapt(client, payload):
    while True:
        client.method(value=payload['value'])
"""
    power = """\
def adapt(client, payload):
    value = 999999 ** 999999
    return client.method(value=value)
"""
    assert not SAI3.check_policy(loop).ok
    assert not SAI3.check_policy(power).ok


def test_fenced_completion_parser() -> None:
    task = SAI3.generate_task(seed=31, split="development", mode=1, index=2)
    completion = f"Here is the implementation:\n```python\n{task['references'][1]}\n```\n"
    assert SAI3.verify_completion(task, completion)["passed"]
