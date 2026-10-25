"""Run a Claude Code sub-agent session.

Replaces run_single_agent.sh + OpenClaw invocation entirely.
Uses `claude --print` (non-interactive) with session continuation to run
a multi-turn agent loop that manages its own time budget.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_workflow.agents.base import AgentRunner
from agent_workflow.budgeting import BudgetTracker
from agent_workflow.config import AgentConfig
from agent_workflow.utils.log_parser import (
    parse_evaluator_mode,
    parse_total_seconds,
    parse_total_steps,
    parse_train_max_steps,
    parse_train_time_budget,
    parse_training_seconds,
    parse_val_bpb,
)


def _ts() -> str:
    """Return current local time as ISO-8601 string with second precision."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(log_fh, msg: str) -> None:
    """Write a timestamped system-event line and flush."""
    log_fh.write(f"[{_ts()}] {msg}\n")
    log_fh.flush()


def _workspace_git_state(workspace: Path) -> dict[str, object]:
    """Return lightweight git state for the workspace."""
    state: dict[str, object] = {
        "commit": None,
        "commit_short": None,
        "train_py_dirty": None,
    }
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if commit:
            state["commit"] = commit
            state["commit_short"] = commit[:8]
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "train.py"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        state["train_py_dirty"] = bool(dirty)
    except (OSError, subprocess.SubprocessError):
        pass

    return state


class ClaudeAgentRunner(AgentRunner):
    """Runs a Claude Code sub-agent via the `claude` CLI.

    The agent is invoked in a loop:
    - First turn: full first_message with context
    - Subsequent turns: "Continue. ~N min remaining. Keep experimenting."
    - Budget clock starts after first successful turn

    Failure modes handled:
    - API errors: retry with exponential backoff (no time refund)
    - Rate limits: backoff aggressively (no time refund)
    - No-reply turns: track count, rotate session after MAX_NOREPLY
    - Budget exceeded: break loop
    - Startup timeout: exit(2)
    """

    MAX_NOREPLY = 5
    MIN_TURN_INTERVAL_SEC = 5
    INITIAL_BACKOFF_SEC = 5
    MAX_BACKOFF_SEC = 60
    FIRST_TURN_TIMEOUT_SEC = 300  # 5 min cap per Claude turn
    MAX_TURN_TIMEOUT_SEC = 300    # 5 min cap per subsequent turn
    NO_PROGRESS_TURN_TIMEOUT_SEC = 90
    HEARTBEAT_INTERVAL_SEC = 30   # log "still alive" every 30s during a turn
    MIN_EVALS_FOR_PROMOTION = 2

    @staticmethod
    def _temperature_directive(temperature: Optional[float]) -> str:
        if temperature is None:
            return ""
        if temperature >= 1.0:
            return (
                "\n\n[SEARCH STYLE: Be creative and exploratory. "
                "Prefer bold, diverse changes over incremental refinement. "
                "Try unconventional hyperparameter combinations that you would not "
                "normally attempt. High variance in search is desirable.]"
            )
        if temperature < 0.5:
            return (
                "\n\n[SEARCH STYLE: Be conservative and methodical. "
                "Make only small, well-motivated incremental changes. "
                "Exploit the best-known region before exploring new directions. "
                "Low variance and high reliability are desirable.]"
            )
        return ""

    def run(
        self,
        run_id: str,
        experiment_id: str,
        system_prompt: str,
        first_message: str,
    ) -> None:
        """Run the agent loop until budget expires. Writes metadata.json at end."""
        config = self.config

        effective_system_prompt = system_prompt + self._temperature_directive(
            config.temperature
        )

        self._active_proc: Optional[subprocess.Popen] = None
        self._planned_turn_stop = False
        self._planned_turn_stop_reason = ""
        self._pending_turn_stop_at: Optional[float] = None

        budget = BudgetTracker(
            wall_clock_budget_seconds=config.time_budget_minutes * 60,
            train_time_budget_seconds=config.train_time_budget_seconds,
            startup_deadline_seconds=config.time_budget_minutes * 60 + 300,
        )

        session_id = f"{experiment_id}-{config.agent_id}-{int(time.time())}-{os.getpid()}"
        env = self._build_env(run_id, experiment_id)
        session_log = self.logs_dir / "run_agent.log"

        start_time = datetime.now(timezone.utc).isoformat()
        self.turn_count = 0
        self.turns_log_path = self.results_dir / "turns.jsonl"
        self.turns_log_path.write_text("")
        self.training_runs_log_path = self.results_dir / "training_runs.jsonl"
        self.training_runs_log_path.write_text("")
        self.reevaluation_log_path = self.results_dir / "reevaluations.jsonl"
        self.reevaluation_log_path.write_text("")
        self._cumulative_chars = 0
        self._turn_records: list[dict] = []
        self._training_run_count = 0
        self._candidate_eval_history: dict[str, list[float]] = {}
        self._incumbent_candidate_id: Optional[str] = None
        self._pending_reevaluation: Optional[dict] = None
        self._current_turn_context: dict[str, object] = {}
        backoff = self.INITIAL_BACKOFF_SEC
        noreply_count = 0
        first_turn = True

        with open(session_log, "w") as log_fh:
            _log(log_fh, f"[{config.agent_id}] Session starting: {session_id}")

            _stop_watcher = threading.Event()
            _observed_val_bpbs: list[float] = []

            # GPU allocation watcher — starts budget clock
            threading.Thread(
                target=self._watch_gpu_allocation,
                args=(budget, log_fh, _stop_watcher),
                daemon=True,
            ).start()

            # Workspace event watcher — training trigger/result/file changes
            threading.Thread(
                target=self._watch_workspace_events,
                args=(log_fh, _stop_watcher, _observed_val_bpbs),
                daemon=True,
            ).start()

            threading.Thread(
                target=self._watch_budget_expiry,
                args=(budget, log_fh, _stop_watcher),
                daemon=True,
            ).start()

            while True:
                if budget.startup_expired():
                    msg = f"[{config.agent_id}] ABORT: no successful turn within startup deadline."
                    _log(log_fh, msg)
                    sys.stderr.write(msg + "\n")
                    break

                if budget.should_stop():
                    _log(log_fh, f"[{config.agent_id}] Budget expired — stopping.")
                    break

                if first_turn:
                    memory_context_visible = False
                    memory_context_entries = 0
                    shared_memory_context_visible = False
                    shared_memory_context_entries = 0
                    protocol_mode = "bootstrap"
                    turn_msg = first_message
                    turn_timeout = min(
                        self.FIRST_TURN_TIMEOUT_SEC,
                        max(int(budget.remaining_seconds()), 60),
                    )
                    _log(log_fh, f"[{config.agent_id}] Turn {self.turn_count} starting (first turn).")
                else:
                    mins_left = budget.remaining_minutes()
                    secs_left = int(budget.remaining_seconds())
                    # Expected wall time per run: train_budget + ~90s compile/eval overhead
                    run_wall_sec = config.train_time_budget_seconds + 90
                    run_wall_min = round(run_wall_sec / 60)
                    if secs_left < run_wall_sec + 60:
                        time_guidance = (
                            f"WARNING: only ~{mins_left} min left — NOT ENOUGH for another "
                            f"training run (~{run_wall_min} min each). "
                            f"Do NOT start a new run. Instead review results.tsv, "
                            f"ensure the best result is committed, and stop."
                        )
                    else:
                        runs_remaining = secs_left // run_wall_sec
                        time_guidance = (
                            f"Each training run takes ~{run_wall_min} min. "
                            f"You can fit approximately {runs_remaining} more run(s)."
                        )
                    turn_msg = (
                        f"Current workspace: {self.workspace}. Stay in this directory, "
                        "use only the local worker scripts here, and do not inspect or "
                        "mention any other repository path or external GPU environment. "
                        "Do not modify or delete any helper scripts; only `train.py` may change. "
                        f"Continue the research. ~{mins_left} min remaining in budget. "
                        f"{time_guidance} "
                        "In this Claude turn, recover WORKER_JOB_ID from `.worker_job_id` or "
                        "start and save it if missing. Determine the next STEP from "
                        "`reasoning/trace.jsonl`. Run at most one new experiment iteration: "
                        "pick one hypothesis, edit train.py, commit it, save the snapshot, run "
                        "exactly one training run, update results.tsv and the snapshot, then stop "
                        "and return a brief summary. Do not start a second training run in this turn. "
                        "If you cannot decide on a concrete run quickly, stop and summarize instead of "
                        "thinking indefinitely."
                    )
                    protocol_directive, protocol_mode = self._build_protocol_directive()
                    if protocol_directive:
                        turn_msg = f"{protocol_directive}\n\n---\n\n{turn_msg}"
                    memory_context_visible = False
                    memory_context_entries = 0
                    shared_memory_context_visible = False
                    shared_memory_context_entries = 0
                    if self.config.use_shared_memory:
                        memory = self._build_shared_memory_context()
                        shared_memory_context_visible = bool(memory)
                        shared_memory_context_entries = self._count_shared_memory_entries()
                        if memory:
                            turn_msg = f"{memory}\n\n---\n\n{turn_msg}"
                    if self.config.use_external_memory:
                        memory = self._build_memory_context()
                        memory_context_visible = bool(memory)
                        memory_context_entries = self._count_private_memory_entries()
                        if memory:
                            turn_msg = f"{memory}\n\n---\n\n{turn_msg}"
                    turn_timeout = min(secs_left, self.MAX_TURN_TIMEOUT_SEC)
                    _log(log_fh, f"[{config.agent_id}] Turn {self.turn_count} starting (~{mins_left} min remaining).")

                self._current_turn_context = {
                    "experiment_id": experiment_id,
                    "agent_id": config.agent_id,
                    "protocol_mode": protocol_mode,
                    "memory_context_visible": memory_context_visible,
                    "memory_context_entries": memory_context_entries,
                    "shared_memory_context_visible": shared_memory_context_visible,
                    "shared_memory_context_entries": shared_memory_context_entries,
                    "pending_reevaluation_candidate_id": (
                        self._pending_reevaluation.get("candidate_id")
                        if isinstance(self._pending_reevaluation, dict)
                        else None
                    ),
                }

                log_fh.write(
                    f"[{_ts()}] [{config.agent_id}] Turn {self.turn_count} message begin\n"
                )
                log_fh.write(turn_msg.rstrip() + "\n")
                log_fh.write(
                    f"[{_ts()}] [{config.agent_id}] Turn {self.turn_count} message end\n"
                )
                log_fh.flush()

                turn_start = time.monotonic()
                self._training_runs_this_turn = 0
                self._turn_evaluator_wall_seconds = 0.0
                self._pending_turn_stop_at = None
                self._turn_started_at = turn_start
                self._turn_training_started = False

                # Heartbeat thread: logs "still alive" every HEARTBEAT_INTERVAL_SEC
                _turn_done = threading.Event()
                threading.Thread(
                    target=self._heartbeat,
                    args=(config.agent_id, self.turn_count, turn_start, _turn_done, log_fh),
                    daemon=True,
                ).start()

                exit_code, output, usage = self._run_turn(
                    turn_msg=turn_msg,
                    session_id=session_id,
                    system_prompt=effective_system_prompt,
                    timeout_seconds=turn_timeout,
                    env=env,
                    log_fh=log_fh,
                )
                _turn_done.set()
                turn_elapsed = time.monotonic() - turn_start

                if self._planned_turn_stop and exit_code != 0:
                    stripped_output = output.strip()
                    hook_cancelled = (
                        "SessionEnd hook" in stripped_output
                        and "Hook cancelled" in stripped_output
                    )
                    if not stripped_output or hook_cancelled:
                        exit_code = 0
                        output = f"[{self._planned_turn_stop_reason}]"
                self._planned_turn_stop = False
                self._planned_turn_stop_reason = ""

                system_prompt_chars = len(effective_system_prompt) if effective_system_prompt else 0
                turn_msg_chars = len(turn_msg)
                response_chars = len(output)
                evaluator_wall_seconds = float(
                    getattr(self, "_turn_evaluator_wall_seconds", 0.0) or 0.0
                )
                deliberation_wall_seconds = max(turn_elapsed - evaluator_wall_seconds, 0.0)

                input_tokens = _coerce_token_count(usage.get("input_tokens"))
                if input_tokens is None:
                    input_tokens = (system_prompt_chars + turn_msg_chars) // 4

                output_tokens = _coerce_token_count(usage.get("output_tokens"))
                if output_tokens is None:
                    output_tokens = response_chars // 4

                self._cumulative_chars += system_prompt_chars + turn_msg_chars + response_chars
                turn_record = {
                    "turn": self.turn_count,
                    "timestamp": time.time(),
                    "experiment_id": experiment_id,
                    "agent_id": config.agent_id,
                    "model": self.config.model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "system_prompt_chars": system_prompt_chars,
                    "turn_msg_chars": turn_msg_chars,
                    "response_chars": response_chars,
                    "context_fill_ratio": self._estimate_context_fill(),
                    "wall_clock_seconds": turn_elapsed,
                    "agent_deliberation_wall_seconds": deliberation_wall_seconds,
                    "evaluator_wall_seconds": evaluator_wall_seconds,
                    "protocol_mode": protocol_mode,
                    "memory_context_visible": memory_context_visible,
                    "memory_context_entries": memory_context_entries,
                    "shared_memory_context_visible": shared_memory_context_visible,
                    "shared_memory_context_entries": shared_memory_context_entries,
                    "pending_reevaluation_candidate_id": (
                        self._pending_reevaluation.get("candidate_id")
                        if isinstance(self._pending_reevaluation, dict)
                        else None
                    ),
                }
                self._turn_records.append(turn_record)
                with open(self.turns_log_path, "a") as turns_fh:
                    turns_fh.write(json.dumps(turn_record) + "\n")

                _log(log_fh,
                    f"[{config.agent_id}] Turn {self.turn_count} finished: exit={exit_code} elapsed={turn_elapsed:.1f}s")
                if output:
                    log_fh.write(output[:2000] + ("\n...(truncated)\n" if len(output) > 2000 else "\n"))
                    log_fh.flush()

                is_noreply = "No reply from agent" in output or (not output.strip() and exit_code == 0)
                is_ratelimit = "rate limit" in output.lower() or "rate_limit" in output.lower()
                is_error = exit_code != 0

                if is_error:
                    _log(log_fh, f"[{config.agent_id}] Error turn, retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF_SEC)
                elif is_ratelimit:
                    _log(log_fh, f"[{config.agent_id}] Rate limit, backing off {backoff}s...")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF_SEC)
                elif is_noreply:
                    noreply_count += 1
                    _log(log_fh, f"[{config.agent_id}] No-reply turn #{noreply_count}/{self.MAX_NOREPLY}")
                    if noreply_count >= self.MAX_NOREPLY:
                        noreply_count = 0
                        session_id = f"{experiment_id}-{config.agent_id}-{int(time.time())}-{os.getpid()}"
                        first_turn = True
                        _log(log_fh, f"[{config.agent_id}] Session rotated to {session_id}")
                    _enforce_min_interval(turn_elapsed, self.MIN_TURN_INTERVAL_SEC)
                else:
                    backoff = self.INITIAL_BACKOFF_SEC
                    noreply_count = 0
                    self.turn_count += 1

                    if not budget.budget_started():
                        budget.start_budget_clock()
                        _log(log_fh,
                            f"[{config.agent_id}] Budget clock started (fallback, no gpu_allocated_at) — "
                            f"{budget.wall_clock_budget_seconds}s remaining.")
                    first_turn = False
                    _enforce_min_interval(turn_elapsed, self.MIN_TURN_INTERVAL_SEC)

        _stop_watcher.set()

        end_time = datetime.now(timezone.utc).isoformat()
        self._write_metadata(
            run_id=run_id,
            experiment_id=experiment_id,
            start_time=start_time,
            end_time=end_time,
            total_turns=self.turn_count,
            budget_seconds=config.time_budget_minutes * 60,
            observed_val_bpbs=_observed_val_bpbs,
        )

    # ------------------------------------------------------------------
    # Background threads
    # ------------------------------------------------------------------

    def _watch_gpu_allocation(
        self,
        budget: BudgetTracker,
        log_fh,
        stop_event: threading.Event,
    ) -> None:
        """Start budget clock when gpu_allocated_at appears."""
        marker = self.workspace / "gpu_allocated_at"
        while not stop_event.is_set():
            if not budget.budget_started() and marker.exists():
                budget.start_budget_clock()
                ts = marker.read_text().strip()
                _log(log_fh,
                    f"[{self.config.agent_id}] GPU allocated at {ts} — "
                    f"budget clock started ({budget.wall_clock_budget_seconds}s).")
                return
            stop_event.wait(2)

    def _watch_workspace_events(
        self,
        log_fh,
        stop_event: threading.Event,
        observed_val_bpbs: list,
    ) -> None:
        """Log key workspace file events: trigger, result, train.py edits, results.tsv rows."""
        ws = self.workspace
        agent_id = self.config.agent_id

        trigger = ws / "run.trigger"
        result = ws / "run.result"
        train_out = ws / "logs" / "train_current.out"
        train_py = ws / "train.py"
        results_tsv = ws / "results" / "results.tsv"
        trace_path = self.agent_dir / "reasoning" / "trace.jsonl"

        trigger_seen = False
        result_seen = False
        run_count = 0
        run_wall_start: Optional[float] = None
        train_py_mtime: Optional[float] = None
        results_tsv_lines = 0
        train_out_lines = 0
        shared_logged_steps: set[int] = set()
        run_git_state: dict[str, object] = {
            "commit": None,
            "commit_short": None,
            "train_py_dirty": None,
        }
        active_run_context: Optional[dict[str, object]] = None

        while not stop_event.is_set():
            # Repair shared memory symlink if agent destroyed it (e.g. git checkout)
            if self.config.use_shared_memory:
                shared_ws = ws / "shared_results_log.jsonl"
                if not shared_ws.exists():
                    # Find the experiment-level shared log
                    shared_src = self.agent_dir.parent.parent / "shared_results_log.jsonl"
                    if shared_src.exists():
                        try:
                            shared_ws.symlink_to(shared_src)
                        except OSError:
                            pass

            # train.py modified → log diff vs baseline so we see what changed
            try:
                mtime = train_py.stat().st_mtime if train_py.exists() else None
                if mtime is not None and mtime != train_py_mtime:
                    if train_py_mtime is not None:
                        _log(log_fh, f"[{agent_id}] train.py modified.")
                        _log_train_diff(train_py, log_fh, agent_id)
                    train_py_mtime = mtime
            except OSError:
                pass

            # results.tsv new row → agent logged a result (log only, shared memory
            # is populated directly from training run completion above)
            try:
                if results_tsv.exists():
                    lines = [l for l in results_tsv.read_text().splitlines() if l.strip()]
                    if len(lines) > results_tsv_lines:
                        for row in lines[results_tsv_lines:]:
                            if row.startswith("commit"):
                                continue
                            _log(log_fh, f"[{agent_id}] results.tsv: {row}")
                        results_tsv_lines = len(lines)
            except OSError:
                pass

            # run.trigger appeared → training started
            if not trigger_seen and trigger.exists():
                trigger_seen = True
                result_seen = False
                run_count += 1
                self._turn_training_started = True
                run_wall_start = time.time()
                run_git_state = _workspace_git_state(ws)
                active_run_context = self._prepare_training_run_context(run_git_state)
                if train_out.exists():
                    try:
                        train_out_lines = len(train_out.read_text().splitlines())
                    except OSError:
                        train_out_lines = 0
                else:
                    train_out_lines = 0
                _log(log_fh, f"[{agent_id}] Training run #{run_count} started.")

            # stream new lines from train_current.out while a run is active
            if trigger_seen and not result_seen:
                try:
                    if train_out.exists():
                        all_lines = train_out.read_text().splitlines()
                        new_lines = all_lines[train_out_lines:]
                        for line in new_lines:
                            log_fh.write(f"[{_ts()}] [{agent_id}][training] {line}\n")
                        if new_lines:
                            log_fh.flush()
                        train_out_lines = len(all_lines)
                except OSError:
                    pass

            # run.result appeared → training finished
            if trigger_seen and not result_seen and result.exists():
                result_seen = True
                trigger_seen = False
                finished_at = time.time()
                wall_seconds = finished_at - run_wall_start if run_wall_start else None
                elapsed = f"{wall_seconds:.0f}s" if wall_seconds is not None else "?s"
                val_bpb = None
                try:
                    for src in (result, train_out):
                        if src.exists():
                            for line in src.read_text().splitlines():
                                if line.startswith("val_bpb:"):
                                    val_bpb = line.split(":", 1)[1].strip()
                                    break
                        if val_bpb:
                            break
                except OSError:
                    pass

                parsed_val_bpb = parse_val_bpb(train_out) if train_out.exists() else None
                if parsed_val_bpb is None and val_bpb is not None:
                    try:
                        parsed_val_bpb = float(val_bpb)
                    except ValueError:
                        parsed_val_bpb = None
                training_seconds = (
                    parse_training_seconds(train_out) if train_out.exists() else None
                )
                train_total_seconds = (
                    parse_total_seconds(train_out) if train_out.exists() else None
                )
                total_steps = parse_total_steps(train_out) if train_out.exists() else None
                evaluator_mode = (
                    parse_evaluator_mode(train_out) if train_out.exists() else None
                )
                train_time_budget = (
                    parse_train_time_budget(train_out) if train_out.exists() else None
                )
                train_max_steps = (
                    parse_train_max_steps(train_out) if train_out.exists() else None
                )
                if wall_seconds is not None:
                    self._turn_evaluator_wall_seconds = (
                        float(getattr(self, "_turn_evaluator_wall_seconds", 0.0) or 0.0)
                        + float(wall_seconds)
                    )
                self._training_run_count += 1
                self._training_runs_this_turn = getattr(
                    self, "_training_runs_this_turn", 0
                ) + 1
                training_run_record = self._record_completed_training_run(
                    run_index=self._training_run_count,
                    run_git_state=run_git_state,
                    run_context=active_run_context,
                    run_wall_start=run_wall_start,
                    finished_at=finished_at,
                    wall_seconds=wall_seconds,
                    training_seconds=training_seconds,
                    train_total_seconds=train_total_seconds,
                    total_steps=total_steps,
                    evaluator_mode=evaluator_mode,
                    train_time_budget=train_time_budget,
                    train_max_steps=train_max_steps,
                    parsed_val_bpb=parsed_val_bpb,
                )

                # Populate shared memory from completed training run
                # (more reliable than waiting for agent to write results.tsv)
                if self.config.use_shared_memory and parsed_val_bpb is not None:
                    desc = (
                        training_run_record.get("git_message")
                        or training_run_record.get("hypothesis")
                        or "run"
                    )
                    self._append_shared_log(
                        step=self._training_run_count,
                        hypothesis=desc[:60],
                        val_bpb=parsed_val_bpb,
                        accepted=parsed_val_bpb < min(observed_val_bpbs) if observed_val_bpbs else True,
                    )

                if val_bpb:
                    try:
                        observed_val_bpbs.append(float(val_bpb))
                    except ValueError:
                        pass
                    _log(log_fh, f"[{agent_id}] Training run #{run_count} done — val_bpb: {val_bpb} (elapsed: {elapsed})")
                else:
                    status = ""
                    try:
                        status = result.read_text().strip().splitlines()[0] if result.exists() else "no result"
                    except OSError:
                        pass
                    _log(log_fh, f"[{agent_id}] Training run #{run_count} done — {status} (elapsed: {elapsed})")
                    _dump_slurm_failure_logs(ws, agent_id, run_count, log_fh)

                self._pending_turn_stop_at = time.monotonic() + 2.0
                active_run_context = None

            if (
                self._pending_turn_stop_at is not None
                and time.monotonic() >= self._pending_turn_stop_at
                and not trigger.exists()
            ):
                self._pending_turn_stop_at = None
                self._terminate_active_turn(
                    log_fh,
                    f"[{agent_id}] Completed planned training run for this turn.",
                    planned=True,
                )

            if (
                getattr(self, "_turn_started_at", None) is not None
                and not getattr(self, "_turn_training_started", False)
                and time.monotonic() - self._turn_started_at >= self.NO_PROGRESS_TURN_TIMEOUT_SEC
            ):
                self._turn_started_at = None
                self._terminate_active_turn(
                    log_fh,
                    f"[{agent_id}] No training run started within "
                    f"{self.NO_PROGRESS_TURN_TIMEOUT_SEC}s — ending turn to preserve budget.",
                    planned=True,
                )

            stop_event.wait(2)

    def _watch_budget_expiry(
        self,
        budget: BudgetTracker,
        log_fh,
        stop_event: threading.Event,
    ) -> None:
        """Stop an active Claude turn once wall-clock budget has expired.

        If a training run is still active, wait for that run to finish so we do not
        kill the worker mid-train. As soon as no run is active, terminate the Claude
        subprocess so the outer loop can exit cleanly.
        """
        budget_expired_logged = False
        trigger = self.workspace / "run.trigger"

        while not stop_event.is_set():
            if not budget.budget_started() or not budget.should_stop():
                stop_event.wait(2)
                continue

            proc = self._active_proc
            if proc is None or proc.poll() is not None:
                return

            if trigger.exists():
                if not budget_expired_logged:
                    _log(
                        log_fh,
                        f"[{self.config.agent_id}] Budget expired during an active training run; "
                        "waiting for the run to finish before stopping the turn.",
                    )
                    budget_expired_logged = True
                stop_event.wait(2)
                continue

            self._terminate_active_turn(
                log_fh,
                f"[{self.config.agent_id}] Budget expired — terminating active Claude turn.",
                planned=True,
            )
            return

    def _heartbeat(
        self,
        agent_id: str,
        turn_num: int,
        turn_start: float,
        done_event: threading.Event,
        log_fh,
    ) -> None:
        """Log 'still alive' every HEARTBEAT_INTERVAL_SEC during a turn."""
        while not done_event.wait(self.HEARTBEAT_INTERVAL_SEC):
            elapsed = time.monotonic() - turn_start
            _log(log_fh, f"[{agent_id}] Turn {turn_num} still running ({elapsed:.0f}s elapsed).")

    # ------------------------------------------------------------------
    # Core turn execution
    # ------------------------------------------------------------------

    def _parse_claude_output(self, raw_stdout: str) -> tuple[str, dict]:
        """Parse JSON output from claude CLI. Returns (text_response, usage_dict)."""
        try:
            data = json.loads(raw_stdout)
        except json.JSONDecodeError:
            return raw_stdout, {}

        if not isinstance(data, dict):
            return raw_stdout, {}

        text = data.get("result", raw_stdout)
        usage = data.get("usage", {})
        return str(text), usage if isinstance(usage, dict) else {}

    def _run_turn(
        self,
        turn_msg: str,
        session_id: str,
        system_prompt: str,
        timeout_seconds: int,
        env: dict,
        log_fh,
    ) -> tuple[int, str, dict]:
        """Invoke `claude --print` for one turn, streaming output to log in real-time."""
        cmd = [
            "claude",
            "--print",
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]
        if self.config.model:
            cmd += ["--model", self.config.model]
        if system_prompt:
            cmd += ["--system-prompt", system_prompt]
        cmd += [turn_msg]

        output_lines: list[str] = []

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.workspace),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._active_proc = proc

            # Stream stdout in real-time
            def _stream_stdout():
                for line in proc.stdout:
                    output_lines.append(line)
                    log_fh.write(f"  {line}" if not line.startswith("[") else line)
                    log_fh.flush()

            stdout_thread = threading.Thread(target=_stream_stdout, daemon=True)
            stdout_thread.start()

            try:
                proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                return -1, f"[timeout after {timeout_seconds}s]", {}

            stdout_thread.join(timeout=5)
            stderr = proc.stderr.read()
            self._active_proc = None
            output, usage = self._parse_claude_output("".join(output_lines))
            if stderr:
                output += "\n[stderr]\n" + stderr
            return proc.returncode, output, usage

        except FileNotFoundError:
            return -2, "[claude CLI not found in PATH]", {}
        except Exception as e:
            return -3, f"[exception: {e}]", {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _estimate_context_fill(self) -> float:
        """Estimate context fill ratio c/K from cumulative character count."""
        estimated_tokens = self._cumulative_chars / 4
        return min(estimated_tokens / 200_000, 1.0)

    def _terminate_active_turn(self, log_fh, reason: str, planned: bool = False) -> None:
        """Terminate the active Claude subprocess if it is still running."""
        proc = self._active_proc
        if proc is None or proc.poll() is not None:
            return
        if planned:
            self._planned_turn_stop = True
            self._planned_turn_stop_reason = reason
        _log(log_fh, reason)
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def _build_memory_context(self) -> str:
        """Build a compact experiment log from training_runs.jsonl (primary) or results.tsv."""
        lines = [
            "# Experiment Log",
            "| # | change | bpb | Δ | best |",
            "|---|--------|-----|---|------|",
        ]
        best_bpb = float("inf")
        prev_bpb: Optional[float] = None
        step = 0

        # Primary source: training_runs.jsonl (written by monitoring loop, always reliable)
        if self.training_runs_log_path.exists():
            for raw_line in self.training_runs_log_path.read_text().splitlines():
                if not raw_line.strip():
                    continue
                try:
                    entry = json.loads(raw_line)
                    bpb_val = entry.get("val_bpb")
                    if bpb_val is None:
                        continue
                    desc = (
                        entry.get("git_message")
                        or entry.get("hypothesis")
                        or entry.get("strategy_category")
                        or "?"
                    )[:40]
                    step += 1
                    delta = (
                        f"{bpb_val - prev_bpb:+.4f}" if prev_bpb is not None else "—"
                    )
                    is_best = "✓" if bpb_val < best_bpb else ""
                    if bpb_val < best_bpb:
                        best_bpb = bpb_val
                    lines.append(
                        f"| {step} | {desc} | {bpb_val:.4f} | {delta} | {is_best} |"
                    )
                    prev_bpb = bpb_val
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

        # Fallback: results.tsv in workspace (agent-written, sometimes incomplete)
        if step == 0:
            results_tsv = self.workspace / "results" / "results.tsv"
            if results_tsv.exists():
                for raw_line in results_tsv.read_text().splitlines():
                    if not raw_line.strip() or raw_line.startswith("commit"):
                        continue
                    try:
                        parts = raw_line.split("\t")
                        if len(parts) < 5:
                            continue
                        bpb_str = parts[1]
                        if bpb_str in ("0.000000", ""):
                            continue
                        bpb_val = float(bpb_str)
                        desc = parts[4][:40]
                        step += 1
                        delta = (
                            f"{bpb_val - prev_bpb:+.4f}" if prev_bpb is not None else "—"
                        )
                        is_best = "✓" if bpb_val < best_bpb else ""
                        if bpb_val < best_bpb:
                            best_bpb = bpb_val
                        lines.append(
                            f"| {step} | {desc} | {bpb_val:.4f} | {delta} | {is_best} |"
                        )
                        prev_bpb = bpb_val
                    except (ValueError, IndexError):
                        continue

        return "\n".join(lines) if len(lines) > 3 else ""

    def _build_shared_memory_context(self) -> str:
        """Build a compact experiment log across all agents."""
        shared_path = self.workspace / "shared_results_log.jsonl"
        if not shared_path.exists():
            return ""

        lines = [
            "# Shared Experiment Log (all agents)",
            "| agent | # | change | bpb | kept |",
            "|-------|---|--------|-----|------|",
        ]

        for raw_line in shared_path.read_text().splitlines():
            if not raw_line.strip():
                continue
            try:
                entry = json.loads(raw_line)
                agent = str(entry.get("agent_id", "?"))[-4:]
                step = entry.get("step", "?")
                hypothesis = str(entry.get("hypothesis", "?"))[:35]
                bpb = entry.get("val_bpb")
                accepted = "✓" if entry.get("accepted") else "✗"
                if bpb is not None:
                    lines.append(
                        f"| {agent} | {step} | {hypothesis} | {float(bpb):.4f} | {accepted} |"
                    )
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        return "\n".join(lines) if len(lines) > 3 else ""

    def _append_shared_log(self, step, hypothesis, val_bpb, accepted) -> None:
        """Append one completed experiment result to the shared JSONL log."""
        shared_path = self.workspace / "shared_results_log.jsonl"
        if not shared_path.exists():
            return

        record = json.dumps(
            {
                "agent_id": self.config.agent_id,
                "step": step,
                "hypothesis": str(hypothesis)[:60],
                "val_bpb": val_bpb,
                "accepted": accepted,
                "timestamp": time.time(),
            }
        )
        with open(shared_path, "a") as shared_fh:
            fcntl.flock(shared_fh, fcntl.LOCK_EX)
            shared_fh.write(record + "\n")
            fcntl.flock(shared_fh, fcntl.LOCK_UN)

    def _build_env(self, run_id: str, experiment_id: str) -> dict:
        env = os.environ.copy()
        env["RUN_ID"] = run_id
        env["AGENT_ID"] = self.config.agent_id
        env["RESULTS_ROOT"] = str(self.results_dir)
        env["AUTOSEARCH_TIME_BUDGET"] = str(self.config.train_time_budget_seconds)
        if self.config.train_max_steps is not None:
            env["AUTOSEARCH_MAX_STEPS"] = str(self.config.train_max_steps)
            env["AUTOSEARCH_EVALUATOR_MODE"] = "fixed_steps"
        else:
            env.pop("AUTOSEARCH_MAX_STEPS", None)
            env["AUTOSEARCH_EVALUATOR_MODE"] = "fixed_time"
        env["CUDA_VISIBLE_DEVICES"] = self.config.cuda_device
        env["EXPERIMENT_ID"] = experiment_id
        extra_path = ":".join([
            str(Path.home() / ".local" / "bin"),
            str(Path.home() / "miniforge3" / "bin"),
        ])
        env["PATH"] = extra_path + ":" + env.get("PATH", "")
        return env

    def _count_nonempty_lines(self, path: Path) -> int:
        if not path.exists():
            return 0
        try:
            return sum(1 for line in path.read_text().splitlines() if line.strip())
        except OSError:
            return 0

    def _count_private_memory_entries(self) -> int:
        # Primary: training_runs.jsonl (monitoring loop, always reliable)
        if self.training_runs_log_path.exists():
            count = self._count_nonempty_lines(self.training_runs_log_path)
            if count > 0:
                return count
        # Fallback: results.tsv in workspace (agent-written, sometimes incomplete)
        tsv = self.workspace / "results" / "results.tsv"
        if tsv.exists():
            count = self._count_nonempty_lines(tsv)
            return max(0, count - 1)  # subtract header
        return self._count_nonempty_lines(self.agent_dir / "reasoning" / "trace.jsonl")

    def _count_shared_memory_entries(self) -> int:
        return self._count_nonempty_lines(self.workspace / "shared_results_log.jsonl")

    def _append_jsonl(self, path: Path, record: dict) -> None:
        with open(path, "a") as fh:
            fh.write(json.dumps(record) + "\n")

    def _mean(self, values: list[float]) -> Optional[float]:
        if not values:
            return None
        return sum(values) / len(values)

    def _stddev(self, values: list[float]) -> Optional[float]:
        if len(values) < 2:
            return 0.0 if values else None
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        return variance ** 0.5

    def _classify_strategy_category(
        self,
        hypothesis: str,
        expected_effect: str = "",
    ) -> str:
        text = f"{hypothesis} {expected_effect}".lower().replace("_", " ")
        tokens = set(re.findall(r"[a-z0-9]+", text))
        if any(
            (phrase in text if " " in phrase else phrase in tokens)
            for phrase in ["lr", "learning rate", "scheduler", "warmup", "adam", "optimizer"]
        ):
            return "optimization"
        if any(
            (phrase in text if " " in phrase else phrase in tokens)
            for phrase in ["dropout", "weight decay", "regularization", "label smoothing"]
        ):
            return "regularization"
        if any(
            (phrase in text if " " in phrase else phrase in tokens)
            for phrase in ["batch", "augment", "mixup", "cutmix", "crop", "flip", "data"]
        ):
            return "data_pipeline"
        if any(
            (phrase in text if " " in phrase else phrase in tokens)
            for phrase in ["embed", "hidden", "width", "depth", "conv", "architecture", "head", "layer"]
        ):
            return "architecture"
        if any(
            (phrase in text if " " in phrase else phrase in tokens)
            for phrase in ["memory", "cache", "shared", "workspace", "retrieve"]
        ):
            return "memory_or_coordination"
        return "other"

    def _latest_snapshot_metadata(self, commit: Optional[str]) -> dict[str, object]:
        snapshots_dir = self.agent_dir / "snapshots"
        if not snapshots_dir.exists():
            return {}

        candidates: list[dict[str, object]] = []
        for meta_path in sorted(snapshots_dir.glob("step_*/metadata.json"), reverse=True):
            try:
                metadata = json.loads(meta_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            meta_commit = str(metadata.get("git_commit") or "")
            if commit and meta_commit and meta_commit == commit:
                return metadata
            candidates.append(metadata)

        return candidates[0] if candidates else {}

    def _candidate_context_for_commit(self, commit: Optional[str]) -> dict[str, object]:
        snapshot = self._latest_snapshot_metadata(commit)
        snapshot_step = snapshot.get("step_index")
        hypothesis = str(snapshot.get("hypothesis") or "")
        expected_effect = str(snapshot.get("expected_effect") or "")
        resolved_commit = str(commit or snapshot.get("git_commit") or "")
        commit_fragment = resolved_commit[:12] if resolved_commit else f"run{self._training_run_count + 1}"
        candidate_id = f"{self.config.agent_id}:{commit_fragment}"
        return {
            "candidate_id": candidate_id,
            "candidate_commit": resolved_commit or None,
            "snapshot_step_index": snapshot_step,
            "hypothesis": hypothesis,
            "expected_effect": expected_effect,
            "git_message": str(snapshot.get("git_message") or ""),
            "strategy_category": self._classify_strategy_category(hypothesis, expected_effect),
            "shared_memory_context_visible": bool(
                self._current_turn_context.get("shared_memory_context_visible")
            ),
            "shared_memory_context_entries": int(
                self._current_turn_context.get("shared_memory_context_entries") or 0
            ),
            "memory_context_visible": bool(
                self._current_turn_context.get("memory_context_visible")
            ),
            "memory_context_entries": int(
                self._current_turn_context.get("memory_context_entries") or 0
            ),
        }

    def _current_incumbent_mean(self) -> tuple[Optional[str], Optional[float]]:
        incumbent_id = self._incumbent_candidate_id
        if not incumbent_id:
            return None, None
        return incumbent_id, self._mean(self._candidate_eval_history.get(incumbent_id, []))

    def _build_protocol_directive(self) -> tuple[str, str]:
        pending = self._pending_reevaluation
        if not pending:
            return "", "explore"

        candidate_id = str(pending.get("candidate_id") or "unknown")
        candidate_commit = str(pending.get("candidate_commit") or "")
        incumbent_id = str(pending.get("incumbent_candidate_id_before") or "none")
        incumbent_mean = pending.get("incumbent_mean_before")
        candidate_val = pending.get("initial_val_bpb")
        incumbent_fragment = (
            f"{incumbent_mean:.6f}" if isinstance(incumbent_mean, (int, float)) else "unknown"
        )
        candidate_fragment = (
            f"{candidate_val:.6f}" if isinstance(candidate_val, (int, float)) else "unknown"
        )
        directive = (
            "PROTOCOL PRIORITY: a candidate provisionally beat the incumbent on a single noisy "
            "evaluation and must be re-evaluated before any new edit.\n"
            f"- candidate_id: {candidate_id}\n"
            f"- candidate_commit: {candidate_commit or 'unknown'}\n"
            f"- incumbent_before: {incumbent_id}\n"
            f"- incumbent_mean_before: {incumbent_fragment}\n"
            f"- provisional_single_eval: {candidate_fragment}\n"
            "Required actions for this turn:\n"
            "1. Restore that exact candidate commit into train.py.\n"
            "2. Do not edit train.py before the run.\n"
            "3. Run exactly one repeat evaluation of the same candidate.\n"
            "4. Summarize whether the repeated mean still beats the incumbent.\n"
            "5. Only after this reevaluation should you consider new exploration."
        )
        return directive, "reevaluation"

    def _prepare_training_run_context(
        self,
        run_git_state: dict[str, object],
    ) -> dict[str, object]:
        commit = str(run_git_state.get("commit") or "")
        candidate = self._candidate_context_for_commit(commit or None)
        incumbent_candidate_id, incumbent_mean_before = self._current_incumbent_mean()
        pending = self._pending_reevaluation
        is_pending_candidate = bool(
            pending and candidate["candidate_id"] == pending.get("candidate_id")
        )
        candidate_history = self._candidate_eval_history.get(
            str(candidate["candidate_id"]), []
        )
        evaluation_kind = "reevaluation" if is_pending_candidate else "primary"
        return {
            **candidate,
            "experiment_id": self._current_turn_context.get("experiment_id"),
            "agent_id": self._current_turn_context.get("agent_id"),
            "protocol_mode": self._current_turn_context.get("protocol_mode"),
            "evaluation_kind": evaluation_kind,
            "evaluation_round": len(candidate_history) + 1,
            "is_reevaluation": evaluation_kind == "reevaluation",
            "baseline_candidate": incumbent_candidate_id is None,
            "incumbent_candidate_id_before": incumbent_candidate_id,
            "incumbent_mean_before": incumbent_mean_before,
        }

    def _record_completed_training_run(
        self,
        run_index: int,
        run_git_state: dict[str, object],
        run_context: Optional[dict[str, object]],
        run_wall_start: Optional[float],
        finished_at: float,
        wall_seconds: Optional[float],
        training_seconds: Optional[float],
        train_total_seconds: Optional[float],
        total_steps: Optional[int],
        evaluator_mode: Optional[str],
        train_time_budget: Optional[int],
        train_max_steps: Optional[int],
        parsed_val_bpb: Optional[float],
    ) -> dict[str, object]:
        context = dict(run_context or self._prepare_training_run_context(run_git_state))
        candidate_id = str(context.get("candidate_id") or f"{self.config.agent_id}:unknown")
        candidate_history = self._candidate_eval_history.setdefault(candidate_id, [])
        incumbent_candidate_id = context.get("incumbent_candidate_id_before")
        incumbent_mean_before = context.get("incumbent_mean_before")
        evaluation_kind = str(context.get("evaluation_kind") or "primary")

        promotion_decision = "no_decision"
        if parsed_val_bpb is None:
            promotion_decision = (
                "reevaluation_failed"
                if evaluation_kind == "reevaluation"
                else "evaluation_failed"
            )
            if (
                evaluation_kind == "reevaluation"
                and self._pending_reevaluation
                and self._pending_reevaluation.get("candidate_id") == candidate_id
            ):
                self._append_jsonl(
                    self.reevaluation_log_path,
                    {
                        "timestamp": time.time(),
                        "event": "reevaluation_failed",
                        "candidate_id": candidate_id,
                        "candidate_commit": context.get("candidate_commit"),
                        "incumbent_candidate_id_before": incumbent_candidate_id,
                    },
                )
                self._pending_reevaluation = None
        else:
            candidate_history.append(parsed_val_bpb)
            candidate_mean_after = self._mean(candidate_history)
            required_total_evaluations = max(self.MIN_EVALS_FOR_PROMOTION, 1)
            better_than_incumbent = (
                incumbent_candidate_id is None
                or candidate_id == incumbent_candidate_id
                or (
                    isinstance(incumbent_mean_before, (int, float))
                    and parsed_val_bpb < float(incumbent_mean_before)
                )
            )

            if evaluation_kind == "reevaluation":
                promote = (
                    incumbent_candidate_id is None
                    or candidate_id == incumbent_candidate_id
                    or (
                        isinstance(incumbent_mean_before, (int, float))
                        and isinstance(candidate_mean_after, (int, float))
                        and candidate_mean_after < float(incumbent_mean_before)
                    )
                )
                if promote:
                    self._incumbent_candidate_id = candidate_id
                    promotion_decision = (
                        "promoted_after_reevaluation"
                        if incumbent_candidate_id not in (None, candidate_id)
                        else "confirmed_after_reevaluation"
                    )
                else:
                    promotion_decision = "rejected_after_reevaluation"
                self._append_jsonl(
                    self.reevaluation_log_path,
                    {
                        "timestamp": time.time(),
                        "event": "resolved",
                        "candidate_id": candidate_id,
                        "candidate_commit": context.get("candidate_commit"),
                        "decision": promotion_decision,
                        "evaluation_count": len(candidate_history),
                        "candidate_mean_val_bpb": candidate_mean_after,
                        "incumbent_candidate_id_before": incumbent_candidate_id,
                        "incumbent_mean_before": incumbent_mean_before,
                    },
                )
                self._pending_reevaluation = None
            elif incumbent_candidate_id is None:
                self._incumbent_candidate_id = candidate_id
                promotion_decision = "bootstrap_incumbent"
            elif candidate_id == incumbent_candidate_id:
                promotion_decision = "incumbent_repeat"
            elif better_than_incumbent:
                self._pending_reevaluation = {
                    "candidate_id": candidate_id,
                    "candidate_commit": context.get("candidate_commit"),
                    "initial_val_bpb": parsed_val_bpb,
                    "incumbent_candidate_id_before": incumbent_candidate_id,
                    "incumbent_mean_before": incumbent_mean_before,
                    "required_total_evaluations": required_total_evaluations,
                    "queued_at_turn": self.turn_count,
                }
                promotion_decision = "provisional_pending_reevaluation"
                self._append_jsonl(
                    self.reevaluation_log_path,
                    {
                        "timestamp": time.time(),
                        "event": "queued",
                        "candidate_id": candidate_id,
                        "candidate_commit": context.get("candidate_commit"),
                        "initial_val_bpb": parsed_val_bpb,
                        "incumbent_candidate_id_before": incumbent_candidate_id,
                        "incumbent_mean_before": incumbent_mean_before,
                        "required_total_evaluations": required_total_evaluations,
                    },
                )
            else:
                promotion_decision = "not_better_than_incumbent"

        training_run_record = {
            "run_index": run_index,
            "turn": self.turn_count,
            "experiment_id": context.get("experiment_id"),
            "agent_id": context.get("agent_id"),
            "started_at": run_wall_start,
            "finished_at": finished_at,
            "wall_seconds": wall_seconds,
            "evaluator_wall_seconds": wall_seconds,
            "training_seconds": training_seconds,
            "train_total_seconds": train_total_seconds,
            "total_steps": total_steps,
            "evaluator_mode": evaluator_mode or (
                "fixed_steps" if self.config.train_max_steps is not None else "fixed_time"
            ),
            "train_time_budget": train_time_budget or self.config.train_time_budget_seconds,
            "train_max_steps": train_max_steps or self.config.train_max_steps,
            "val_bpb": parsed_val_bpb,
            "status": "success" if parsed_val_bpb is not None else "crash",
            "commit": run_git_state.get("commit"),
            "commit_short": run_git_state.get("commit_short"),
            "train_py_dirty": run_git_state.get("train_py_dirty"),
            "candidate_id": candidate_id,
            "candidate_commit": context.get("candidate_commit"),
            "snapshot_step_index": context.get("snapshot_step_index"),
            "hypothesis": context.get("hypothesis"),
            "expected_effect": context.get("expected_effect"),
            "git_message": context.get("git_message"),
            "strategy_category": context.get("strategy_category"),
            "evaluation_kind": evaluation_kind,
            "evaluation_round": context.get("evaluation_round"),
            "is_reevaluation": context.get("is_reevaluation"),
            "baseline_candidate": context.get("baseline_candidate"),
            "protocol_mode": context.get("protocol_mode"),
            "memory_context_visible": context.get("memory_context_visible"),
            "memory_context_entries": context.get("memory_context_entries"),
            "shared_memory_context_visible": context.get("shared_memory_context_visible"),
            "shared_memory_context_entries": context.get("shared_memory_context_entries"),
            "incumbent_candidate_id_before": incumbent_candidate_id,
            "incumbent_mean_before": incumbent_mean_before,
            "candidate_eval_count_after": len(candidate_history),
            "candidate_mean_val_bpb_after": self._mean(candidate_history),
            "promotion_decision": promotion_decision,
            "pending_reevaluation_candidate_id_after": (
                self._pending_reevaluation.get("candidate_id")
                if isinstance(self._pending_reevaluation, dict)
                else None
            ),
        }
        self._append_jsonl(self.training_runs_log_path, training_run_record)
        return training_run_record

    def _write_metadata(
        self,
        run_id: str,
        experiment_id: str,
        start_time: str,
        end_time: str,
        total_turns: int,
        budget_seconds: int,
        observed_val_bpbs: list | None = None,
    ) -> None:
        turn_records = getattr(self, "_turn_records", [])
        turn_wall_seconds = [
            float(record.get("wall_clock_seconds"))
            for record in turn_records
            if record.get("wall_clock_seconds") is not None
        ]
        turn_total_tokens = [
            float(record.get("total_tokens"))
            for record in turn_records
            if record.get("total_tokens") is not None
        ]
        deliberation_wall_seconds = [
            float(record.get("agent_deliberation_wall_seconds"))
            for record in turn_records
            if record.get("agent_deliberation_wall_seconds") is not None
        ]
        evaluator_wall_seconds = [
            float(record.get("evaluator_wall_seconds"))
            for record in turn_records
            if record.get("evaluator_wall_seconds") is not None
        ]
        metadata = {
            "agent_id": self.config.agent_id,
            "run_id": run_id,
            "experiment_id": experiment_id,
            "start_time": start_time,
            "end_time": end_time,
            "total_turns": max(total_turns, len(turn_records)),
            "budget_seconds": budget_seconds,
            "model": self.config.model,
            "total_input_tokens": sum(
                record.get("input_tokens") or 0 for record in turn_records
            ),
            "total_output_tokens": sum(
                record.get("output_tokens") or 0 for record in turn_records
            ),
            "turn_wall_clock_seconds_mean": self._mean(turn_wall_seconds),
            "turn_wall_clock_seconds_std": self._stddev(turn_wall_seconds),
            "agent_deliberation_wall_seconds_total": sum(deliberation_wall_seconds),
            "agent_deliberation_wall_seconds_mean": self._mean(deliberation_wall_seconds),
            "agent_deliberation_wall_seconds_std": self._stddev(deliberation_wall_seconds),
            "evaluator_wall_seconds_total": sum(evaluator_wall_seconds),
            "evaluator_wall_seconds_mean": self._mean(evaluator_wall_seconds),
            "evaluator_wall_seconds_std": self._stddev(evaluator_wall_seconds),
            "turn_total_tokens_mean": self._mean(turn_total_tokens),
            "turn_total_tokens_std": self._stddev(turn_total_tokens),
            "avg_context_fill": (
                sum(record.get("context_fill_ratio", 0.0) for record in turn_records)
                / len(turn_records)
                if turn_records
                else 0.0
            ),
            "final_context_fill": (
                turn_records[-1].get("context_fill_ratio", 0.0)
                if turn_records
                else 0.0
            ),
            "evaluator_mode": (
                "fixed_steps" if self.config.train_max_steps is not None else "fixed_time"
            ),
            "train_max_steps": self.config.train_max_steps,
            "train_time_budget_seconds": self.config.train_time_budget_seconds,
        }
        meta_path = self.results_dir / "metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2))

        # Build trajectory.jsonl — primary source: observed val_bpb values captured
        # by the workspace watcher. Fallback: workspace/results/results.tsv.
        traj_path = self.results_dir / "trajectory.jsonl"
        traj_bpbs: list[float] = list(observed_val_bpbs) if observed_val_bpbs else []
        if not traj_bpbs:
            results_tsv = self.workspace / "results" / "results.tsv"
            if results_tsv.exists():
                for row in results_tsv.read_text().splitlines():
                    if not row.strip() or row.startswith("commit"):
                        continue
                    parts = row.split("\t")
                    if len(parts) >= 2:
                        try:
                            traj_bpbs.append(float(parts[1]))
                        except ValueError:
                            pass
        if traj_bpbs:
            traj_lines = [json.dumps({"step": i, "val_bpb": v}) for i, v in enumerate(traj_bpbs)]
            traj_path.write_text("\n".join(traj_lines) + "\n")

        if traj_path.exists():
            lines = [l for l in traj_path.read_text().splitlines() if l.strip()]
            metadata["total_training_runs"] = len(lines)
            if lines:
                bpbs = [json.loads(l).get("val_bpb") for l in lines if l.strip()]
                bpbs = [b for b in bpbs if b is not None]
                if bpbs:
                    metadata["best_val_bpb"] = min(bpbs)
        training_runs: list[dict] = []
        if self.training_runs_log_path.exists():
            for raw_line in self.training_runs_log_path.read_text().splitlines():
                if not raw_line.strip():
                    continue
                try:
                    training_runs.append(json.loads(raw_line))
                except json.JSONDecodeError:
                    continue
        if training_runs:
            wall_values = [
                float(row["wall_seconds"])
                for row in training_runs
                if row.get("wall_seconds") is not None
            ]
            training_values = [
                float(row["training_seconds"])
                for row in training_runs
                if row.get("training_seconds") is not None
            ]
            step_values = [
                int(row["total_steps"])
                for row in training_runs
                if row.get("total_steps") is not None
            ]
            metadata["training_run_wall_seconds_mean"] = self._mean(wall_values)
            metadata["training_run_wall_seconds_std"] = self._stddev(wall_values)
            metadata["training_run_seconds_mean"] = self._mean(training_values)
            metadata["training_run_seconds_std"] = self._stddev(training_values)
            metadata["training_run_total_steps_mean"] = self._mean(step_values)
            metadata["training_run_total_steps_std"] = self._stddev(step_values)
            metadata["reevaluation_run_count"] = sum(
                1 for row in training_runs if row.get("is_reevaluation")
            )
            metadata["promoted_after_reevaluation_count"] = sum(
                1
                for row in training_runs
                if row.get("promotion_decision") == "promoted_after_reevaluation"
            )
            metadata["candidate_count"] = len(
                {
                    row.get("candidate_id")
                    for row in training_runs
                    if row.get("candidate_id")
                }
            )
        meta_path.write_text(json.dumps(metadata, indent=2))


def _enforce_min_interval(elapsed: float, min_interval: float) -> None:
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)


def _coerce_token_count(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _log_train_diff(train_py: Path, log_fh, agent_id: str, max_lines: int = 40) -> None:
    """Log a unified diff of train.py vs train.py.baseline."""
    import difflib
    baseline = train_py.parent / "train.py.baseline"
    if not baseline.exists():
        return
    try:
        old = baseline.read_text().splitlines()
        new = train_py.read_text().splitlines()
        diff = list(difflib.unified_diff(old, new, fromfile="train.py.baseline", tofile="train.py", lineterm="", n=2))
        if not diff:
            return
        log_fh.write(f"[{agent_id}] --- train.py diff vs baseline ({len(diff)} lines) ---\n")
        for line in diff[:max_lines]:
            log_fh.write(f"[{agent_id}]   {line}\n")
        if len(diff) > max_lines:
            log_fh.write(f"[{agent_id}]   ... ({len(diff) - max_lines} more lines truncated)\n")
        log_fh.write(f"[{agent_id}] --- end diff ---\n")
    except OSError:
        pass


def _dump_slurm_failure_logs(
    workspace: Path,
    agent_id: str,
    run_count: int,
    log_fh,
    tail_lines: int = 50,
) -> None:
    """Append SLURM training logs to the agent log on training failure.

    Dumps (up to tail_lines each):
    - workspace/logs/train_current.out  — stdout of the failing train.py run
    - workspace/logs/worker_*.err       — stderr of the SLURM worker job
    """
    logs_dir = workspace / "logs"

    train_out = logs_dir / "train_current.out"
    if train_out.exists():
        try:
            lines = train_out.read_text().splitlines()
            tail = lines[-tail_lines:]
            log_fh.write(f"[{agent_id}] --- train_current.out (last {len(tail)} lines) ---\n")
            for line in tail:
                log_fh.write(f"[{agent_id}]   {line}\n")
            log_fh.write(f"[{agent_id}] --- end train_current.out ---\n")
        except OSError:
            pass

    try:
        err_files = sorted(logs_dir.glob("worker_*.err"))
        if err_files:
            latest_err = err_files[-1]
            lines = latest_err.read_text().splitlines()
            if lines:
                tail = lines[-tail_lines:]
                log_fh.write(f"[{agent_id}] --- {latest_err.name} (last {len(tail)} lines) ---\n")
                for line in tail:
                    log_fh.write(f"[{agent_id}]   {line}\n")
                log_fh.write(f"[{agent_id}] --- end {latest_err.name} ---\n")
    except OSError:
        pass

    log_fh.flush()
