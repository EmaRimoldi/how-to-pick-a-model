"""Codex CLI adapter for GPT/Codex model backends."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from vao.agents.anthropic_adapter import BackendUnavailable, ClaudeHaikuAdapter


class CodexCliAdapter(ClaudeHaikuAdapter):
    """Strict single-prompt adapter using the local `codex exec` transport.

    This keeps the C(a) batch protocol implemented by `ClaudeHaikuAdapter` and
    swaps only the completion transport. It is useful when Codex account auth is
    available locally but `OPENAI_API_KEY` is not exported for Responses API.
    """

    strict_failures = True

    def __init__(
        self,
        model_id: str,
        *,
        timeout_seconds: int = 900,
        max_tokens_distribution: int = 2048,
        max_tokens_edit: int = 4096,
        max_tokens_batch: int = 12000,
        retries: int = 1,
        edit_protocol: str = "structured_edits",
        reasoning_effort: str = "medium",
        sandbox: str = "read-only",
        use_output_schema: bool = False,
        extra_cli_args: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(
            model_id=model_id,
            transport="codex_cli",
            temperature=float(kwargs.pop("temperature", 0.2)),
            timeout_seconds=timeout_seconds,
            max_tokens_distribution=max_tokens_distribution,
            max_tokens_edit=max_tokens_edit,
            max_budget_usd=None,
            retries=retries,
            edit_protocol=edit_protocol,
            max_tokens_batch=max_tokens_batch,
            **kwargs,
        )
        self.reasoning_effort = str(reasoning_effort)
        self.sandbox = str(sandbox)
        self.use_output_schema = bool(use_output_schema)
        self.extra_cli_args = list(extra_cli_args or [])

    def _complete(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        if shutil.which("codex") is None:
            raise BackendUnavailable("codex CLI not found")

        with tempfile.TemporaryDirectory(prefix="vao_codex_cli_") as tmp:
            tmp_dir = Path(tmp)
            output_path = tmp_dir / "last_message.json"
            cmd = [
                "codex",
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "-m",
                self.model_id,
                "-c",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "-s",
                self.sandbox,
                "--output-last-message",
                str(output_path),
            ]
            if self.use_output_schema:
                schema_path = tmp_dir / "schema.json"
                schema_path.write_text(json.dumps(schema, sort_keys=True), encoding="utf-8")
                cmd += ["--output-schema", str(schema_path)]
            prompt_with_schema = prompt
            if not self.use_output_schema:
                prompt_with_schema = prompt + "\n\nRequired JSON schema:\n" + json.dumps(schema, sort_keys=True)
            cmd += [*self.extra_cli_args, prompt_with_schema]
            started = time.perf_counter()
            proc = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
            )
            elapsed = time.perf_counter() - started
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout)[-2000:]
                raise RuntimeError(f"codex_cli_failed:{proc.returncode}:{detail}")
            if output_path.exists():
                raw = output_path.read_text(encoding="utf-8")
            else:
                raw = _last_jsonish_stdout_block(proc.stdout)
            if not raw.strip():
                raise RuntimeError("codex_cli_empty_output")
            return raw, {
                "transport": "codex_cli",
                "usage": _parse_codex_stdout_usage(proc.stdout),
                "cost_usd": None,
                "elapsed_wall_seconds": elapsed,
                "model": self.model_id,
                "reasoning_effort": self.reasoning_effort,
                "max_tokens_requested": int(max_tokens),
                "raw_cli_result": {
                    "stdout_tail": proc.stdout[-1000:],
                    "stderr_tail": proc.stderr[-1000:],
                },
            }


def _last_jsonish_stdout_block(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            return line
    return ""


def _parse_codex_stdout_usage(stdout: str) -> dict[str, Any]:
    lines = [line.strip() for line in stdout.splitlines()]
    for index, line in enumerate(lines):
        if line == "tokens used" and index + 1 < len(lines):
            try:
                return {"total_tokens_reported": float(lines[index + 1])}
            except ValueError:
                return {"tokens_used_raw": lines[index + 1]}
    return {}
