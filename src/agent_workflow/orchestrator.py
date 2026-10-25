"""Manages parallel process spawning for agent experiments.

Responsibilities:
- Initialize experiment directory
- Create isolated workspaces (one per agent)
- Launch agent processes concurrently
- Enforce wall-clock budget per agent
- Ensure zero cross-agent file access
- Wait for all agents to finish
- Hand off to collector.py

Must NOT:
- Read one agent's results and pass them to another
- Merge trajectories during the run
- Act as a central planner that changes agent behavior
"""

from __future__ import annotations

import atexit
import csv
import json
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_workflow.agents.isolated_agent_process import IsolatedAgentProcess
from agent_workflow.config import AgentConfig, ExperimentConfig
from agent_workflow.utils.workspace import create_workspace, destroy_workspace


class Orchestrator:
    """Coordinates multi-agent experiments.

    Modes supported:
      run_parallel()   — N independent agents in parallel (N from config.agents)
      run_single()     — 1 agent with 2× budget
      run_merge()      — post-hoc merge of a completed parallel run
    """

    POLL_INTERVAL_SEC = 10

    def __init__(self, config: ExperimentConfig, repo_root: Path):
        self.config = config
        self.repo_root = repo_root
        self.autoresearch_dir = repo_root / config.autoresearch_dir
        self._processes: list[IsolatedAgentProcess] = []
        self._cleanup_done = False

    # ------------------------------------------------------------------
    # Graceful shutdown: SIGTERM / SIGINT / atexit
    # ------------------------------------------------------------------

    def _register_cleanup(self) -> None:
        """Register cleanup handlers once per orchestrator instance."""
        atexit.register(self._cleanup)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, frame) -> None:
        print(f"\n[orchestrator] Signal {signum} received — shutting down.", flush=True)
        self._cleanup()
        sys.exit(1)

    def _cleanup(self) -> None:
        """Terminate all agent processes and cancel their SLURM worker jobs."""
        if self._cleanup_done:
            return
        self._cleanup_done = True

        # 1. Gracefully terminate agent processes, then force-kill stragglers.
        for proc in self._processes:
            if proc.is_alive():
                proc.terminate()
        time.sleep(3)
        for proc in self._processes:
            if proc.is_alive():
                proc.kill()

        # 2. Cancel SLURM worker jobs for every agent in this experiment.
        for agent in self.config.agents:
            try:
                subprocess.run(
                    ["bash", "-c",
                     f'squeue -u "$USER" -n "worker_{agent.agent_id}" -h -o "%i" 2>/dev/null'
                     " | xargs -r scancel"],
                    capture_output=True,
                    timeout=15,
                )
            except Exception:
                pass

        print("[orchestrator] Cleanup complete.", flush=True)

    def run_parallel(
        self,
        experiment_dir: Path,
        system_prompt: str,
        first_message_prompt: str,
    ) -> None:
        """Launch all agents simultaneously. Block until all finish or budgets expire."""
        self._validate_gpu_assignments()
        mode_dir = experiment_dir / f"mode_{self.config.mode}"
        run_id = self.config.experiment_id

        # Write experiment manifest
        manifest_path = experiment_dir / "config.json"
        manifest_path.write_text(json.dumps(self.config.to_dict(), indent=2))

        # Set up workspaces and build processes
        processes: list[IsolatedAgentProcess] = []
        hard_deadlines: list[float] = []

        for agent_config in self.config.agents:
            agent_dir, workspace = self._setup_agent(agent_config, mode_dir, run_id)
            first_message = _render_first_message(
                prompt=first_message_prompt,
                agent_config=agent_config,
                run_id=run_id,
                experiment_id=self.config.experiment_id,
                workspace=workspace,
            )
            proc = IsolatedAgentProcess(
                config=agent_config,
                workspace=workspace,
                agent_dir=agent_dir,
                run_id=run_id,
                experiment_id=self.config.experiment_id,
                system_prompt=system_prompt,
                first_message=first_message,
            )
            processes.append(proc)
            hard_deadlines.append(
                time.monotonic() + agent_config.time_budget_minutes * 60 * 3
            )

        self._register_cleanup()
        self._processes = processes

        # Launch all agents simultaneously — no stagger, no communication
        for proc in processes:
            proc.start()

        print(f"[orchestrator] Launched {len(processes)} agent(s) simultaneously.")

        # Wait for all agents to finish or hit their hard deadlines
        self._wait_for_all(processes, hard_deadlines)

        print(f"[orchestrator] All {len(processes)} agents finished.")

    def run_single(
        self,
        experiment_dir: Path,
        system_prompt: str,
        first_message_prompt: str,
    ) -> None:
        """Launch one agent with double budget."""
        mode_dir = experiment_dir / f"mode_{self.config.mode}"
        run_id = self.config.experiment_id

        manifest_path = experiment_dir / "config.json"
        if not manifest_path.exists():
            manifest_path.write_text(json.dumps(self.config.to_dict(), indent=2))

        assert len(self.config.agents) == 1, "single_long mode expects exactly 1 agent"
        agent_config = self.config.agents[0]

        agent_dir, workspace = self._setup_agent(agent_config, mode_dir, run_id)
        first_message = _render_first_message(
            prompt=first_message_prompt,
            agent_config=agent_config,
            run_id=run_id,
            experiment_id=self.config.experiment_id,
            workspace=workspace,
        )
        proc = IsolatedAgentProcess(
            config=agent_config,
            workspace=workspace,
            agent_dir=agent_dir,
            run_id=run_id,
            experiment_id=self.config.experiment_id,
            system_prompt=system_prompt,
            first_message=first_message,
        )

        self._register_cleanup()
        self._processes = [proc]

        hard_deadline = time.monotonic() + agent_config.time_budget_minutes * 60 * 3
        proc.start()
        print(f"[orchestrator] Launched single agent {agent_config.agent_id}.")
        self._wait_for_all([proc], [hard_deadline])
        print("[orchestrator] Single agent finished.")
        self._finalize_single_mode(experiment_dir, agent_config)

    def run_merge(
        self,
        experiment_dir: Path,
        source_mode: str = "parallel",
        evaluate: bool = False,
    ) -> None:
        """Run the merge phase on a completed parallel experiment.

        Parameters
        ----------
        experiment_dir : Path
            The experiment root produced by a previous parallel run.
        source_mode : str
            Which mode directory to read agent results from (default "parallel").
        evaluate : bool
            If True, attempt to evaluate the merged train.py via SLURM.
        """
        from agent_workflow.merger import MergeOrchestrator

        print(f"[orchestrator] Starting merge phase for {experiment_dir.name}")
        merger = MergeOrchestrator(
            experiment_dir=experiment_dir,
            autoresearch_dir=self.autoresearch_dir,
            mode=source_mode,
        )
        results = merger.run(evaluate=evaluate, agent_based=True)
        print(
            f"[orchestrator] Merge complete. "
            f"best_individual={results.best_individual_val_bpb}, "
            f"merge={results.merge_val_bpb}, "
            f"merge_won={results.merge_won}"
        )

    def _setup_agent(
        self, agent_config: AgentConfig, mode_dir: Path, run_id: str
    ) -> tuple[Path, Path]:
        """Create workspace and result dirs for one agent. Returns (agent_dir, workspace)."""
        agent_dir = mode_dir / agent_config.agent_id
        workspace = agent_dir / "workspace"
        results_root = agent_dir / "results"

        branch_name = f"claude/{self.config.experiment_id}/{agent_config.agent_id}"

        create_workspace(
            autoresearch_dir=self.autoresearch_dir,
            workspace_path=workspace,
            branch_name=branch_name,
            train_budget_seconds=agent_config.train_time_budget_seconds,
            train_max_steps=agent_config.train_max_steps,
            run_id=run_id,
            agent_id=agent_config.agent_id,
            results_root=results_root,
            slurm_partition=self.config.slurm_partition,
            slurm_gres=self.config.slurm_gres,
            slurm_time=self.config.slurm_time,
            use_slurm=self.config.slurm_enabled,
            agent_time_budget_minutes=agent_config.time_budget_minutes,
            experiment_mode=self.config.mode,
            evaluator_lock_path=(
                mode_dir.parent / "evaluator.lock"
                if self.config.evaluator_concurrency == "serialized"
                else None
            ),
        )
        (agent_dir / "logs").mkdir(parents=True, exist_ok=True)
        return agent_dir, workspace

    def _finalize_single_mode(
        self, experiment_dir: Path, agent_config: AgentConfig
    ) -> None:
        """Post-run finalization for single-agent modes.

        Prefer the structured per-run log emitted by the runner so we capture the
        actual commit used for each training attempt. Fall back to workspace
        results.tsv only if structured data is unavailable.
        """
        import subprocess as _sp

        agent_dir = experiment_dir / f"mode_{self.config.mode}" / agent_config.agent_id
        workspace = agent_dir / "workspace"
        results_tsv = workspace / "results" / "results.tsv"
        training_runs_path = agent_dir / "results" / "training_runs.jsonl"
        report_path = agent_dir / "final_report.txt"

        print(f"[orchestrator] Running {self.config.mode} finalization...")

        rows, source = self._collect_single_mode_results(
            workspace=workspace,
            training_runs_path=training_runs_path,
            results_tsv_path=results_tsv,
        )
        if not rows:
            print("[orchestrator] No usable run records found — skipping finalization.")
            return

        best_row = min(rows, key=lambda row: row["val_bpb"])
        best_commit = str(best_row["commit"])
        best_bpb = float(best_row["val_bpb"])
        print(f"[orchestrator] Best result: commit={best_commit} val_bpb={best_bpb}")

        # Checkout the best commit in the workspace
        try:
            _sp.run(
                ["git", "checkout", best_commit, "--", "train.py"],
                cwd=workspace,
                check=True,
                capture_output=True,
            )
            print(f"[orchestrator] Checked out train.py from commit {best_commit}.")
        except _sp.CalledProcessError as e:
            print(f"[orchestrator] git checkout failed: {e.stderr.decode().strip()}")

        # Write final report
        ts = datetime.now(timezone.utc).isoformat()
        lines = [
            f"{self.config.mode} finalization report",
            f"experiment:   {experiment_dir.name}",
            f"agent:        {agent_config.agent_id}",
            f"timestamp:    {ts}",
            f"source:       {source}",
            f"best_commit:  {best_commit}",
            f"best_val_bpb: {best_bpb}",
            f"total_runs:   {len(rows)}",
            "",
            "All runs (chronological):",
        ]
        for row in rows:
            lines.append(
                f"  {str(row.get('commit', '?'))[:8]}  val_bpb={float(row['val_bpb']):>10.6f}  "
                f"{row.get('description','')}"
            )
        report_path.write_text("\n".join(lines) + "\n")
        print(f"[orchestrator] Final report written to {report_path}")

    def _collect_single_mode_results(
        self,
        workspace: Path,
        training_runs_path: Path,
        results_tsv_path: Path,
    ) -> tuple[list[dict], str]:
        """Collect finalization rows from structured logs or workspace fallback."""
        training_rows = self._load_training_run_rows(workspace, training_runs_path)
        if training_rows:
            return training_rows, "training_runs.jsonl"

        tsv_rows = self._load_results_tsv_rows(results_tsv_path)
        if tsv_rows:
            return tsv_rows, "workspace/results.tsv"

        return [], "none"

    def _load_training_run_rows(
        self,
        workspace: Path,
        training_runs_path: Path,
    ) -> list[dict]:
        """Return successful training runs with commit ids attached."""
        if not training_runs_path.exists():
            return []

        commit_messages = self._git_commit_messages(workspace)
        reflog_entries = self._git_reflog_entries(workspace)
        rows: list[dict] = []

        try:
            for raw_line in training_runs_path.read_text().splitlines():
                if not raw_line.strip():
                    continue
                entry = json.loads(raw_line)
                val_bpb = entry.get("val_bpb")
                if val_bpb is None:
                    continue
                try:
                    val_bpb_float = float(val_bpb)
                except (TypeError, ValueError):
                    continue

                commit = entry.get("commit")
                if not commit:
                    commit = self._infer_commit_from_reflog(
                        reflog_entries, entry.get("started_at")
                    )
                if not commit:
                    continue

                rows.append(
                    {
                        "commit": commit,
                        "val_bpb": val_bpb_float,
                        "description": commit_messages.get(commit, ""),
                    }
                )
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            print(f"[orchestrator] Failed to parse training_runs.jsonl: {exc}")
            return []

        return rows

    def _load_results_tsv_rows(self, results_tsv_path: Path) -> list[dict]:
        """Fallback: parse workspace results.tsv."""
        if not results_tsv_path.exists():
            return []

        rows: list[dict] = []
        try:
            with open(results_tsv_path) as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    try:
                        val_bpb = float(row["val_bpb"])
                        commit = row["commit"]
                    except (KeyError, TypeError, ValueError):
                        continue
                    rows.append(
                        {
                            "commit": commit,
                            "val_bpb": val_bpb,
                            "description": row.get("description", ""),
                        }
                    )
        except OSError as exc:
            print(f"[orchestrator] Failed to parse results.tsv: {exc}")
            return []

        return rows

    def _git_reflog_entries(self, workspace: Path) -> list[tuple[float, str]]:
        """Return reflog entries as (epoch_seconds, commit), oldest first."""
        try:
            proc = subprocess.run(
                [
                    "git",
                    "reflog",
                    "--date=unix",
                    "--format=%H%x09%gd",
                ],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.SubprocessError):
            return []

        entries: list[tuple[float, str]] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            try:
                commit, selector = line.split("\t", 1)
                ts_fragment = selector.split("@{", 1)[1].rstrip("}")
                entries.append((float(ts_fragment), commit.strip()))
            except (IndexError, ValueError):
                continue

        entries.sort(key=lambda item: item[0])
        return entries

    def _infer_commit_from_reflog(
        self,
        reflog_entries: list[tuple[float, str]],
        started_at: object,
    ) -> Optional[str]:
        """Infer the HEAD commit at a training run's start time."""
        try:
            started_at_float = float(started_at)
        except (TypeError, ValueError):
            return None

        chosen: Optional[str] = None
        for ts, commit in reflog_entries:
            if ts <= started_at_float:
                chosen = commit
            else:
                break
        return chosen

    def _git_commit_messages(self, workspace: Path) -> dict[str, str]:
        """Return commit subject lines keyed by full hash."""
        try:
            proc = subprocess.run(
                ["git", "log", "--format=%H%x09%s", "-n", "200"],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.SubprocessError):
            return {}

        messages: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            try:
                commit, subject = line.split("\t", 1)
            except ValueError:
                continue
            messages[commit.strip()] = subject.strip()
        return messages

    def _validate_gpu_assignments(self) -> None:
        if self.config.evaluator_concurrency == "serialized":
            return
        devices = [a.cuda_device for a in self.config.agents]
        if len(devices) != len(set(devices)):
            raise ValueError(
                f"Two agents assigned the same GPU: {devices}. "
                "Each agent must have a unique CUDA_VISIBLE_DEVICES."
            )

    def _wait_for_all(
        self,
        processes: list[IsolatedAgentProcess],
        hard_deadlines: list[float],
    ) -> None:
        """Poll until all processes finish or hard deadlines hit."""
        while True:
            now = time.monotonic()
            all_done = True
            for proc, deadline in zip(processes, hard_deadlines):
                if proc.is_alive():
                    if now >= deadline:
                        print(
                            f"[orchestrator] Hard deadline reached for "
                            f"{proc.config.agent_id}, sending SIGTERM."
                        )
                        proc.terminate()
                        time.sleep(2)
                        proc.kill()
                    else:
                        all_done = False
            if all_done:
                break
            time.sleep(self.POLL_INTERVAL_SEC)


def _render_first_message(
    prompt: str,
    agent_config: AgentConfig,
    run_id: str,
    experiment_id: str,
    workspace: Path,
) -> str:
    """Substitute prompt variables in the first message."""
    return (
        prompt
        .replace("{{AGENT_ID}}", agent_config.agent_id)
        .replace("{{AGENT_ROLE}}", agent_config.role or "general search agent")
        .replace("{{RUN_ID}}", run_id)
        .replace("{{EXPERIMENT_ID}}", experiment_id)
        .replace("{{TIME_BUDGET}}", str(agent_config.time_budget_minutes))
        .replace("{{TRAIN_TIME_BUDGET}}", str(agent_config.train_time_budget_seconds))
        .replace("{{WORKSPACE}}", str(workspace))
        .replace("{{BRANCH}}", f"claude/{experiment_id}/{agent_config.agent_id}")
    )
