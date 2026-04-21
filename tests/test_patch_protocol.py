from __future__ import annotations

import difflib
import json
from pathlib import Path

import vao.orchestrator as orchestrator_module
from vao.agents.base import AgentState
from vao.agents.claude_parser import parse_edit_payload
from vao.logging_utils import read_jsonl, sha256_file, write_json
from vao.orchestrator import run_single
from vao.schemas import BranchEvaluation, CandidateProposal, ModeDistribution
from vao.taxonomy import MODES
from vao.validate_run import validate_run


class PatchProbeAdapter:
    model_id = "patch-probe-v1"
    strict_failures = True

    def __init__(self, model_id: str = "patch-probe-v1", **_: object) -> None:
        self.model_id = model_id

    def propose_mode_distribution(self, state: AgentState) -> ModeDistribution:
        probs = {mode: 0.1 for mode in MODES}
        probs["layout"] = 0.5
        parsed = {
            "mode_probs": probs,
            "mode_ranking": ["layout", "indexing", "topk", "caching", "summaries", "micro"],
            "mode_rationales": {mode: "patch probe" for mode in MODES},
        }
        return ModeDistribution(raw_text=json.dumps(parsed), parsed_json=parsed, **parsed)

    def propose_edit_for_mode(self, state: AgentState, mode: str, branch_dir: Path) -> CandidateProposal:
        parent_path = branch_dir / "parent_solution.py"
        proposed_path = branch_dir / "proposed_solution.py"
        model_edit_path = branch_dir / "model_edit.diff"
        parent_source = parent_path.read_text(encoding="utf-8")
        proposed_source = parent_source + f"# patch-probe mode: {mode}\n"
        diff_text = "\n".join(
            difflib.unified_diff(
                parent_source.splitlines(),
                proposed_source.splitlines(),
                fromfile="parent_solution.py",
                tofile="proposed_solution.py",
                lineterm="",
            )
        )
        raw = json.dumps(
            {
                "primary_mode": mode,
                "declared_mode": mode,
                "edit_format": "unified_diff",
                "secondary_modes": [],
                "target_regions": ["file_footer"],
                "rationale": f"Append a harmless marker for {mode}.",
                "unified_diff": diff_text,
            }
        )
        parsed = parse_edit_payload(raw, mode, parent_source=parent_source)
        model_edit_path.write_text(parsed["unified_diff"], encoding="utf-8")
        proposed_path.write_text(parsed["solution_py"], encoding="utf-8")
        return CandidateProposal(
            branch_index=MODES.index(mode),
            primary_mode=mode,
            secondary_modes=[],
            declared_mode=mode,
            source_hash=sha256_file(proposed_path),
            source_parent_hash=sha256_file(parent_path),
            file_path=str(proposed_path),
            raw_output_text=raw,
            parsed_output_json={key: value for key, value in parsed.items() if key != "solution_py"}
            | {"model_edit_path": str(model_edit_path)},
            changed=True,
        )


def test_patch_protocol_materializes_isolated_branch_edits(tmp_path: Path, monkeypatch) -> None:
    def fake_evaluate_solution(solution_path: Path, profile_id: str, timeout_seconds: int, out_path: Path, **kwargs: object) -> BranchEvaluation:
        declared_mode = str(kwargs.get("declared_mode", "micro"))
        loss = 1.0 if kwargs.get("run_id") == "baseline" else 0.9 + 0.01 * MODES.index(declared_mode)
        result = BranchEvaluation(
            branch_index=int(kwargs.get("branch_index", 0)),
            primary_mode=str(kwargs.get("primary_mode", declared_mode)),
            secondary_modes=list(kwargs.get("secondary_modes", [])),
            declared_mode=declared_mode,
            inferred_mode=str(kwargs.get("inferred_mode", declared_mode)),
            source_hash=sha256_file(solution_path),
            source_parent_hash=kwargs.get("source_parent_hash"),
            file_path=str(solution_path),
            correctness=True,
            latent_loss=loss,
            family_losses={"fake": loss},
            raw_verifier_path=str(out_path.parent / "fake_raw"),
        )
        write_json(out_path, result)
        return result

    monkeypatch.setattr("vao.orchestrator.evaluate_solution", fake_evaluate_solution)
    monkeypatch.setitem(orchestrator_module.ADAPTERS, "patch_probe", PatchProbeAdapter)
    config = {
        "experiment": {
            "name": "patch_probe",
            "visibility_regime": "top1_only",
            "modes": MODES,
            "steps": 1,
            "wall_budget_seconds": 300,
            "branch_timeout_seconds": 30,
            "incorrect_penalty": -1.0,
        },
        "benchmark": {
            "template_path": "benchmarks/stateful_query_engine/solution_template.py",
            "profiles": ["hard_optimization"],
        },
        "models": {"include": ["patch_probe"]},
        "output": {"root": str(tmp_path / "runs")},
    }
    run_dir = run_single(
        config,
        "patch_probe",
        {"adapter": "patch_probe", "model_id": "patch-probe-v1"},
        "hard_optimization",
        run_id="patch_probe",
    )

    row = read_jsonl(run_dir / "evaluations.jsonl")[0]
    parent_hash = row["parent_solution_hash"]
    assert len(row["branches"]) == 6
    assert {branch["source_parent_hash"] for branch in row["branches"]} == {parent_hash}
    for branch in row["branches"]:
        edit_path = Path(branch["model_edit_path"])
        candidate_path = Path(branch["file_path"])
        assert edit_path.exists()
        assert "unified_diff" not in candidate_path.read_text(encoding="utf-8")
        assert f"# patch-probe mode: {branch['declared_mode']}" in candidate_path.read_text(encoding="utf-8")

    validation = validate_run(run_dir)
    assert validation["passed"], validation
