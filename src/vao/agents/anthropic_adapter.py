"""Claude Haiku adapter using Anthropic Messages API or Claude CLI transport."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from vao.agents.base import AgentState
from vao.agents.claude_parser import (
    ModelOutputError,
    parse_json_object,
    parse_mode_distribution,
    parse_structured_edit_payload,
)
from vao.benchmark_registry import get_benchmark_spec
from vao.logging_utils import sha256_file, sha256_text
from vao.prompts import render_template
from vao.schemas import CandidateProposal, ModeDistribution
from vao.taxonomy import DEFAULT_MODE, MODES, validate_mode


class BackendUnavailable(RuntimeError):
    """Raised when no configured Claude transport is available."""


class ClaudeHaikuAdapter:
    """Strict Claude Haiku backend.

    The adapter does not silently substitute local-stub edits. If a candidate
    cannot be parsed or repaired, it writes the unchanged parent solution as an
    explicit rejected no-op candidate with validation failure metadata.
    """

    strict_failures = True

    def __init__(
        self,
        model_id: str = "haiku",
        *,
        transport: str = "auto",
        temperature: float = 0.2,
        timeout_seconds: int = 180,
        max_tokens_distribution: int = 2048,
        max_tokens_edit: int = 12000,
        max_budget_usd: float | None = 0.20,
        retries: int = 1,
        edit_protocol: str = "structured_edits",
        **kwargs: object,
    ) -> None:
        self.model_id = model_id
        self.transport = str(transport)
        self.temperature = float(temperature)
        self.timeout_seconds = int(timeout_seconds)
        self.max_tokens_distribution = int(max_tokens_distribution)
        self.max_tokens_edit = int(max_tokens_edit)
        self.max_budget_usd = max_budget_usd
        self.retries = int(retries)
        self.edit_protocol = str(edit_protocol)
        if self.edit_protocol != "structured_edits":
            raise ValueError("real-model C(a) adapters only support edit_protocol=structured_edits")
        self.config = kwargs
        self._last_distribution_usage: dict[str, Any] = {}

    def propose_step_batch(self, state: AgentState, branch_dirs: dict[str, Path]) -> tuple[ModeDistribution, dict[str, CandidateProposal]]:
        """Produce q(m) and one structured-edit candidate per mode in one Claude call.

        This is the low-token variant of the C(a) protocol: the parent source
        appears once in the prompt, Claude returns compact branch-local edits
        for all six modes, and the framework materializes each candidate in its
        own branch directory before verifier evaluation.
        """
        if self.edit_protocol != "structured_edits":
            raise ValueError("batched Claude candidate generation requires edit_protocol=structured_edits")

        parent_sources = {
            mode: (branch_dirs[mode] / "parent_solution.py").read_text(encoding="utf-8")
            for mode in MODES
        }
        parent_source = parent_sources[MODES[0]]
        if any(source != parent_source for source in parent_sources.values()):
            raise ValueError("batched candidate generation requires identical parent sources across branches")

        prompt_template = str(state.metadata.get("prompt_template", "autoresearch_program.txt"))
        prompt = render_template(
            prompt_template,
            profile_summary=json.dumps(state.profile_summary, sort_keys=True),
            visible_history=json.dumps(state.visible_history, sort_keys=True),
            current_solution_source=parent_source,
        )
        prompt_hash = sha256_text(prompt)
        _write_step_prompt_snapshot(branch_dirs, prompt, prompt_hash, prompt_template)
        raw = ""
        meta: dict[str, Any] = {}
        failures: list[str] = []
        payload: dict[str, Any] | None = None
        last_exc: Exception | None = None
        for attempt_index in range(max(self.retries, 1)):
            try:
                raw, meta = self._complete(prompt, self._step_batch_schema(), int(self.config.get("max_tokens_batch", 12000)))
                _write_step_batch_raw_output(branch_dirs, raw, meta)
                payload = parse_json_object(raw)
                break
            except (BackendUnavailable, ModelOutputError, RuntimeError) as exc:
                last_exc = exc
                failures.append(f"batch_parse_failed:attempt_{attempt_index + 1}:{type(exc).__name__}:{exc}")
        if payload is None:
            assert last_exc is not None
            raise last_exc

        distribution = parse_mode_distribution(json.dumps(payload, sort_keys=True))
        distribution.raw_text = raw
        distribution.validation_failures.extend(failures)
        distribution.parsed_json = {
            **(distribution.parsed_json or {}),
            "candidate_generation": "batched_structured_edits",
            "transport": meta.get("transport"),
            "usage": meta.get("usage"),
            "cost_usd": meta.get("cost_usd"),
            "model": meta.get("model", self.model_id),
            "prompt_template": prompt_template,
            "prompt_hash": prompt_hash,
            "prompt_snapshot_path": _step_prompt_snapshot_path(branch_dirs),
        }

        candidates = payload.get("candidates")
        if not isinstance(candidates, dict):
            raise ModelOutputError("batch_candidates_missing_or_not_object")

        proposals: dict[str, CandidateProposal] = {}
        benchmark_id = str(state.metadata.get("benchmark_id", "autoresearch_cifar10"))
        source_validator = get_benchmark_spec(benchmark_id).validate_source
        for mode in MODES:
            branch_dir = branch_dirs[mode]
            parent_path = branch_dir / "parent_solution.py"
            proposed_path = branch_dir / "proposed_solution.py"
            model_edit_path = branch_dir / "model_edit.json"
            mode_payload = candidates.get(mode)
            errors: list[str] = []
            validation_failures: list[str] = []
            parsed: dict[str, Any] | None = None
            mode_raw = json.dumps(mode_payload, sort_keys=True) if isinstance(mode_payload, dict) else str(mode_payload)
            try:
                if not isinstance(mode_payload, dict):
                    raise ModelOutputError(f"candidate_payload_missing_or_not_object:{mode}")
                parsed = parse_structured_edit_payload(
                    mode_raw,
                    mode,
                    parent_source=parent_source,
                    source_validator=source_validator,
                )
            except ModelOutputError as exc:
                errors.append(f"batch_candidate_invalid:{type(exc).__name__}:{exc}")
                validation_failures.append("candidate_rejected_from_batch")

            if parsed is None:
                proposed_path.write_text(parent_source, encoding="utf-8")
                model_edit_path.write_text("", encoding="utf-8")
                parsed = {
                    "primary_mode": mode,
                    "declared_mode": mode,
                    "secondary_modes": [],
                    "rationale": "Rejected malformed batched Claude candidate; parent copied unchanged.",
                    "edit_format": "rejected_noop",
                    "edits": [],
                    "patch_parse_status": "failed",
                    "patch_apply_status": "not_applied",
                    "structured_edit_parse_status": "failed",
                    "structured_edit_apply_status": "not_applied",
                    "source_validation": {"passed": True, "errors": []},
                    "source_validation_status": "not_applicable_noop",
                }
            else:
                proposed_path.write_text(str(parsed["solution_py"]), encoding="utf-8")
                model_edit_path.write_text(json.dumps(parsed.get("edits", []), indent=2, sort_keys=True), encoding="utf-8")

            changed = sha256_file(parent_path) != sha256_file(proposed_path)
            proposals[mode] = CandidateProposal(
                branch_index=MODES.index(mode),
                primary_mode=mode,
                secondary_modes=[str(item) for item in parsed.get("secondary_modes", []) if item in set(MODES)],
                declared_mode=mode,
                source_hash=sha256_file(proposed_path),
                source_parent_hash=sha256_file(parent_path),
                file_path=str(proposed_path),
                raw_output_text=mode_raw,
                parsed_output_json={
                    key: value
                    for key, value in parsed.items()
                    if key != "solution_py"
                }
                | {
                    "model_edit_path": str(model_edit_path) if model_edit_path.exists() else None,
                    "edit_protocol": self.edit_protocol,
                    "candidate_generation": "batched_structured_edits",
                    "batch_usage_accounted_on_distribution": True,
                    "prompt_template": prompt_template,
                    "prompt_snapshot_path": _step_prompt_snapshot_path(branch_dirs),
                },
                prompt_hash=prompt_hash,
                changed=changed,
                errors=errors,
                validation_failures=validation_failures,
            )
        return distribution, proposals

    def propose_step_single(self, state: AgentState, branch_dirs: dict[str, Path]) -> tuple[ModeDistribution, CandidateProposal]:
        if self.edit_protocol != "structured_edits":
            raise ValueError("single-candidate Claude generation requires edit_protocol=structured_edits")

        parent_sources = {
            mode: (branch_dirs[mode] / "parent_solution.py").read_text(encoding="utf-8")
            for mode in MODES
        }
        parent_source = parent_sources[MODES[0]]
        if any(source != parent_source for source in parent_sources.values()):
            raise ValueError("single candidate generation requires identical parent sources across branches")

        prompt_template = str(state.metadata.get("prompt_template", "autoresearch_program.txt"))
        prompt = render_template(
            prompt_template,
            profile_summary=json.dumps(state.profile_summary, sort_keys=True),
            visible_history=json.dumps(state.visible_history, sort_keys=True),
            current_solution_source=parent_source,
        )
        prompt_hash = sha256_text(prompt)
        _write_step_prompt_snapshot(branch_dirs, prompt, prompt_hash, prompt_template)

        benchmark_id = str(state.metadata.get("benchmark_id", "autoresearch_cifar10"))
        source_validator = get_benchmark_spec(benchmark_id).validate_source

        raw = ""
        meta: dict[str, Any] = {}
        failures: list[str] = []
        payload: dict[str, Any] | None = None
        parsed: dict[str, Any] | None = None
        selected_mode = ""
        last_exc: Exception | None = None
        for attempt_index in range(max(self.retries, 1)):
            try:
                raw, meta = self._complete(prompt, self._single_candidate_schema(), self.max_tokens_edit)
                _write_step_batch_raw_output(branch_dirs, raw, meta)
                payload = parse_json_object(raw)
                selected_mode = str(payload.get("primary_mode") or payload.get("declared_mode") or "")
                validate_mode(selected_mode)
                if payload.get("declared_mode") != selected_mode:
                    raise ModelOutputError(f"declared_mode_mismatch:{payload.get('declared_mode')!r}!={selected_mode!r}")
                mode_raw = json.dumps(payload, sort_keys=True)
                parsed = parse_structured_edit_payload(
                    mode_raw,
                    selected_mode,
                    parent_source=parent_source,
                    source_validator=source_validator,
                )
                break
            except (BackendUnavailable, ModelOutputError, RuntimeError) as exc:
                last_exc = exc
                failures.append(f"single_parse_failed:attempt_{attempt_index + 1}:{type(exc).__name__}:{exc}")
        if payload is None or parsed is None:
            fallback_mode = selected_mode if selected_mode in MODES else DEFAULT_MODE
            branch_dir = branch_dirs[fallback_mode]
            parent_path = branch_dir / "parent_solution.py"
            proposed_path = branch_dir / "proposed_solution.py"
            proposed_path.write_text(parent_source, encoding="utf-8")
            distribution = ModeDistribution(
                mode_probs={mode: (1.0 if mode == fallback_mode else 0.0) for mode in MODES},
                mode_ranking=[fallback_mode, *[mode for mode in MODES if mode != fallback_mode]],
                mode_rationales={mode: "" for mode in MODES},
                raw_text=raw,
                parsed_json={
                    "candidate_generation": "single_structured_edit_fallback_noop",
                    "transport": meta.get("transport"),
                    "usage": meta.get("usage"),
                    "cost_usd": meta.get("cost_usd"),
                    "model": meta.get("model", self.model_id),
                    "prompt_template": prompt_template,
                    "prompt_hash": prompt_hash,
                    "prompt_snapshot_path": _step_prompt_snapshot_path(branch_dirs),
                    "selected_mode": fallback_mode,
                },
                validation_failures=failures,
                agent_contract_failed=True,
            )
            proposal = CandidateProposal(
                branch_index=MODES.index(fallback_mode),
                primary_mode=fallback_mode,
                secondary_modes=[],
                declared_mode=fallback_mode,
                source_hash=sha256_file(proposed_path),
                source_parent_hash=sha256_file(parent_path),
                file_path=str(proposed_path),
                raw_output_text=raw,
                parsed_output_json={
                    "candidate_generation": "single_structured_edit_fallback_noop",
                    "fallback_reason": str(last_exc) if last_exc is not None else "unknown_single_candidate_failure",
                    "edit_protocol": self.edit_protocol,
                    "prompt_template": prompt_template,
                    "prompt_snapshot_path": _step_prompt_snapshot_path(branch_dirs),
                },
                prompt_hash=prompt_hash,
                changed=False,
                errors=[str(last_exc)] if last_exc is not None else ["single_candidate_generation_failed"],
                validation_failures=failures,
            )
            return distribution, proposal
        branch_dir = branch_dirs[selected_mode]
        parent_path = branch_dir / "parent_solution.py"
        proposed_path = branch_dir / "proposed_solution.py"
        model_edit_path = branch_dir / "model_edit.json"
        proposed_path.write_text(str(parsed["solution_py"]), encoding="utf-8")
        model_edit_path.write_text(json.dumps(parsed.get("edits", []), indent=2, sort_keys=True), encoding="utf-8")

        one_hot = {mode: (1.0 if mode == selected_mode else 0.0) for mode in MODES}
        distribution = ModeDistribution(
            mode_probs=one_hot,
            mode_ranking=[selected_mode, *[mode for mode in MODES if mode != selected_mode]],
            mode_rationales={mode: (str(payload.get("rationale", "")) if mode == selected_mode else "") for mode in MODES},
            raw_text=raw,
            parsed_json={
                "candidate_generation": "single_structured_edit",
                "transport": meta.get("transport"),
                "usage": meta.get("usage"),
                "cost_usd": meta.get("cost_usd"),
                "model": meta.get("model", self.model_id),
                "prompt_template": prompt_template,
                "prompt_hash": prompt_hash,
                "prompt_snapshot_path": _step_prompt_snapshot_path(branch_dirs),
                "selected_mode": selected_mode,
            },
            validation_failures=failures,
        )
        proposal = CandidateProposal(
            branch_index=MODES.index(selected_mode),
            primary_mode=selected_mode,
            secondary_modes=[str(item) for item in parsed.get("secondary_modes", []) if item in set(MODES)],
            declared_mode=selected_mode,
            source_hash=sha256_file(proposed_path),
            source_parent_hash=sha256_file(parent_path),
            file_path=str(proposed_path),
            raw_output_text=mode_raw,
            parsed_output_json={
                key: value
                for key, value in parsed.items()
                if key != "solution_py"
            }
            | {
                "model_edit_path": str(model_edit_path) if model_edit_path.exists() else None,
                "edit_protocol": self.edit_protocol,
                "candidate_generation": "single_structured_edit",
                "usage_accounted_on_distribution": True,
                "prompt_template": prompt_template,
                "prompt_snapshot_path": _step_prompt_snapshot_path(branch_dirs),
            },
            prompt_hash=prompt_hash,
            changed=sha256_file(parent_path) != sha256_file(proposed_path),
        )
        return distribution, proposal

    def propose_single_prompt_trajectory(self, state: AgentState, max_steps: int) -> dict[str, Any]:
        """Return a full edit trajectory from one model call.

        The harness still verifies each proposed edit sequentially. The model
        receives only the initial artifact and must provide a finite ordered
        list of structured edits; it does not get verifier feedback between
        proposed steps.
        """
        prompt_template = str(state.metadata.get("prompt_template", "autoresearch_program.txt"))
        base_prompt = render_template(
            prompt_template,
            profile_summary=json.dumps(state.profile_summary, sort_keys=True),
            visible_history=json.dumps(state.visible_history, sort_keys=True),
            current_solution_source=state.current_solution_source,
        )
        prompt = (
            base_prompt
            + "\n\nSingle-prompt trajectory mode:\n"
            + f"Return up to {int(max_steps)} sequential structured-edit steps in `trajectory_steps`. "
            + "Each step will be applied to the result of the previous accepted step by the external harness. "
            + "Do not assume verifier feedback after individual proposed edits. Return only JSON."
        )
        prompt_hash = sha256_text(prompt)
        raw, meta = self._complete(prompt, self._trajectory_schema(int(max_steps)), int(self.config.get("max_tokens_trajectory", self.config.get("max_tokens_batch", 12000))))
        payload = parse_json_object(raw)
        steps = payload.get("trajectory_steps")
        if not isinstance(steps, list):
            raise ModelOutputError("trajectory_steps_missing_or_not_array")
        return {
            "raw": raw,
            "meta": meta,
            "payload": payload,
            "prompt": prompt,
            "prompt_hash": prompt_hash,
            "prompt_template": prompt_template,
        }

    def propose_mode_distribution(self, state: AgentState) -> ModeDistribution:
        raise RuntimeError("single_step_program_only: use candidate_generation=batched and propose_step_batch")

    def propose_edit_for_mode(self, state: AgentState, mode: str, branch_dir: Path) -> CandidateProposal:
        raise RuntimeError("single_step_program_only: use candidate_generation=batched and propose_step_batch")

    def _complete(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        transport = self._resolve_transport()
        if transport == "api":
            return self._complete_api(prompt, schema, max_tokens)
        if transport == "cli":
            return self._complete_cli(prompt, schema)
        raise BackendUnavailable(f"unsupported_transport:{transport}")

    def _resolve_transport(self) -> str:
        if self.transport == "api":
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise BackendUnavailable("ANTHROPIC_API_KEY is not set")
            return "api"
        if self.transport == "cli":
            if shutil.which("claude") is None:
                raise BackendUnavailable("claude CLI not found")
            return "cli"
        if self.transport != "auto":
            raise BackendUnavailable(f"unknown_transport:{self.transport}")
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "api"
        if shutil.which("claude") is not None:
            return "cli"
        raise BackendUnavailable("no Anthropic API key and no claude CLI found")

    def _complete_api(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise BackendUnavailable("ANTHROPIC_API_KEY is not set")
        body = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
            "system": "Return only valid JSON matching the user's schema. Do not include markdown.",
            "messages": [
                {
                    "role": "user",
                    "content": prompt + "\n\nRequired JSON schema:\n" + json.dumps(schema, sort_keys=True),
                }
            ],
        }
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"anthropic_api_http_error:{exc.code}:{detail}") from exc
        elapsed = time.perf_counter() - started
        text = "\n".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
        usage = payload.get("usage") or {}
        return text, {
            "transport": "api",
            "usage": usage,
            "cost_usd": None,
            "elapsed_wall_seconds": elapsed,
            "model": payload.get("model", self.model_id),
        }

    def _complete_cli(self, prompt: str, schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        cmd = [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--tools",
            "",
            "--model",
            self.model_id,
            "--json-schema",
            json.dumps(schema, sort_keys=True),
        ]
        if self.max_budget_usd is not None:
            cmd += ["--max-budget-usd", str(self.max_budget_usd)]
        cmd.append(prompt)
        started = time.perf_counter()
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
        )
        elapsed = time.perf_counter() - started
        if proc.returncode != 0:
            raise RuntimeError(f"claude_cli_failed:{proc.returncode}:{proc.stderr[-2000:]}")
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"claude_cli_non_json:{proc.stdout[-2000:]}") from exc
        if payload.get("subtype") not in {None, "success"} or payload.get("is_error"):
            raise RuntimeError(f"claude_cli_error:{payload.get('subtype')}:{payload.get('errors')}")
        if "structured_output" in payload:
            raw = json.dumps(payload["structured_output"], sort_keys=True)
        else:
            raw = str(payload.get("result", ""))
        usage = payload.get("usage") or {}
        model_usage = payload.get("modelUsage") or {}
        model = next(iter(model_usage), self.model_id) if isinstance(model_usage, dict) else self.model_id
        return raw, {
            "transport": "cli",
            "usage": usage,
            "cost_usd": payload.get("total_cost_usd"),
            "elapsed_wall_seconds": elapsed,
            "model": model,
            "session_id": payload.get("session_id"),
            "raw_cli_result": {key: payload.get(key) for key in ["type", "subtype", "stop_reason", "total_cost_usd"]},
        }


    def _step_batch_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "mode_probs": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {mode: {"type": "number", "minimum": 0} for mode in MODES},
                    "required": MODES,
                },
                "mode_ranking": {
                    "type": "array",
                    "items": {"type": "string", "enum": MODES},
                    "minItems": 6,
                    "maxItems": 6,
                },
                "mode_rationales": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {mode: {"type": "string"} for mode in MODES},
                    "required": MODES,
                },
                "candidates": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        mode: {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": self._structured_candidate_properties(mode),
                            "required": [
                                "primary_mode",
                                "declared_mode",
                                "edit_format",
                                "secondary_modes",
                                "rationale",
                                "target_regions",
                                "edits",
                            ],
                        }
                        for mode in MODES
                    },
                    "required": MODES,
                },
            },
            "required": ["mode_probs", "mode_ranking", "mode_rationales", "candidates"],
        }

    def _single_candidate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "primary_mode": {"type": "string", "enum": MODES},
                "declared_mode": {"type": "string", "enum": MODES},
                "edit_format": {"type": "string", "enum": ["structured_edits"]},
                "secondary_modes": {
                    "type": "array",
                    "items": {"type": "string", "enum": MODES},
                },
                "rationale": {"type": "string"},
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": ["replace_exact", "delete_exact", "insert_before", "insert_after", "replace_function"],
                            },
                            "function": {"type": "string"},
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                            "anchor": {"type": "string"},
                            "text": {"type": "string"},
                            "source": {"type": "string"},
                        },
                        "required": ["op", "function", "old", "new", "anchor", "text", "source"],
                    },
                    "minItems": 1,
                    "maxItems": 8,
                },
            },
            "required": ["primary_mode", "declared_mode", "edit_format", "secondary_modes", "rationale", "edits"],
        }

    def _trajectory_schema(self, max_steps: int) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "trajectory_rationale": {"type": "string"},
                "trajectory_steps": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": max(1, int(max_steps)),
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "step": {"type": "integer", "minimum": 0},
                            "primary_mode": {"type": "string", "enum": MODES},
                            "declared_mode": {"type": "string", "enum": MODES},
                            "edit_format": {"type": "string", "enum": ["structured_edits"]},
                            "secondary_modes": {
                                "type": "array",
                                "items": {"type": "string", "enum": MODES},
                            },
                            "rationale": {"type": "string"},
                            "edits": self._single_candidate_schema()["properties"]["edits"],
                        },
                        "required": [
                            "step",
                            "primary_mode",
                            "declared_mode",
                            "edit_format",
                            "secondary_modes",
                            "rationale",
                            "edits",
                        ],
                    },
                },
            },
            "required": ["trajectory_rationale", "trajectory_steps"],
        }

    def _structured_candidate_properties(self, mode: str) -> dict[str, Any]:
        edit_item = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "op": {
                    "type": "string",
                    "enum": ["replace_exact", "delete_exact", "insert_before", "insert_after", "replace_function"],
                },
                "function": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
                "anchor": {"type": "string"},
                "text": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["op", "function", "old", "new", "anchor", "text", "source"],
        }
        return {
            "primary_mode": {"type": "string", "enum": [mode]},
            "declared_mode": {"type": "string", "enum": [mode]},
            "edit_format": {"type": "string", "enum": ["structured_edits"]},
            "secondary_modes": {
                "type": "array",
                "items": {"type": "string", "enum": MODES},
            },
            "rationale": {"type": "string"},
            "target_regions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "edits": {
                "type": "array",
                "items": edit_item,
                "minItems": 1,
                "maxItems": 8,
            },
        }

def _step_dir_from_branch_dirs(branch_dirs: dict[str, Path]) -> Path:
    first = branch_dirs[MODES[0]]
    return first.parent.parent if first.parent.name == "branches" else first.parent


def _step_prompt_snapshot_path(branch_dirs: dict[str, Path]) -> str:
    return str(_step_dir_from_branch_dirs(branch_dirs) / "prompt_snapshot.txt")


def _write_step_prompt_snapshot(branch_dirs: dict[str, Path], prompt: str, prompt_hash: str, template_name: str) -> None:
    step_dir = _step_dir_from_branch_dirs(branch_dirs)
    step_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = step_dir / "prompt_snapshot.txt"
    meta_path = step_dir / "prompt_snapshot.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "template": template_name,
                "prompt_hash": prompt_hash,
                "prompt_path": str(prompt_path),
                "prompt_chars": len(prompt),
                "prompt_lines": prompt.count("\n") + 1,
                "single_model_generation_prompt": True,
                "modes": MODES,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_step_batch_raw_output(branch_dirs: dict[str, Path], raw: str, meta: dict[str, Any]) -> None:
    step_dir = _step_dir_from_branch_dirs(branch_dirs)
    step_dir.mkdir(parents=True, exist_ok=True)
    (step_dir / "batch_raw_output.txt").write_text(raw, encoding="utf-8")
    (step_dir / "batch_raw_output_meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True),
        encoding="utf-8",
    )
