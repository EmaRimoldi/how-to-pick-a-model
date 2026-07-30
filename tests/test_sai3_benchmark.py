from __future__ import annotations

import importlib.util
import json
import math
import sys
from fractions import Fraction
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

CONFIRMATION_AUDIT_PATH = (
    ROOT
    / "experiments"
    / "four-term-packed-validation"
    / "scripts"
    / "audit_sai3_confirmation.py"
)
CONFIRMATION_AUDIT_SPEC = importlib.util.spec_from_file_location(
    "audit_sai3_confirmation", CONFIRMATION_AUDIT_PATH
)
assert CONFIRMATION_AUDIT_SPEC is not None and CONFIRMATION_AUDIT_SPEC.loader is not None
CONFIRMATION_AUDIT = importlib.util.module_from_spec(CONFIRMATION_AUDIT_SPEC)
CONFIRMATION_AUDIT_SPEC.loader.exec_module(CONFIRMATION_AUDIT)

PROVENANCE_PATH = (
    ROOT / "experiments" / "four-term-packed-validation" / "runtime_provenance.py"
)
PROVENANCE_SPEC = importlib.util.spec_from_file_location("runtime_provenance", PROVENANCE_PATH)
assert PROVENANCE_SPEC is not None and PROVENANCE_SPEC.loader is not None
PROVENANCE = importlib.util.module_from_spec(PROVENANCE_SPEC)
PROVENANCE_SPEC.loader.exec_module(PROVENANCE)

CALIBRATION_ANALYSIS_PATH = (
    ROOT
    / "experiments"
    / "four-term-packed-validation"
    / "scripts"
    / "analyze_sai3_calibration.py"
)
CALIBRATION_ANALYSIS_SPEC = importlib.util.spec_from_file_location(
    "analyze_sai3_calibration", CALIBRATION_ANALYSIS_PATH
)
assert CALIBRATION_ANALYSIS_SPEC is not None and CALIBRATION_ANALYSIS_SPEC.loader is not None
CALIBRATION_ANALYSIS = importlib.util.module_from_spec(CALIBRATION_ANALYSIS_SPEC)
CALIBRATION_ANALYSIS_SPEC.loader.exec_module(CALIBRATION_ANALYSIS)

PLOT_PATH = (
    ROOT / "experiments" / "four-term-packed-validation" / "scripts" / "plot_sai3_four_term.py"
)
PLOT_SPEC = importlib.util.spec_from_file_location("plot_sai3_four_term", PLOT_PATH)
assert PLOT_SPEC is not None and PLOT_SPEC.loader is not None
PLOT = importlib.util.module_from_spec(PLOT_SPEC)
PLOT_SPEC.loader.exec_module(PLOT)


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


def test_numeric_postprocessing_has_explicit_precedence() -> None:
    for index in range(32):
        task = SAI3.generate_task(seed=29, split="development", mode=0, index=index, difficulty="scalar")
        if task["normalization"]["kind"] == "integer_offset":
            prompt = task["prompts"][0]
            assert "set `base`" in prompt
            assert "then set `value`" in prompt
            return
    raise AssertionError("seed did not generate an integer_offset task")


def test_scalar_generator_balances_task_strata_within_mode() -> None:
    tasks = SAI3.generate_tasks(seed=31, split="calibration", tasks_per_mode=12, difficulty="scalar")
    for mode in range(3):
        counts = {}
        for task in tasks:
            if task["mode"] == mode:
                counts[task["task_stratum"]] = counts.get(task["task_stratum"], 0) + 1
        assert counts == {
            "collapse_spaces": 3,
            "integer_offset": 3,
            "strip_lower": 3,
            "strip_upper": 3,
        }


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
    assert max(seeds) > 2**32
    assert RUNNER.sampling_seed(17, "model", "task-1", 2, 3) == RUNNER.sampling_seed(
        17, "model", "task-1", 2, 3
    )


def test_tokenizer_fingerprint_covers_vocab_and_chat_protocol() -> None:
    class Tokenizer:
        special_tokens_map = {"eos_token": "<eos>"}

        def __init__(self, chat_template: str) -> None:
            self.chat_template = chat_template

        def get_vocab(self) -> dict[str, int]:
            return {"b": 2, "a": 1}

    first = PROVENANCE.tokenizer_fingerprint(Tokenizer("template-a"))
    assert first == PROVENANCE.tokenizer_fingerprint(Tokenizer("template-a"))
    assert first != PROVENANCE.tokenizer_fingerprint(Tokenizer("template-b"))


def test_balanced_task_selection_supports_disjoint_shards() -> None:
    tasks = SAI3.generate_tasks(seed=37, split="development", tasks_per_mode=6)
    first, first_counts = RUNNER.select_balanced_tasks(tasks, tasks_per_mode=2, task_offset_per_mode=0)
    second, second_counts = RUNNER.select_balanced_tasks(tasks, tasks_per_mode=2, task_offset_per_mode=2)
    assert first_counts == {0: 2, 1: 2, 2: 2}
    assert second_counts == {0: 2, 1: 2, 2: 2}
    assert {task["task_id"] for task in first}.isdisjoint(task["task_id"] for task in second)


def test_targeted_task_selection_supports_calibration_extensions() -> None:
    tasks = SAI3.generate_tasks(seed=39, split="calibration", tasks_per_mode=4)
    requested = [tasks[0]["task_id"], tasks[5]["task_id"], tasks[10]["task_id"]]
    selected, counts = RUNNER.select_task_ids(tasks, requested)
    assert [task["task_id"] for task in selected] == requested
    assert counts == {0: 1, 1: 1, 2: 1}


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
    assert max(row["schedule_seed"] for row in rows) > 2**32
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
    assert max(seeds) > 2**32


def test_inverse_share_fixed_effect_fit_recovers_unit_slope() -> None:
    cells = []
    for model, scale in (("small", 1.5), ("large", 2.25)):
        for mode, mode_scale in enumerate((1.0, 1.4, 2.0)):
            for q_true in (0.1, 0.2, 0.5, 0.8, 1.0):
                cells.append((model, mode, q_true, scale * mode_scale / q_true))
    assert math.isclose(INVERSE_ANALYSIS.fixed_effect_slope(cells), 1.0, abs_tol=1e-12)


def test_four_term_statistical_helpers_are_conservative() -> None:
    lower, upper = FOUR_TERM_ANALYSIS.wilson_interval(0, 6144)
    assert lower >= 0.0
    assert 0.0006 < upper < 0.0007
    adjusted = FOUR_TERM_ANALYSIS.holm_adjust({"a": 0.01, "b": 0.04, "c": 0.20, "d": 0.80})
    assert adjusted == {"a": 0.04, "b": 0.12, "c": 0.4, "d": 0.8}


def test_confirmation_share_audit_uses_full_planned_schedule() -> None:
    rows = [
        {
            "model": "model",
            "condition": "condition",
            "q": [0.5, 0.25, 0.25],
            "planned_issued": [64, 32, 32],
        },
        {
            "model": "model",
            "condition": "condition",
            "q": [0.25, 0.5, 0.25],
            "planned_issued": [32, 64, 32],
        },
    ]
    audit = FOUR_TERM_ANALYSIS.planned_share_audit(rows)
    assert len(audit) == 1
    assert audit[0]["max_absolute_planned_share_error"] == 0.0


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


def test_censored_first_passage_uses_geometric_exposure_mle() -> None:
    rows = [
        {
            "design": "four_term",
            "model": "model",
            "condition": "condition",
            "mode": 0,
            "z": 0,
            "task_stratum": "stratum",
            "task_id": "task",
            "total_slots": slots,
            "success": success,
        }
        for slots, success in ((2, True), (3, True), (10, False), (10, False))
    ]
    estimates = FOUR_TERM_ANALYSIS.trajectory_task_means(rows)
    assert list(estimates.values()) == [12.5]


def test_task_aggregation_matches_expected_log_time() -> None:
    task_scales = {
        ("model", 0, "stratum", "easy"): 1.0,
        ("model", 0, "stratum", "hard"): 9.0,
    }
    focused = FOUR_TERM_ANALYSIS.focused_scales(task_scales)
    assert math.isclose(focused[("model", 0)], 3.0)

    task_means = {
        ("model", "condition", 0, 0, "stratum", "easy"): 1.0,
        ("model", "condition", 0, 0, "stratum", "hard"): 9.0,
    }
    cells = FOUR_TERM_ANALYSIS.trajectory_cells(task_means)
    assert math.isclose(cells[("model", "condition", 0, 0)], 3.0)


def test_confirmation_integrity_rejects_wrong_shard_success() -> None:
    audit = FOUR_TERM_ANALYSIS.confirmation_integrity(
        [
            {
                "model": "model",
                "trajectory_id": "trajectory",
                "mode": 1,
                "success": True,
                "censored": False,
                "winning_shard": 2,
                "total_slots": 3,
                "issued": [0, 2, 1],
            }
        ]
    )
    assert audit["wrong_shard_successes"] == 1


def test_confirmation_artifact_audit_checks_slot_accounting(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text('{"task_id":"task"}\n')
    tasks_sha256 = CONFIRMATION_AUDIT.sha256_path(tasks_path)
    design_row = {
        "trajectory_id": "trajectory",
        "task_id": "task",
        "task_stratum": "stratum",
        "mode": 0,
        "condition": "baseline_prior",
        "schedule_seed": 11,
        "q": [1.0, 0.0, 0.0],
    }
    design_path = tmp_path / "design.jsonl"
    design_path.write_text(json.dumps(design_row) + "\n")
    design_sha256 = CONFIRMATION_AUDIT.sha256_path(design_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    trajectory = {
        **design_row,
        "model": "model",
        "success": True,
        "censored": False,
        "total_slots": 1,
        "issued": [1, 0, 0],
        "winning_shard": 0,
    }
    (run_dir / "trajectories.jsonl").write_text(json.dumps(trajectory) + "\n")
    slot = {
        "model": "model",
        "trajectory_id": "trajectory",
        "slot": 0,
        "shard": 0,
        "seed": 17,
        "decoded_tokens": 4,
        "verification": {"passed": True},
    }
    (run_dir / "slots.jsonl").write_text(json.dumps(slot) + "\n")
    metadata = {
        "model": "model",
        "max_slots": 1,
        "trajectories": 1,
        "successful_trajectories": 1,
        "censored_trajectories": 0,
        "generation_slots": 1,
        "decoded_tokens": 4,
        "generation_elapsed_seconds": 2.0,
        "model_load_seconds": 1.0,
        "decoded_tokens_per_second": 2.0,
        "gpu": "A100",
        "provenance": {
            "tasks_sha256": tasks_sha256,
            "design_sha256": design_sha256,
            "model_revision": "revision",
            "tokenizer_sha256": "tokenizer",
            "code_git_commit": "commit",
            "package_versions": {},
            "slurm_job_id": "job",
        },
    }
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata))

    summary = CONFIRMATION_AUDIT.audit_run(
        run_dir,
        tasks_sha256=tasks_sha256,
        designs_by_sha256={design_sha256: {"trajectory": design_row}},
        all_generation_seeds=set(),
    )
    assert summary["generation_slots"] == 1
    assert summary["wrong_shard_successes"] == 0


def test_four_term_main_runs_on_exact_disjoint_splits(tmp_path: Path, monkeypatch) -> None:
    baseline = "baseline"
    deployed = "deployed"
    models = (baseline, deployed)
    calibration = []
    for model in models:
        for mode in range(3):
            task_id = f"calibration-{mode}"
            for attempt in range(64):
                calibration.append(
                    {
                        "model": model,
                        "mode": mode,
                        "task_id": task_id,
                        "task_stratum": "stratum",
                        "relation": "matched",
                        "attempt": attempt,
                        "verification": {"passed": True},
                    }
                )
            for attempt in range(200):
                calibration.append(
                    {
                        "model": model,
                        "mode": mode,
                        "task_id": task_id,
                        "task_stratum": "stratum",
                        "relation": "wrong",
                        "attempt": attempt,
                        "verification": {"passed": False},
                    }
                )

    confirmation = []
    for model in models:
        for mode in range(3):
            task_id = f"confirmation-{mode}"
            confirmation.append(
                {
                    "design": "four_term",
                    "model": model,
                    "condition": "baseline_prior",
                    "mode": mode,
                    "task_id": task_id,
                    "task_stratum": "stratum",
                    "q": [1 / 3] * 3,
                    "q_true": 1 / 3,
                    "total_slots": 3.0,
                    "success": True,
                    "censored": False,
                    "planned_issued": [40, 40, 40],
                }
            )
            for alpha in (0.6, 0.8):
                for allocation_name in ("matched", "prior", "half_anti"):
                    condition = f"alpha={alpha:.8f}|allocation={allocation_name}"
                    for z in range(3):
                        q = DESIGN.allocation(alpha, z, allocation_name)
                        planned = [round(value * 120) for value in q]
                        target = Fraction(1.0 / q[mode]).limit_denominator(1000)
                        slots = [1] * target.denominator
                        slots[0] += target.numerator - target.denominator
                        for total_slots in slots:
                            confirmation.append(
                                {
                                    "design": "four_term",
                                    "model": model,
                                    "condition": condition,
                                    "mode": mode,
                                    "z": z,
                                    "task_id": task_id,
                                    "task_stratum": "stratum",
                                    "q": q,
                                    "q_true": q[mode],
                                    "total_slots": total_slots,
                                    "success": True,
                                    "censored": False,
                                    "planned_issued": planned,
                                }
                            )

    for index, row in enumerate(confirmation):
        row["trajectory_id"] = f"trajectory-{index}"
        row["winning_shard"] = row["mode"]
        row["issued"] = [0, 0, 0]
        row["issued"][row["mode"]] = int(row["total_slots"])

    calibration_path = tmp_path / "calibration.jsonl"
    confirmation_path = tmp_path / "confirmation.jsonl"
    manifest_path = tmp_path / "manifest.json"
    costs_path = tmp_path / "costs.json"
    output_path = tmp_path / "analysis.json"
    calibration_path.write_text("".join(json.dumps(row) + "\n" for row in calibration))
    confirmation_path.write_text("".join(json.dumps(row) + "\n" for row in confirmation))
    manifest_path.write_text(
        json.dumps(
            {
                "terms": [
                    {
                        "alpha": alpha,
                        "allocation": allocation_name,
                        "information_nats": DESIGN.information(alpha),
                        "mismatch_nats": DESIGN.mismatch(alpha, allocation_name),
                    }
                    for alpha in (0.6, 0.8)
                    for allocation_name in ("matched", "prior", "half_anti")
                ]
            }
        )
    )
    costs_path.write_text(
        json.dumps(
            {
                "clock": "test",
                "models": {baseline: {"kappa": 2.0}, deployed: {"kappa": 1.0}},
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "analyze_sai3_four_term.py",
            "--calibration",
            str(calibration_path),
            "--confirmation",
            str(confirmation_path),
            "--design-manifest",
            str(manifest_path),
            "--costs",
            str(costs_path),
            "--baseline-model",
            baseline,
            "--deployed-model",
            deployed,
            "--bootstrap-repetitions",
            "20",
            "--output",
            str(output_path),
        ],
    )
    FOUR_TERM_ANALYSIS.main()
    result = json.loads(output_path.read_text())
    assert result["status"] == "PASS"
    assert math.isclose(result["confirmation_inverse_share_beta"], 1.0, abs_tol=1e-12)
    assert math.isclose(result["primary_residual_rms_nats"], 0.0, abs_tol=1e-12)


def test_calibration_gate_checks_physical_counts(tmp_path: Path, monkeypatch) -> None:
    rows = []
    seed = 0
    for mode in range(3):
        task_id = f"calibration-{mode}"
        for attempt in range(64):
            seed += 1
            rows.append(
                {
                    "model": "model",
                    "mode": mode,
                    "task_id": task_id,
                    "task_stratum": "stratum",
                    "shard": mode,
                    "relation": "matched",
                    "attempt": attempt,
                    "seed": seed,
                    "verification": {"passed": True},
                }
            )
        for shard in range(3):
            if shard == mode:
                continue
            for attempt in range(4):
                seed += 1
                rows.append(
                    {
                        "model": "model",
                        "mode": mode,
                        "task_id": task_id,
                        "task_stratum": "stratum",
                        "shard": shard,
                        "relation": "wrong",
                        "attempt": attempt,
                        "seed": seed,
                        "verification": {"passed": False},
                    }
                )
    input_path = tmp_path / "calibration.jsonl"
    output_path = tmp_path / "audit.json"
    input_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "analyze_sai3_calibration.py",
            str(input_path),
            "--bootstrap-repetitions",
            "20",
            "--max-off-diagonal-hazard-ratio",
            "1.0",
            "--output",
            str(output_path),
        ],
    )
    CALIBRATION_ANALYSIS.main()
    result = json.loads(output_path.read_text())
    assert result["status"] == "PASS"
    assert result["duplicate_physical_slots"] == 0
    assert result["count_mismatch_task_cells"] == 0


def test_four_term_plots_render_from_analysis_schema(tmp_path: Path) -> None:
    rows = []
    for alpha in (0.6, 0.8):
        for index, allocation_name in enumerate(("matched", "prior", "half_anti")):
            rows.append(
                {
                    "alpha": alpha,
                    "allocation": allocation_name,
                    "predicted_delta_nats": 0.2 + 0.1 * index,
                    "observed_delta_nats": 0.21 + 0.1 * index,
                    "unit_cost_nats": 0.7,
                    "competence_nats": -0.3,
                    "information_nats": DESIGN.information(alpha),
                    "mismatch_nats": DESIGN.mismatch(alpha, allocation_name),
                }
            )
    PLOT.plot_closure(rows, tmp_path / "closure.png")
    PLOT.plot_decomposition(rows, tmp_path / "decomposition.png")
    inverse = {
        "cells": [
            {
                "model": model,
                "mode": mode,
                "q_true": q,
                "mean_first_passage_slots": scale / q,
                "focused_mean_slots": scale,
            }
            for model, scale in (
                ("Qwen/Qwen2.5-Coder-7B-Instruct", 1.3),
                ("Qwen/Qwen2.5-Coder-14B-Instruct", 1.0),
            )
            for mode in range(3)
            for q in (0.2, 0.5, 1.0)
        ]
    }
    PLOT.plot_inverse_share(inverse, tmp_path / "inverse.png")
    assert all((tmp_path / name).stat().st_size > 1000 for name in ("closure.png", "decomposition.png", "inverse.png"))
