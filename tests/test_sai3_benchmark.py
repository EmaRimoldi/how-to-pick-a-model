from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "experiments" / "four-term-packed-validation" / "sai3.py"
SPEC = importlib.util.spec_from_file_location("sai3", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
SAI3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SAI3
SPEC.loader.exec_module(SAI3)

RUNNER_PATH = ROOT / "experiments" / "four-term-packed-validation" / "scripts" / "run_sai3_scout.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("run_sai3_scout", RUNNER_PATH)
assert RUNNER_SPEC is not None and RUNNER_SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)

DESIGN_PATH = (
    ROOT
    / "experiments"
    / "four-term-packed-validation"
    / "scripts"
    / "generate_sai3_schedule_design.py"
)
DESIGN_SPEC = importlib.util.spec_from_file_location("generate_sai3_schedule_design", DESIGN_PATH)
assert DESIGN_SPEC is not None and DESIGN_SPEC.loader is not None
DESIGN = importlib.util.module_from_spec(DESIGN_SPEC)
DESIGN_SPEC.loader.exec_module(DESIGN)

SCHEDULE_PATH = ROOT / "experiments" / "four-term-packed-validation" / "scripts" / "run_sai3_schedule.py"
SCHEDULE_SPEC = importlib.util.spec_from_file_location("run_sai3_schedule", SCHEDULE_PATH)
assert SCHEDULE_SPEC is not None and SCHEDULE_SPEC.loader is not None
SCHEDULE = importlib.util.module_from_spec(SCHEDULE_SPEC)
SCHEDULE_SPEC.loader.exec_module(SCHEDULE)

INVERSE_ANALYSIS_PATH = (
    ROOT
    / "experiments"
    / "four-term-packed-validation"
    / "scripts"
    / "analyze_sai3_inverse_share.py"
)
INVERSE_ANALYSIS_SPEC = importlib.util.spec_from_file_location(
    "analyze_sai3_inverse_share", INVERSE_ANALYSIS_PATH
)
assert INVERSE_ANALYSIS_SPEC is not None and INVERSE_ANALYSIS_SPEC.loader is not None
INVERSE_ANALYSIS = importlib.util.module_from_spec(INVERSE_ANALYSIS_SPEC)
INVERSE_ANALYSIS_SPEC.loader.exec_module(INVERSE_ANALYSIS)

FOUR_TERM_ANALYSIS_PATH = (
    ROOT
    / "experiments"
    / "four-term-packed-validation"
    / "scripts"
    / "analyze_sai3_four_term.py"
)
FOUR_TERM_ANALYSIS_SPEC = importlib.util.spec_from_file_location(
    "analyze_sai3_four_term", FOUR_TERM_ANALYSIS_PATH
)
assert FOUR_TERM_ANALYSIS_SPEC is not None and FOUR_TERM_ANALYSIS_SPEC.loader is not None
FOUR_TERM_ANALYSIS = importlib.util.module_from_spec(FOUR_TERM_ANALYSIS_SPEC)
FOUR_TERM_ANALYSIS_SPEC.loader.exec_module(FOUR_TERM_ANALYSIS)


def test_reference_and_wrong_shards_are_separated() -> None:
    for mode in range(3):
        task = SAI3.generate_task(seed=17, split="development", mode=mode, index=0)
        assert SAI3.verify_code(task, task["references"][mode])["passed"]
        for shard in range(3):
            if shard != mode:
                assert not SAI3.verify_code(task, task["references"][shard])["passed"]


def test_reference_audit_passes_generator_gate() -> None:
    for difficulty in ("scalar", "list"):
        tasks = SAI3.generate_tasks(seed=23, split="development", tasks_per_mode=4, difficulty=difficulty)
        audits = [SAI3.audit_task(task, deterministic_reruns=3) for task in tasks]
        assert all(audit["gate_passed"] for audit in audits)
        assert min(audit["mutation_score"] for audit in audits) >= 0.95


def test_difficulty_variants_have_distinct_payload_contracts() -> None:
    scalar = SAI3.generate_task(seed=29, split="development", mode=0, index=0, difficulty="scalar")
    list_task = SAI3.generate_task(seed=29, split="development", mode=0, index=0, difficulty="list")
    assert "payload['value']" in scalar["prompts"][0]
    assert "payload['values']" in list_task["prompts"][0]
    assert SAI3.verify_code(scalar, scalar["references"][0])["passed"]
    assert SAI3.verify_code(list_task, list_task["references"][0])["passed"]


def test_task_randomness_is_disjoint_across_splits() -> None:
    tasks = [
        SAI3.generate_task(seed=29, split=split, mode=0, index=0, difficulty="scalar")
        for split in ("development", "calibration", "confirmation")
    ]
    assert len({task["task_seed"] for task in tasks}) == 3
    assert len({task["contracts"][0]["method"] for task in tasks}) == 3


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


def test_vllm_slot_seeds_are_stable_and_unique() -> None:
    seeds = {
        RUNNER.sampling_seed(17, "model", f"task-{task}", shard, attempt)
        for task in range(3)
        for shard in range(3)
        for attempt in range(8)
    }
    assert len(seeds) == 72
    assert RUNNER.sampling_seed(17, "model", "task-1", 2, 3) == RUNNER.sampling_seed(
        17, "model", "task-1", 2, 3
    )


def test_balanced_task_selection_supports_disjoint_shards() -> None:
    tasks = SAI3.generate_tasks(seed=37, split="development", tasks_per_mode=6)
    first, first_counts = RUNNER.select_balanced_tasks(tasks, tasks_per_mode=2, task_offset_per_mode=0)
    second, second_counts = RUNNER.select_balanced_tasks(tasks, tasks_per_mode=2, task_offset_per_mode=2)
    assert first_counts == {0: 2, 1: 2, 2: 2}
    assert second_counts == {0: 2, 1: 2, 2: 2}
    assert {task["task_id"] for task in first}.isdisjoint(task["task_id"] for task in second)


def test_controlled_channel_terms_match_known_special_cases() -> None:
    assert math.isclose(DESIGN.information(1.0 / 3.0), 0.0, abs_tol=1e-12)
    for alpha in (0.6, 0.8):
        assert math.isclose(DESIGN.mismatch(alpha, "matched"), 0.0, abs_tol=1e-12)
        assert math.isclose(DESIGN.mismatch(alpha, "prior"), DESIGN.information(alpha), rel_tol=1e-12)
        assert DESIGN.mismatch(alpha, "half_anti") > DESIGN.mismatch(alpha, "prior")


def test_schedule_design_is_balanced_and_reuses_no_trajectory_seed() -> None:
    tasks = SAI3.generate_tasks(seed=41, split="confirmation", tasks_per_mode=1)
    rows = DESIGN.four_term_rows(tasks, [0.8], ["matched", "prior"], repetitions=2, seed=43)
    assert len(rows) == 3 * (2 + 2 * 3 * 2)
    assert len({row["trajectory_id"] for row in rows}) == len(rows)
    assert len({row["schedule_seed"] for row in rows}) == len(rows)
    for row in rows:
        assert math.isclose(sum(row["q"]), 1.0, abs_tol=1e-12)
        assert math.isclose(row["q_true"], row["q"][row["mode"]], abs_tol=1e-12)


def test_schedule_generation_seeds_are_unique_per_physical_slot() -> None:
    seeds = {
        SCHEDULE.generation_seed(47, "model", f"trajectory-{trajectory}", slot)
        for trajectory in range(5)
        for slot in range(32)
    }
    assert len(seeds) == 160


def test_inverse_share_fixed_effect_fit_recovers_unit_slope() -> None:
    cells = []
    for model, scale in (("small", 1.5), ("large", 2.25)):
        for mode, mode_scale in enumerate((1.0, 1.4, 2.0)):
            for q_true in (0.1, 0.2, 0.5, 0.8, 1.0):
                cells.append((model, mode, q_true, scale * mode_scale / q_true))
    assert math.isclose(INVERSE_ANALYSIS.fixed_effect_slope(cells), 1.0, abs_tol=1e-12)


def test_four_term_analysis_closes_on_exact_packed_cells() -> None:
    baseline_model = "baseline"
    deployed_model = "deployed"
    costs = {baseline_model: 2.0, deployed_model: 1.0}
    scales = {
        (baseline_model, 0): 2.0,
        (baseline_model, 1): 3.0,
        (baseline_model, 2): 4.0,
        (deployed_model, 0): 1.0,
        (deployed_model, 1): 1.5,
        (deployed_model, 2): 2.0,
    }
    alpha = 0.8
    allocation_name = "half_anti"
    condition = f"alpha={alpha:.8f}|allocation={allocation_name}"
    cells = {}
    for mode in range(3):
        cells[(baseline_model, "baseline_prior", mode, -1)] = scales[(baseline_model, mode)] / (1.0 / 3.0)
        for z in range(3):
            q = DESIGN.allocation(alpha, z, allocation_name)
            cells[(deployed_model, condition, mode, z)] = scales[(deployed_model, mode)] / q[mode]
    observed = FOUR_TERM_ANALYSIS.observed_delta(
        cells, costs, baseline_model, deployed_model, condition, alpha
    )
    terms = FOUR_TERM_ANALYSIS.predicted_terms(
        scales,
        costs,
        baseline_model,
        deployed_model,
        DESIGN.information(alpha),
        DESIGN.mismatch(alpha, allocation_name),
    )
    assert math.isclose(observed, terms["predicted_delta_nats"], abs_tol=1e-12)
