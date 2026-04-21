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
from vao.agents.claude_parser import ModelOutputError, parse_edit_payload, parse_mode_distribution, parse_replacement_payload
from vao.logging_utils import sha256_file, sha256_text
from vao.prompts import render_template
from vao.schemas import CandidateProposal, ModeDistribution
from vao.taxonomy import MODES, validate_mode


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
        edit_protocol: str = "patch_unified_diff",
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
        if self.edit_protocol not in {"patch_unified_diff", "replacement_file"}:
            raise ValueError(f"unsupported edit_protocol: {self.edit_protocol}")
        self.config = kwargs
        self._last_distribution_usage: dict[str, Any] = {}

    def propose_mode_distribution(self, state: AgentState) -> ModeDistribution:
        prompt = render_template(
            "mode_distribution.txt",
            profile_summary=json.dumps(state.profile_summary, sort_keys=True),
            visible_history=json.dumps(state.visible_history, sort_keys=True),
            current_solution_source=state.current_solution_source,
        )
        raw, meta = self._complete(prompt, self._distribution_schema(), self.max_tokens_distribution)
        failures: list[str] = []
        try:
            distribution = parse_mode_distribution(raw)
        except ModelOutputError as exc:
            failures.append(f"parse_failed:{exc}")
            repair_prompt = render_template("repair_json.txt", failure_details=str(exc), raw_response=raw)
            raw, meta = self._complete(repair_prompt, self._distribution_schema(), self.max_tokens_distribution)
            distribution = parse_mode_distribution(raw)
            distribution.retries += 1
        distribution.parsed_json = {
            **(distribution.parsed_json or {}),
            "transport": meta.get("transport"),
            "usage": meta.get("usage"),
            "cost_usd": meta.get("cost_usd"),
            "model": meta.get("model", self.model_id),
        }
        distribution.raw_text = raw
        distribution.validation_failures.extend(failures)
        self._last_distribution_usage = meta
        return distribution

    def propose_edit_for_mode(self, state: AgentState, mode: str, branch_dir: Path) -> CandidateProposal:
        validate_mode(mode)
        parent_path = branch_dir / "parent_solution.py"
        proposed_path = branch_dir / "proposed_solution.py"
        model_edit_path = branch_dir / "model_edit.diff"
        parent_source = parent_path.read_text(encoding="utf-8")
        prompt = render_template(
            self._edit_prompt_template(),
            mode=mode,
            profile_summary=json.dumps(state.profile_summary, sort_keys=True),
            visible_history=json.dumps(state.visible_history, sort_keys=True),
            current_solution_source=parent_source,
        )
        raw = ""
        meta: dict[str, Any] = {}
        errors: list[str] = []
        validation_failures: list[str] = []
        parsed: dict[str, Any] | None = None
        try:
            raw, meta = self._complete(prompt, self._edit_schema(mode), self.max_tokens_edit)
            parsed = self._parse_edit_response(raw, mode, parent_source)
        except (BackendUnavailable, ModelOutputError, RuntimeError) as exc:
            errors.append(f"initial_edit_failed:{type(exc).__name__}:{exc}")
            if raw:
                try:
                    repair_prompt = render_template(
                        self._repair_prompt_template(),
                        mode=mode,
                        failure_details=str(exc),
                        candidate_edit=_candidate_edit_from_raw(raw),
                        candidate_source=_candidate_edit_from_raw(raw),
                        current_solution_source=parent_source,
                    )
                    raw, meta = self._complete(repair_prompt, self._edit_schema(mode), self.max_tokens_edit)
                    parsed = self._parse_edit_response(raw, mode, parent_source)
                    validation_failures.append("repair_used")
                except (BackendUnavailable, ModelOutputError, RuntimeError) as repair_exc:
                    errors.append(f"repair_failed:{type(repair_exc).__name__}:{repair_exc}")

        if parsed is None:
            proposed_path.write_text(parent_source, encoding="utf-8")
            model_edit_path.write_text("", encoding="utf-8")
            validation_failures.append("candidate_rejected_after_repair")
            parsed = {
                "primary_mode": mode,
                "declared_mode": mode,
                "secondary_modes": [],
                "rationale": "Rejected malformed or unavailable Claude candidate; parent copied unchanged.",
                "edit_format": "rejected_noop",
                "unified_diff": "",
                "patch_parse_status": "failed",
                "patch_apply_status": "not_applied",
                "source_validation": {"passed": True, "errors": []},
                "source_validation_status": "not_applicable_noop",
            }
        else:
            proposed_path.write_text(str(parsed["solution_py"]), encoding="utf-8")
            if self.edit_protocol == "patch_unified_diff":
                model_edit_path.write_text(str(parsed.get("unified_diff", "")), encoding="utf-8")

        changed = sha256_file(parent_path) != sha256_file(proposed_path)
        prompt_hash = sha256_text(prompt)
        return CandidateProposal(
            branch_index=MODES.index(mode),
            primary_mode=mode,
            secondary_modes=[str(item) for item in parsed.get("secondary_modes", []) if item in set(MODES)],
            declared_mode=mode,
            source_hash=sha256_file(proposed_path),
            source_parent_hash=sha256_file(parent_path),
            file_path=str(proposed_path),
            raw_output_text=raw,
            parsed_output_json={
                key: value
                for key, value in parsed.items()
                if key != "solution_py"
            }
            | {
                "model_edit_path": str(model_edit_path) if model_edit_path.exists() else None,
                "transport": meta.get("transport"),
                "usage": meta.get("usage"),
                "cost_usd": meta.get("cost_usd"),
                "model": meta.get("model", self.model_id),
                "edit_protocol": self.edit_protocol,
            },
            prompt_hash=prompt_hash,
            changed=changed,
            errors=errors,
            validation_failures=validation_failures,
            usage=meta.get("usage"),
            cost_usd=meta.get("cost_usd"),
            model=meta.get("model", self.model_id),
            transport=meta.get("transport"),
        )

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

    def _distribution_schema(self) -> dict[str, Any]:
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
            },
            "required": ["mode_probs", "mode_ranking", "mode_rationales"],
        }

    def _edit_schema(self, mode: str) -> dict[str, Any]:
        if self.edit_protocol == "replacement_file":
            return self._replacement_schema(mode)
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "primary_mode": {"type": "string", "enum": [mode]},
                "declared_mode": {"type": "string", "enum": [mode]},
                "edit_format": {"type": "string", "enum": ["unified_diff"]},
                "secondary_modes": {
                    "type": "array",
                    "items": {"type": "string", "enum": MODES},
                },
                "rationale": {"type": "string"},
                "target_regions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "unified_diff": {"type": "string"},
            },
            "required": ["primary_mode", "declared_mode", "edit_format", "rationale", "unified_diff"],
        }

    def _replacement_schema(self, mode: str) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "primary_mode": {"type": "string", "enum": [mode]},
                "declared_mode": {"type": "string", "enum": [mode]},
                "edit_format": {"type": "string", "enum": ["replacement_file"]},
                "secondary_modes": {
                    "type": "array",
                    "items": {"type": "string", "enum": MODES},
                },
                "rationale": {"type": "string"},
                "target_regions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "solution_py": {"type": "string"},
            },
            "required": ["primary_mode", "declared_mode", "edit_format", "rationale", "solution_py"],
        }

    def _edit_prompt_template(self) -> str:
        return "mode_edit_replacement.txt" if self.edit_protocol == "replacement_file" else "mode_edit.txt"

    def _repair_prompt_template(self) -> str:
        return "repair_code_replacement.txt" if self.edit_protocol == "replacement_file" else "repair_code.txt"

    def _parse_edit_response(self, raw: str, mode: str, parent_source: str) -> dict[str, Any]:
        if self.edit_protocol == "replacement_file":
            return parse_replacement_payload(raw, mode)
        return parse_edit_payload(raw, mode, parent_source=parent_source)


def _candidate_edit_from_raw(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if not isinstance(payload, dict):
        return raw
    diff_text = payload.get("unified_diff")
    if isinstance(diff_text, str):
        return diff_text
    source = payload.get("solution_py")
    return source if isinstance(source, str) else raw
