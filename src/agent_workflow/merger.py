"""Merge orchestrator: aggregate best agent results into a merged experiment.

The merge phase has six steps:

  1. Gather evidence — collect all snapshots, reasoning traces, and metrics
  2. Build candidate set — best per agent + near-best + informative intermediates
  3. Analyse trajectories — identify modifications correlated with gains
  4. Produce merge candidate(s) — intelligently combine best modifications
  5. Evaluate — run the merged train.py through the normal training pathway
  6. Summarise — explain choices and compare against best individual agent

The key insight for this codebase: train.py contains only scalar hyperparameters.
The merge problem therefore reduces to:
  - identifying which hyperparameter values were improved by which agents
  - building a combined train.py that uses the best value found for each parameter

This is code-aware (uses regex to parse parameters) and evaluation-aware
(uses val_bpb trajectory to confirm which changes helped).

Output directory layout:
    {experiment_dir}/mode_merge/
        candidates/
            candidate_agent_N_best.py
            candidate_merged.py
            ...
        merge_plan.json
        merge_results.json
        merge_report.txt
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import logging

logger = logging.getLogger(__name__)

from agent_workflow.instrumentation.snapshotting import SnapshotManager, SnapshotMetadata
from agent_workflow.instrumentation.reasoning_trace import (
    ReasoningEntry,
    collect_all_traces,
    summarize_all_traces,
)


# ---------------------------------------------------------------------------
# Hyperparameter pattern matching
# ---------------------------------------------------------------------------

# Matches ALL UPPERCASE param assignments with any value type
# e.g. EMBEDDING_LR = 1e-3, ADAM_BETAS = (0.8, 0.95), WINDOW_PATTERN = "local"
_HYPERPARAM_RE_FULL = re.compile(
    r'^(?P<name>[A-Z][A-Z0-9_]+)\s*=\s*(?P<value>[^\s#\n][^#\n]*?)(?:\s*#.*)?$',
    re.MULTILINE,
)

# Keep the old numeric-only regex for backward-compat with produce_merged_candidate
_HYPERPARAM_RE = re.compile(
    r'^(?P<indent>\s*)(?P<name>[A-Z_][A-Z0-9_]*)(?P<sep>\s*=\s*)(?P<value>[0-9eE+\-\.]+)\s*(?:#.*)?$',
    re.MULTILINE,
)

# Auto-detect TUNABLE_PARAMS from any UPPERCASE line — filled lazily per file.
# Kept as a set for backward training runtime with produce_merged_candidate internals.
TUNABLE_PARAMS: set[str] = set()


def _coerce_hyperparam_value(value: str):
    """Return a numeric value when safe, otherwise preserve the source string."""
    stripped = value.strip()
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", stripped):
        return float(stripped)
    return stripped


def _detect_tunable_params(train_py: str) -> set[str]:
    """Return the set of all UPPERCASE param names found in train_py."""
    return {m.group("name") for m in _HYPERPARAM_RE_FULL.finditer(train_py)}


def extract_hyperparams(train_py: str) -> dict[str, object]:
    """Extract all UPPERCASE hyperparameter values from train.py source.

    Numeric scalar values are returned as floats; non-scalar values such as
    tuples and strings are preserved as source strings.
    """
    params: dict[str, object] = {}
    for m in _HYPERPARAM_RE_FULL.finditer(train_py):
        params[m.group("name")] = _coerce_hyperparam_value(m.group("value"))
    return params


def apply_hyperparams(train_py: str, params: dict[str, object]) -> str:
    """Replace hyperparameter values in train.py source (string-based)."""
    result = train_py
    for name, value in params.items():
        result = re.sub(
            r'^(' + re.escape(name) + r'\s*=\s*)[^\s#\n][^#\n]*?(\s*(?:#.*)?)$',
            r'\g<1>' + str(value) + r'\g<2>',
            result,
            flags=re.MULTILINE,
        )
    return result


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MergeCandidate:
    """One candidate train.py for evaluation."""
    name: str                        # human-readable label
    source_agents: list[str]         # which agents contributed
    source_steps: list[int]          # which steps were used
    train_py_path: str               # absolute path to the candidate file
    hyperparams: dict[str, float] = field(default_factory=dict)
    strategy: str = ""               # description of how it was formed
    val_bpb: Optional[float] = None  # filled in after evaluation

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MergePlan:
    """Records what was decided before the merge run."""
    experiment_id: str
    mode: str
    timestamp: str
    candidates: list[dict] = field(default_factory=list)
    reasoning_summary: dict = field(default_factory=dict)
    trajectory_analysis: dict = field(default_factory=dict)
    merge_strategy: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MergeResults:
    """Final results of the merge phase."""
    experiment_id: str
    timestamp: str
    best_individual_agent: str
    best_individual_val_bpb: Optional[float]
    merge_val_bpb: Optional[float]
    merge_candidate_name: str
    merge_won: Optional[bool]
    delta_val_bpb: Optional[float]
    candidates_evaluated: list[dict] = field(default_factory=list)
    merge_explanation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Merge orchestrator
# ---------------------------------------------------------------------------

class MergeOrchestrator:
    """Runs the full merge phase for a completed parallel experiment.

    Parameters
    ----------
    experiment_dir : Path
        The experiment root (e.g. runs/experiment_parallel_20260331/).
    mode : str
        Which parallel run to merge from (default "parallel").
    autoresearch_dir : Path
        Path to the autoresearch repo (for running evaluation).
    """

    def __init__(
        self,
        experiment_dir: Path,
        autoresearch_dir: Path,
        mode: str = "parallel",
    ):
        self.experiment_dir = Path(experiment_dir)
        self.autoresearch_dir = Path(autoresearch_dir)
        self.mode = mode
        self.mode_dir = self.experiment_dir / f"mode_{mode}"
        self.merge_dir = self.experiment_dir / "mode_merge"
        self.merge_dir.mkdir(parents=True, exist_ok=True)
        (self.merge_dir / "candidates").mkdir(exist_ok=True)

        # Read slurm_time from experiment config.json if available
        cfg_path = self.experiment_dir / "config.json"
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text())
                self.slurm_time: str = cfg.get("slurm_time", "00:10:00")
            except Exception:
                self.slurm_time = "00:10:00"
        else:
            self.slurm_time = "00:10:00"

    # ------------------------------------------------------------------
    # Step 1: Gather evidence
    # ------------------------------------------------------------------

    def gather_evidence(self) -> dict:
        """Collect all snapshots, reasoning traces, and metrics."""
        evidence: dict = {
            "agents": {},
            "reasoning_summary": {},
        }

        for agent_dir in sorted(self.mode_dir.glob("agent_*")):
            agent_id = agent_dir.name
            snap_mgr = SnapshotManager(agent_dir / "snapshots")
            snapshots = snap_mgr.list_snapshots()

            # Per-agent trajectory metrics
            traj_path = agent_dir / "results" / "trajectory.jsonl"
            trajectory = []
            if traj_path.exists():
                for line in traj_path.read_text().splitlines():
                    line = line.strip()
                    if line:
                        try:
                            trajectory.append(json.loads(line))
                        except Exception:
                            pass

            evidence["agents"][agent_id] = {
                "agent_dir": str(agent_dir),
                "snapshots": [s.to_dict() for s in snapshots],
                "trajectory": trajectory,
                "best_val_bpb": min(
                    (s["val_bpb"] for s in trajectory if s.get("val_bpb")), default=None
                ),
            }

        # Reasoning traces
        traces = collect_all_traces(self.experiment_dir, self.mode)
        evidence["reasoning_summary"] = summarize_all_traces(traces)

        return evidence

    # ------------------------------------------------------------------
    # Step 2: Build candidate set
    # ------------------------------------------------------------------

    def build_candidate_set(self, evidence: dict) -> list[MergeCandidate]:
        """Select best + informative non-best snapshots as merge candidates."""
        candidates: list[MergeCandidate] = []
        cand_dir = self.merge_dir / "candidates"

        for agent_id, agent_data in evidence["agents"].items():
            agent_dir = Path(agent_data["agent_dir"])
            snap_mgr = SnapshotManager(agent_dir / "snapshots")

            # Best per agent
            best = snap_mgr.best_snapshot()
            if best:
                best_path = snap_mgr.get_snapshot_dir(best.step_index)
                if best_path and (best_path / "train.py").exists():
                    dest = cand_dir / f"candidate_{agent_id}_best.py"
                    shutil.copy2(best_path / "train.py", dest)
                    candidates.append(MergeCandidate(
                        name=f"{agent_id}_best",
                        source_agents=[agent_id],
                        source_steps=[best.step_index],
                        train_py_path=str(dest),
                        hyperparams=extract_hyperparams(dest.read_text()),
                        strategy=f"Best snapshot from {agent_id} (step {best.step_index}, "
                                  f"val_bpb={best.val_bpb_after})",
                        val_bpb=best.val_bpb_after,
                    ))

            # Final snapshot (last step, may differ from best)
            all_snaps = snap_mgr.list_snapshots()
            if all_snaps:
                final = all_snaps[-1]
                if best is None or final.step_index != best.step_index:
                    final_path = snap_mgr.get_snapshot_dir(final.step_index)
                    if final_path and (final_path / "train.py").exists():
                        dest = cand_dir / f"candidate_{agent_id}_final.py"
                        shutil.copy2(final_path / "train.py", dest)
                        candidates.append(MergeCandidate(
                            name=f"{agent_id}_final",
                            source_agents=[agent_id],
                            source_steps=[final.step_index],
                            train_py_path=str(dest),
                            hyperparams=extract_hyperparams(dest.read_text()),
                            strategy=f"Final snapshot from {agent_id} (step {final.step_index})",
                            val_bpb=final.val_bpb_after,
                        ))

            # Informative intermediates (major improvement steps)
            for snap in snap_mgr.informative_snapshots(top_k=3):
                if snap.step_index in {(best.step_index if best else -1), (all_snaps[-1].step_index if all_snaps else -1)}:
                    continue
                snap_path = snap_mgr.get_snapshot_dir(snap.step_index)
                if snap_path and (snap_path / "train.py").exists():
                    dest = cand_dir / f"candidate_{agent_id}_step{snap.step_index:03d}.py"
                    shutil.copy2(snap_path / "train.py", dest)
                    candidates.append(MergeCandidate(
                        name=f"{agent_id}_step{snap.step_index:03d}",
                        source_agents=[agent_id],
                        source_steps=[snap.step_index],
                        train_py_path=str(dest),
                        hyperparams=extract_hyperparams(dest.read_text()),
                        strategy=f"Informative intermediate from {agent_id} step {snap.step_index} "
                                  f"(hypothesis: {snap.hypothesis[:60]})",
                        val_bpb=snap.val_bpb_after,
                    ))

        return candidates

    # ------------------------------------------------------------------
    # Step 3: Analyse trajectories
    # ------------------------------------------------------------------

    def analyse_trajectories(
        self, evidence: dict, candidates: list[MergeCandidate]
    ) -> dict:
        """Identify which modifications correlate with metric improvements.

        Diffs consecutive snapshot train.py files to attribute improvements
        only to the parameters that actually changed in each step.
        """
        analysis: dict = {
            "per_param_improvements": {},
            "cross_agent_patterns": [],
            "conflicting_directions": [],
        }

        # param → list of (improvement, changed_value, agent_id)
        per_param: dict[str, list[float]] = {}

        for agent_id, agent_data in evidence["agents"].items():
            agent_dir = Path(agent_data["agent_dir"])
            snap_mgr = SnapshotManager(agent_dir / "snapshots")
            snaps = snap_mgr.list_snapshots()
            # Sort by step index for consecutive diffing
            snaps_sorted = sorted(snaps, key=lambda s: s.step_index)

            prev_params: Optional[dict[str, str]] = None

            for snap in snaps_sorted:
                snap_dir = snap_mgr.get_snapshot_dir(snap.step_index)
                if snap_dir is None or not (snap_dir / "train.py").exists():
                    prev_params = None
                    continue

                curr_params = extract_hyperparams((snap_dir / "train.py").read_text())

                if prev_params is not None:
                    # Find params that changed between previous and current snapshot
                    changed_params = {
                        name
                        for name, val in curr_params.items()
                        if prev_params.get(name) != val
                    }
                    # Also include new params not in prev
                    changed_params |= set(curr_params.keys()) - set(prev_params.keys())

                    if (
                        changed_params
                        and snap.val_bpb_before is not None
                        and snap.val_bpb_after is not None
                    ):
                        improvement = snap.val_bpb_before - snap.val_bpb_after
                        if not snap.accepted:
                            improvement = -abs(improvement)

                        for param in changed_params:
                            if param not in per_param:
                                per_param[param] = []
                            per_param[param].append(improvement)

                prev_params = curr_params

        for param, improvements in per_param.items():
            if improvements:
                mean_imp = sum(improvements) / len(improvements)
                analysis["per_param_improvements"][param] = {
                    "mean_improvement": mean_imp,
                    "positive_count": sum(1 for x in improvements if x > 0),
                    "negative_count": sum(1 for x in improvements if x < 0),
                    "likely_helpful": mean_imp > 0,
                }

        # Cross-agent patterns from reasoning traces
        reasoning_summary = evidence.get("reasoning_summary", {})
        analysis["cross_agent_patterns"] = reasoning_summary.get(
            "independently_confirmed_hypotheses", []
        )

        return analysis

    # ------------------------------------------------------------------
    # Step 4: Produce merge candidates
    # ------------------------------------------------------------------

    def produce_merged_candidate(
        self,
        candidates: list[MergeCandidate],
        analysis: dict,
        baseline_train_py: Path,
    ) -> MergeCandidate:
        """Produce a merged train.py by combining best modifications.

        Strategy:
        1. Start from the best single candidate (lowest known val_bpb)
        2. For each hyperparameter, check if any other candidate has a better
           value (as evidenced by lower val_bpb with that specific param differing)
        3. Apply the single best value for each parameter
        4. Save as candidate_merged.py

        This is NOT a naive text concatenation — it's parameter-level merging
        grounded in per-candidate val_bpb evidence.
        """
        cand_dir = self.merge_dir / "candidates"

        # Sort by known val_bpb
        ranked = sorted(
            [c for c in candidates if c.val_bpb is not None],
            key=lambda c: c.val_bpb,  # type: ignore[arg-type]
        )
        if not ranked:
            # Fall back to baseline
            dest = cand_dir / "candidate_merged.py"
            shutil.copy2(baseline_train_py, dest)
            return MergeCandidate(
                name="merged_fallback",
                source_agents=["baseline"],
                source_steps=[],
                train_py_path=str(dest),
                hyperparams=extract_hyperparams(dest.read_text()),
                strategy="Fallback to baseline (no ranked candidates available)",
            )

        # Start from the best candidate
        best_cand = ranked[0]
        merged_src = Path(best_cand.train_py_path).read_text()
        merged_params = dict(best_cand.hyperparams)
        contributing_agents = list(best_cand.source_agents)
        contributing_steps = list(best_cand.source_steps)
        transplants: list[str] = []

        # Detect tunable params dynamically from the best candidate's source
        dynamic_tunable = _detect_tunable_params(merged_src)

        # For each tunable parameter, see if any other candidate has a better value
        per_param_improvements = analysis.get("per_param_improvements", {})
        for param in dynamic_tunable:
            if param not in merged_params:
                continue
            best_param_value = merged_params[param]
            best_param_bpb = best_cand.val_bpb

            for cand in ranked[1:]:
                if param not in cand.hyperparams:
                    continue
                cand_value = cand.hyperparams[param]
                if str(cand_value).strip() == str(best_param_value).strip():
                    continue  # same value, skip
                # Only transplant if this candidate has better or comparable val_bpb
                # AND the parameter is generally associated with improvements
                param_info = per_param_improvements.get(param, {})
                if (
                    cand.val_bpb is not None
                    and best_param_bpb is not None
                    and cand.val_bpb < best_param_bpb * 1.005  # within 0.5% of best
                    and param_info.get("likely_helpful", False)
                ):
                    merged_params[param] = cand_value
                    best_param_bpb = cand.val_bpb
                    contributing_agents.append(cand.source_agents[0] if cand.source_agents else "?")
                    contributing_steps.extend(cand.source_steps)
                    transplants.append(
                        f"{param}={cand_value} from {cand.name} (val_bpb={cand.val_bpb:.6f})"
                    )

        merged_src = apply_hyperparams(merged_src, merged_params)
        dest = cand_dir / "candidate_merged.py"
        dest.write_text(merged_src)

        strategy = (
            f"Base: {best_cand.name} (val_bpb={best_cand.val_bpb}). "
            + (f"Transplanted: {'; '.join(transplants)}" if transplants else "No transplants made.")
        )

        return MergeCandidate(
            name="merged",
            source_agents=list(set(contributing_agents)),
            source_steps=contributing_steps,
            train_py_path=str(dest),
            hyperparams=merged_params,
            strategy=strategy,
        )

    # ------------------------------------------------------------------
    # Step 5: Evaluate (optional — requires SLURM or local training)
    # ------------------------------------------------------------------

    def evaluate_candidate(
        self,
        candidate: MergeCandidate,
        workspace: Path,
        slurm_partition: str = "pi_tpoggio",
        slurm_gres: str = "gpu:1",
        slurm_time: Optional[str] = None,
        timeout_seconds: int = 900,
    ) -> Optional[float]:
        """Copy candidate to workspace, run training, return val_bpb.

        Returns None if evaluation fails or times out.
        """
        effective_slurm_time = slurm_time if slurm_time is not None else self.slurm_time
        train_py = workspace / "train.py"
        try:
            shutil.copy2(candidate.train_py_path, train_py)
            logger.debug("[merger] evaluate_candidate using slurm_time=%s", effective_slurm_time)
            submit_sh = workspace / "submit_training.sh"
            if not submit_sh.exists():
                print(f"[merger] No submit_training.sh in {workspace}, skipping evaluation.")
                return None

            # Submit job
            result = subprocess.run(
                ["bash", "submit_training.sh"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=60,
            )
            job_id = result.stdout.strip()
            if not job_id.isdigit():
                print(f"[merger] Unexpected job ID: {job_id!r}")
                return None

            print(f"[merger] Submitted SLURM job {job_id} for {candidate.name}")

            # Poll
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                time.sleep(30)
                check = subprocess.run(
                    ["bash", "check_training.sh", job_id],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                output = check.stdout
                if "TRAINING DONE" in output:
                    # Parse val_bpb
                    for line in output.splitlines():
                        if line.startswith("val_bpb:"):
                            try:
                                return float(line.split(":", 1)[1].strip())
                            except ValueError:
                                pass
                    return None
                elif "TRAINING FAILED" in output:
                    print(f"[merger] Training failed: {output[:200]}")
                    return None

            print(f"[merger] Evaluation timed out after {timeout_seconds}s.")
            return None

        except Exception as e:
            print(f"[merger] Evaluation error: {e}")
            return None

    # ------------------------------------------------------------------
    # Full merge run
    # ------------------------------------------------------------------

    def run(
        self,
        baseline_train_py: Optional[Path] = None,
        evaluation_workspace: Optional[Path] = None,
        evaluate: bool = True,
        agent_based: bool = False,
        agent_model: str = "claude-opus-4-6",
    ) -> MergeResults:
        """Execute the full merge pipeline.

        Evaluation is optional: after producing the merged candidate, a
        training run can be submitted to measure its val_bpb.

        Parameters
        ----------
        baseline_train_py : Path, optional
            Original unmodified train.py. Used as merge base fallback.
        evaluation_workspace : Path, optional
            Pre-configured workspace with submit/check scripts for evaluation.
            Auto-detected from the first agent workspace if not provided.
        agent_based : bool
            If True, use a Claude agent to produce the merged candidate.
            If False (default), use the deterministic parameter-level merge.
        agent_model : str
            Claude model to use when agent_based=True.
        """
        print("[merger] Step 1: Gathering evidence...")
        evidence = self.gather_evidence()

        # Find best individual agent
        best_agent_id: Optional[str] = None
        best_agent_bpb: Optional[float] = None
        for agent_id, agent_data in evidence["agents"].items():
            bpb = agent_data.get("best_val_bpb")
            if bpb is not None and (best_agent_bpb is None or bpb < best_agent_bpb):
                best_agent_bpb = bpb
                best_agent_id = agent_id

        print(f"[merger] Best individual agent: {best_agent_id} (val_bpb={best_agent_bpb})")

        print("[merger] Step 2: Building candidate set...")
        candidates = self.build_candidate_set(evidence)
        print(f"[merger] Collected {len(candidates)} candidates.")

        print("[merger] Step 3: Analysing trajectories...")
        analysis = self.analyse_trajectories(evidence, candidates)

        # Determine baseline train.py for fallback
        if baseline_train_py is None:
            # Try to find it from the first agent's workspace
            for agent_dir in sorted(self.mode_dir.glob("agent_*")):
                baseline_candidate = agent_dir / "workspace" / "train.py.baseline"
                if baseline_candidate.exists():
                    baseline_train_py = baseline_candidate
                    break
        if baseline_train_py is None:
            # Last resort: use autoresearch/train.py
            baseline_train_py = self.autoresearch_dir / "train.py"

        print("[merger] Step 4: Producing merged candidate...")
        if agent_based:
            from agent_workflow.agent_merger import (
                produce_merged_candidate_via_agent,
            )
            print(f"[merger] Using agent-based merge (model={agent_model}).")
            merged = produce_merged_candidate_via_agent(
                candidates=candidates,
                evidence=evidence,
                baseline_train_py_path=baseline_train_py,
                merge_dir=self.merge_dir,
                model=agent_model,
                slurm_time=self.slurm_time,
            )
        else:
            merged = self.produce_merged_candidate(candidates, analysis, baseline_train_py)
        candidates.append(merged)
        print(f"[merger] Merge strategy: {merged.strategy}")

        # Write merge plan
        plan = MergePlan(
            experiment_id=self.experiment_dir.name,
            mode=self.mode,
            timestamp=datetime.now(timezone.utc).isoformat(),
            candidates=[c.to_dict() for c in candidates],
            reasoning_summary=evidence.get("reasoning_summary", {}),
            trajectory_analysis=analysis,
            merge_strategy=merged.strategy,
            notes="Merge produced by parameter-level analysis of agent snapshots and reasoning traces.",
        )
        (self.merge_dir / "merge_plan.json").write_text(
            json.dumps(plan.to_dict(), indent=2)
        )

        # Step 5: Evaluate — auto-detect workspace if evaluation was requested
        if evaluate and evaluation_workspace is None:
            for agent_dir in sorted(self.mode_dir.glob("agent_*")):
                ws = agent_dir / "workspace"
                if (ws / "submit_training.sh").exists():
                    evaluation_workspace = ws
                    print(f"[merger] Auto-detected evaluation workspace: {ws}")
                    break
        if evaluate and evaluation_workspace is None:
            print(
                "[merger] Step 5: No evaluation workspace found — skipping evaluation.",
                file=__import__("sys").stderr,
            )

        merge_val_bpb: Optional[float] = None
        if evaluate and evaluation_workspace is not None:
            print("[merger] Step 5: Evaluating merged candidate...")
            merge_val_bpb = self.evaluate_candidate(merged, evaluation_workspace)
            merged.val_bpb = merge_val_bpb
            print(f"[merger] Merged val_bpb = {merge_val_bpb}")
        else:
            print("[merger] Step 5: Evaluation skipped.")

        # Step 6: Summarise
        merge_won: Optional[bool] = None
        delta: Optional[float] = None
        if merge_val_bpb is not None and best_agent_bpb is not None:
            merge_won = merge_val_bpb < best_agent_bpb
            delta = best_agent_bpb - merge_val_bpb

        explanation = _build_explanation(merged, analysis, evidence, merge_val_bpb, best_agent_bpb)

        results = MergeResults(
            experiment_id=self.experiment_dir.name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            best_individual_agent=best_agent_id or "unknown",
            best_individual_val_bpb=best_agent_bpb,
            merge_val_bpb=merge_val_bpb,
            merge_candidate_name=merged.name,
            merge_won=merge_won,
            delta_val_bpb=delta,
            candidates_evaluated=[c.to_dict() for c in candidates],
            merge_explanation=explanation,
        )

        (self.merge_dir / "merge_results.json").write_text(
            json.dumps(results.to_dict(), indent=2)
        )
        _write_merge_report(self.merge_dir / "merge_report.txt", results, plan)

        print("[merger] Merge phase complete.")
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_explanation(
    merged: MergeCandidate,
    analysis: dict,
    evidence: dict,
    merge_bpb: Optional[float],
    best_bpb: Optional[float],
) -> str:
    lines = ["=== Merge Explanation ===", ""]
    lines.append(f"Merge strategy: {merged.strategy}")
    lines.append("")
    lines.append("Snapshot selection:")
    lines.append(f"  Contributing agents: {', '.join(merged.source_agents)}")
    lines.append(f"  Contributing steps: {merged.source_steps}")
    lines.append("")
    lines.append("Trajectory evidence:")
    for param, info in analysis.get("per_param_improvements", {}).items():
        likely = "likely helpful" if info["likely_helpful"] else "likely not helpful"
        lines.append(
            f"  {param}: mean_improvement={info['mean_improvement']:.4f} ({likely})"
        )
    lines.append("")
    patterns = analysis.get("cross_agent_patterns", [])
    if patterns:
        lines.append("Independently confirmed hypotheses (≥2 agents):")
        for p in patterns:
            lines.append(f"  - {p['hypothesis']} (confirmed by {p['count']} agents)")
    else:
        lines.append("No hypotheses independently confirmed by ≥2 agents.")
    lines.append("")
    if merge_bpb is not None and best_bpb is not None:
        if merge_bpb < best_bpb:
            lines.append(f"Outcome: MERGE WON — val_bpb {merge_bpb:.6f} < best individual {best_bpb:.6f}")
        else:
            lines.append(f"Outcome: MERGE DID NOT WIN — val_bpb {merge_bpb:.6f} >= best individual {best_bpb:.6f}")
    else:
        lines.append("Outcome: merge candidate not yet evaluated.")
    return "\n".join(lines)


def _write_merge_report(path: Path, results: MergeResults, plan: MergePlan) -> None:
    lines = [
        "=== Merge Phase Report ===",
        f"Experiment: {results.experiment_id}",
        f"Timestamp:  {results.timestamp}",
        "",
        f"Best individual agent:  {results.best_individual_agent}",
        f"Best individual val_bpb: {results.best_individual_val_bpb}",
        f"Merged val_bpb:          {results.merge_val_bpb}",
        f"Merge won:               {results.merge_won}",
        f"Delta val_bpb:           {results.delta_val_bpb}",
        "",
        results.merge_explanation,
        "",
        "=== Candidates ===",
    ]
    for c in results.candidates_evaluated:
        raw_bpb = c.get("val_bpb")
        bpb_str = str(raw_bpb) if raw_bpb is not None else "N/A"
        lines.append(
            f"  {c['name']:40s}  val_bpb={bpb_str:>12}  "
            f"agents={c['source_agents']}"
        )
    path.write_text("\n".join(lines) + "\n")
