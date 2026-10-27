"""Offline preparation of a paired output-contract diagnostic; never dispatch APIs.

The unsuccessful recovery bank remains immutable. This module compiles reviewable
requests and checks decoding boundaries before another campaign is authorized.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
from decimal import Decimal
import itertools
import json
from pathlib import Path
import random

from .environment import REPAIR_SYSTEM, RepairTask, canonical, identity
from .pilot import DEFAULT_POOL, fingerprint, Design
from .pool import read_pool
from .provider import Settings
from .records import save
from .verifier import RepairVerifier

CONTRACTS = ("json_current", "json_example", "python_text")
STUDY = "repair-contract-diagnostic-v1"
SEED = 43118
PROPOSED_LIMIT = Decimal("0.06")
DEEPINFRA_STUDY = "repair-contract-deepinfra-v1"
GEMMA12B_STUDY = "repair-contract-gemma12b-v1"
GEMMA27B_STUDY = "repair-contract-gemma27b-v1"
TRACE_STUDY = "repair-public-trace-information-v1"
INTERFACE_STUDY = "repair-interface-cues-v1"
SOLVER_STUDY = "repair-solver-compatibility-v1"
QWEN_TRACE_STUDY = "repair-qwen-public-trace-information-v1"
EXTENSION_TRACE_STUDY = "repair-extension-public-trace-information-v1"
STREAM_TRACE_STUDY = "repair-qwen-stream-trace-development-v1"
EXAMPLE = {"example.py": "def identity(value):\n    return value\n"}
INSTRUCTIONS = {
    "json_current": REPAIR_SYSTEM,
    "json_example": REPAIR_SYSTEM + " Include every supplied filename as a key; an empty object contains no repair. "
        "Unrelated syntax-only example (do not copy its filename or function): " + canonical(EXAMPLE),
    "python_text": "Repair the supplied single Python file. Return only its complete replacement Python source, "
        "without Markdown fences or a JSON wrapper. Preserve the function interface. "
        "The latest feedback describes the preceding failed attempt; it may refer to a different file state from the files supplied here.",
}


def study_settings(study):
    if study == STREAM_TRACE_STUDY:
        from .streaming import StreamingSettings
        return StreamingSettings(model="qwen/qwen3-coder-next", endpoint="parasail/bf16", provider_name="Parasail",
                        quantization="bf16", input_per_million="0.12", output_per_million="0.80",
                        seed=43135), Decimal("0.47")
    if study == EXTENSION_TRACE_STUDY:
        return Settings(model="qwen/qwen3-coder-next", endpoint="parasail/bf16", provider_name="Parasail",
                        quantization="bf16", input_per_million="0.12", output_per_million="0.80",
                        seed=43131), Decimal("0.18")
    if study == QWEN_TRACE_STUDY:
        return Settings(model="qwen/qwen3-coder-next", endpoint="parasail/bf16", provider_name="Parasail",
                        quantization="bf16", input_per_million="0.12", output_per_million="0.80",
                        seed=43130), Decimal("0.47")
    if study == SOLVER_STUDY:
        return Settings(model="qwen/qwen3-coder-next", endpoint="parasail/bf16", provider_name="Parasail",
                        quantization="bf16", input_per_million="0.12", output_per_million="0.80",
                        seed=43128), Decimal("0.24")
    if study == INTERFACE_STUDY:
        return Settings(model="google/gemma-3-27b-it", endpoint="deepinfra/fp8", provider_name="DeepInfra",
                        quantization="fp8", input_per_million="0.08", output_per_million="0.16",
                        seed=43126), Decimal("0.43")
    if study == TRACE_STUDY:
        return Settings(model="google/gemma-3-27b-it", endpoint="deepinfra/fp8", provider_name="DeepInfra",
                        quantization="fp8", input_per_million="0.08", output_per_million="0.16",
                        seed=43122), Decimal("0.34")
    if study == STUDY:
        return Settings(seed=SEED), PROPOSED_LIMIT
    if study == DEEPINFRA_STUDY:
        return Settings(endpoint="deepinfra/bf16", provider_name="DeepInfra",
                        input_per_million="0.05", output_per_million="0.10", seed=43119), Decimal("0.08")
    if study == GEMMA12B_STUDY:
        return Settings(model="google/gemma-3-12b-it", endpoint="deepinfra/bf16", provider_name="DeepInfra",
                        input_per_million="0.05", output_per_million="0.15", seed=43120), Decimal("0.09")
    if study == GEMMA27B_STUDY:
        return Settings(model="google/gemma-3-27b-it", endpoint="deepinfra/fp8", provider_name="DeepInfra",
                        quantization="fp8", input_per_million="0.08", output_per_million="0.16",
                        seed=43121), Decimal("0.13")
    raise ValueError("Undeclared contract study")


def study_spacing(study):
    study_settings(study)  # Reject undeclared studies; historical pacing is unchanged.
    if study in (SOLVER_STUDY, QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY, STREAM_TRACE_STUDY):
        return 60
    if study == INTERFACE_STUDY:
        return 30
    return 10 if study in (GEMMA12B_STUDY, GEMMA27B_STUDY, TRACE_STUDY) else 60


def public_feedback(result: dict) -> dict:
    return {key: result[key] for key in ("passed", "passed_cases", "total_cases", "cases")}


def request(task: RepairTask, feedback: dict, contract: str, settings=None) -> dict:
    if contract not in CONTRACTS or len(task.public["files"]) != 1:
        raise ValueError("Declare one of three contracts for a single-file task")
    p = task.public
    payload = {"instruction": p["instruction"], "entrypoint": p["entrypoint"],
               "public_cases": p["public_cases"], "latest_feedback": public_feedback(feedback), "files": p["files"]}
    return {"messages": [{"role": "system", "content": INSTRUCTIONS[contract]},
                          {"role": "user", "content": canonical(payload)}],
            "remaining_budget_usd": str((settings or Settings()).reserve), "mode": "model_pilot", "provider_call_enabled": True}


def provider_body(settings: Settings, projected: dict, metadata: dict) -> dict:
    """Generate exact payloads for review; this function has no network effects."""
    if metadata["contract"] not in CONTRACTS:
        raise ValueError("Undeclared output contract")
    body = Settings.body(settings, projected, metadata)
    if metadata["contract"] == "python_text":
        body.pop("response_format")  # Explicit serving-mode difference, not a pure wording experiment.
    return body


def decode(task: RepairTask, content, finish_reason, contract: str) -> dict:
    """Strict, deterministic decoding; no salvage, inferred patch or retry."""
    if contract not in CONTRACTS:
        raise ValueError("Undeclared output contract")
    if finish_reason != "stop" or not isinstance(content, str) or not content.strip():
        return {"artifact_valid": False, "reason": "incomplete_or_empty", "files": None,
                "syntax_valid": False, "declared_entrypoint": False}
    try:
        files = ({next(iter(task.public["files"])): content} if contract == "python_text" else json.loads(content))
        task.validate_artifact(files)
    except (ValueError, TypeError, KeyError, RecursionError):
        return {"artifact_valid": False, "reason": "invalid_artifact_contract", "files": None,
                "syntax_valid": False, "declared_entrypoint": False}
    try:
        tree = ast.parse(next(iter(files.values())))
        syntax_valid = True
        declared = any(isinstance(node, ast.FunctionDef) and node.name == task.public["entrypoint"]["function"] for node in tree.body)
    except (SyntaxError, ValueError, TypeError, RecursionError):
        syntax_valid, declared = False, False
    # Syntax and a textual declaration are diagnostics only, never execution or correctness proofs.
    return {"artifact_valid": True, "reason": None, "files": files,
            "syntax_valid": syntax_valid, "declared_entrypoint": declared}


def task_from_record(record):
    return RepairTask.from_dicts(record["public"], record["evaluator"])



def provenance(tasks, study=STUDY):
    runtime = fingerprint(tasks, Design())
    if study in (QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY, STREAM_TRACE_STUDY):
        if study == STREAM_TRACE_STUDY:
            from .stream_information_study import design
        elif study == EXTENSION_TRACE_STUDY:
            from .extension_information_study import design
        else:
            from .qwen_information_study import design
        import hashlib
        runtime['design'] = design()
        for name in ('repair_information.py', 'contract_diagnostic.py', 'contract_verification.py'):
            report = Path(__file__).parent.parent / 'analysis' / name
            runtime['sources']['analysis/' + name] = hashlib.sha256(report.read_bytes()).hexdigest()
        return runtime
    if study == SOLVER_STUDY:
        from .solver_study import design
        import hashlib
        runtime['design'] = design()
        for name in ('repair_solver.py', 'repair_stagnation.py', 'contract_diagnostic.py', 'contract_verification.py'):
            report = Path(__file__).parent.parent / 'analysis' / name
            runtime['sources']['analysis/' + name] = hashlib.sha256(report.read_bytes()).hexdigest()
        return runtime
    if study == INTERFACE_STUDY:
        from .interface_study import design
        import hashlib
        runtime['design'] = design()
        for name in ('repair_interface.py', 'repair_stagnation.py', 'contract_diagnostic.py', 'contract_verification.py'):
            report = Path(__file__).parent.parent / 'analysis' / name
            runtime['sources']['analysis/' + name] = hashlib.sha256(report.read_bytes()).hexdigest()
        return runtime
    if study == TRACE_STUDY:
        from .diagnostic_study import design
        import hashlib
        runtime["design"] = design()
        for name in ("repair_information.py", "contract_diagnostic.py", "contract_verification.py"):
            report = Path(__file__).parent.parent / "analysis" / name
            runtime["sources"]["analysis/" + name] = hashlib.sha256(report.read_bytes()).hexdigest()
        return runtime
    runtime["design"] = {"contracts": list(CONTRACTS), "draws_per_contract": 1, "seed": study_settings(study)[0].seed}
    return runtime


def construct(tasks: list[RepairTask], verifier, *, prior_commitment="0.01011411", study=STUDY) -> dict:
    """Qualify inputs offline and construct all paired requests before outcomes."""
    if not tasks or any(len(t.public["files"]) != 1 for t in tasks):
        raise ValueError("Nonempty single-file development pool required")
    settings, limit = study_settings(study)
    seed = settings.seed
    ceiling = len(tasks) * len(CONTRACTS) * settings.reserve
    if ceiling > limit:
        raise ValueError("Proposed cap does not cover the entire design")
    preflight = verifier.preflight()
    original = [verifier.check(t.public["files"], t.public["entrypoint"], t.public["public_cases"]) for t in tasks]
    if any(f["passed"] for f in original):
        raise ValueError("Diagnostic requires initially failing bugs; do not silently drop tasks")
    order = list(range(len(tasks)))
    random.Random(seed).shuffle(order)
    permutations = list(itertools.permutations(CONTRACTS))
    random.Random(seed + 1).shuffle(permutations)
    requests = []
    for position, task_index in enumerate(order):
        task = tasks[task_index]
        for contract in permutations[position % len(permutations)]:
            meta = {"study": study, "trajectory": f"{study}-task-{task_index:03d}",
                    "phase": "contract_probe", "depth": 1, "contract": contract,
                    "task_index": task_index, "task_hash": task.task_hash}
            meta["attempt_id"] = identity(meta)
            projected = request(task, original[task_index], contract, settings)
            requests.append({"metadata": meta, "request": projected,
                             "provider_body": provider_body(settings, projected, meta)})
    plan = {"schema_version": 1, "study": study, "status": "draft_not_authorized",
            "api_calls": 0, "live_calls_enabled": False, "monetary_authorization_usd": None,
            "model_results": False, "provider_settings": asdict(settings), "contracts": list(CONTRACTS),
            "maximum_calls": len(requests), "reservation_usd": str(settings.reserve),
            "maximum_new_reservations_usd": str(ceiling), "proposed_cap_usd": str(limit),
            "closed_pilot_commitment_usd": str(Decimal(prior_commitment)),
            "maximum_cumulative_commitment_usd": str(ceiling + Decimal(prior_commitment)),
            "source_provenance": provenance(tasks, study),
            "verifier_preflight": preflight,
            "tasks": [{"public": t.public, "evaluator": json.loads(t.evaluator_json), "task_hash": t.task_hash,
                       "initial_public_result": f} for t, f in zip(tasks, original)],
            "requests": requests,
            "limitations": ["One response per contract per already inspected development bug; no held-out inference.",
                            "Text arm also removes JSON serving mode; do not isolate wording as the cause.",
                            "Artifact validity alone is not comparable across encodings; report syntax, declared entrypoint and full tests.",
                            "No new collection or reuse of closed authorization is enabled by this packet."]}
    plan["packet_id"] = identity(plan)
    validate(plan)
    return plan


def validate(plan: dict) -> dict:
    if plan.get("study") == STREAM_TRACE_STUDY:
        from .stream_information_study import validate_packet
        return validate_packet(plan)
    if plan.get("study") == EXTENSION_TRACE_STUDY:
        from .extension_information_study import validate_packet
        return validate_packet(plan)
    if plan.get('study') == QWEN_TRACE_STUDY:
        from .qwen_information_study import validate_packet
        return validate_packet(plan)
    if plan.get('study') == SOLVER_STUDY:
        from .solver_study import validate_packet
        return validate_packet(plan)
    if plan.get('study') == INTERFACE_STUDY:
        from .interface_study import validate_packet
        return validate_packet(plan)
    if plan.get("study") == TRACE_STUDY:
        from .diagnostic_study import validate_packet
        return validate_packet(plan)
    if identity({k: v for k, v in plan.items() if k != "packet_id"}) != plan["packet_id"]:
        raise ValueError("Packet identity differs")
    if plan["status"] != "draft_not_authorized" or plan["live_calls_enabled"] or plan["monetary_authorization_usd"] is not None:
        raise ValueError("This offline packet cannot grant live authorization")
    settings, limit = study_settings(plan["study"])
    study, seed = plan["study"], settings.seed
    if plan["schema_version"] != 1 or plan["model_results"] or plan["api_calls"] != 0:
        raise ValueError("Undeclared study or model evidence in an offline packet")
    if plan["source_provenance"]["design"] != {"contracts": list(CONTRACTS), "draws_per_contract": 1, "seed": seed}:
        raise ValueError("Diagnostic design drift")
    if [task_from_record(t).task_hash for t in plan["tasks"]] != plan["source_provenance"]["tasks"]:
        raise ValueError("Task provenance differs")
    if Decimal(plan["proposed_cap_usd"]) != limit:
        raise ValueError("Proposed cap differs")
    if Decimal(plan["maximum_cumulative_commitment_usd"]) != Decimal(plan["closed_pilot_commitment_usd"]) + Decimal(plan["maximum_new_reservations_usd"]):
        raise ValueError("Prior commitment missing from total")
    if Settings(**plan["provider_settings"]) != settings or plan["contracts"] != list(CONTRACTS):
        raise ValueError("Undeclared settings/contracts")
    seen, bodies = set(), {}
    for row in plan["requests"]:
        meta = row["metadata"]
        if (meta["study"] != study or meta["phase"] != "contract_probe" or meta["depth"] != 1
                or meta["trajectory"] != f"{study}-task-{meta['task_index']:03d}"):
            raise ValueError("Sampling identity drift")
        task_row = plan["tasks"][meta["task_index"]]
        task = task_from_record(task_row)
        if task.task_hash != meta["task_hash"] or task.task_hash != task_row["task_hash"]:
            raise ValueError("Task identity mismatch")
        key = (meta["task_index"], meta["contract"])
        if key in seen or identity({k: v for k, v in meta.items() if k != "attempt_id"}) != meta["attempt_id"]:
            raise ValueError("Duplicate or altered admission identity")
        seen.add(key)
        expected = request(task, task_row["initial_public_result"], meta["contract"], settings)
        body = provider_body(settings, expected, meta)
        if row["request"] != expected or row["provider_body"] != body:
            raise ValueError("Request projection includes drift or undeclared information")
        normalized = {k: v for k, v in body.items() if k not in ("messages", "response_format")}
        paired = (body["messages"][1], normalized)
        if meta["task_index"] in bodies and bodies[meta["task_index"]] != paired:
            raise ValueError("Matched task/feedback/model/seed/allowance differs")
        bodies[meta["task_index"]] = paired
    expected_cells = {(i, c) for i in range(len(plan["tasks"])) for c in CONTRACTS}
    order = list(range(len(plan["tasks"])))
    random.Random(seed).shuffle(order)
    permutations = list(itertools.permutations(CONTRACTS))
    random.Random(seed + 1).shuffle(permutations)
    expected_order = [(i, c) for pos, i in enumerate(order) for c in permutations[pos % len(permutations)]]
    actual_order = [(r["metadata"]["task_index"], r["metadata"]["contract"]) for r in plan["requests"]]
    if seen != expected_cells or plan["maximum_calls"] != len(seen):
        raise ValueError("Missing or extra planned task/contract cells")
    if actual_order != expected_order:
        raise ValueError("Counterbalanced collection order differs")
    if Decimal(plan["maximum_new_reservations_usd"]) != len(seen) * settings.reserve or len(seen) * settings.reserve > Decimal(plan["proposed_cap_usd"]):
        raise ValueError("Design reservation mismatch")
    return {"tasks": len(plan["tasks"]), "requests": len(seen), "matched_inputs": True,
            "api_calls": 0, "packet_id": plan["packet_id"]}


def demo(plan: dict, output: Path, verifier) -> dict:
    """Synthetic responses test parser/scoring; no model outcomes or transport."""
    validate(plan)
    output.mkdir(parents=True, exist_ok=False)
    preflight = verifier.preflight()
    rows = []
    for row in plan["requests"]:
        meta = row["metadata"]
        task = task_from_record(plan["tasks"][meta["task_index"]])
        # Handwritten engineering response: return the known buggy input unchanged.
        content = (next(iter(task.public["files"].values())) if meta["contract"] == "python_text" else canonical(task.public["files"]))
        parsed = decode(task, content, "stop", meta["contract"])
        public = verifier.check(parsed["files"], task.public["entrypoint"], task.public["public_cases"])
        evaluator = verifier.check(parsed["files"], task.public["entrypoint"], json.loads(task.evaluator_json)["cases"])
        rows.append({"attempt_id": meta["attempt_id"], "task_index": meta["task_index"], "contract": meta["contract"],
                     "content": content, "decoded": parsed, "public": public, "evaluator": evaluator,
                     "full_pass": public["passed"] and evaluator["passed"]})
    result = {"mode": "scripted_contract_demo", "model_results": False, "api_calls": 0,
              "simulated_model_spend_usd": "0", "packet_id": plan["packet_id"],
              "preflight": preflight, "observations": rows,
              "limitation": "Responses are known buggy source copied by a script, never model capability evidence."}
    save(output / "demo.json", result)
    return {"mode": result["mode"], "model_results": False, "api_calls": 0, "scripted_responses": len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "audit", "demo"))
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--study", choices=(STUDY, DEEPINFRA_STUDY, GEMMA12B_STUDY, GEMMA27B_STUDY), default=STUDY)
    parser.add_argument("--prior-commitment", default="0.01011411")
    args = parser.parse_args()
    if args.action == "plan":
        if not args.output:
            parser.error("plan needs a fresh --output JSON path")
        plan = construct([t for _, t, _ in read_pool(args.pool)], RepairVerifier(),
                         study=args.study, prior_commitment=args.prior_commitment)
        save(args.output, plan)
        result = {**validate(plan), "maximum_new_reservations_usd": plan["maximum_new_reservations_usd"],
                  "proposed_cap_usd": plan["proposed_cap_usd"], "live_calls_enabled": False}
    else:
        if not args.input:
            parser.error("audit/demo needs --input packet")
        plan = json.loads(args.input.read_text())
        if args.action == "demo":
            if not args.output:
                parser.error("demo needs a fresh --output directory")
            result = demo(plan, args.output, RepairVerifier())
        else:
            result = validate(plan)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
