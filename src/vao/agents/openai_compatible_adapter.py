"""OpenAI-compatible adapter for local/open-weight model serving.

This adapter targets vLLM/SGLang-style `/v1/chat/completions` endpoints and
shares the same strict parsing/materialization path used by the Claude adapter.
It does not fall back to deterministic local edits: endpoint or output failures
are logged as strict backend failures by the orchestrator.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from vao.agents.anthropic_adapter import ClaudeHaikuAdapter


class OpenAICompatibleAdapter(ClaudeHaikuAdapter):
    """Strict adapter for Qwen and other locally served chat models.

    The inherited protocol methods produce mode probabilities and structured
    branch-local edits. This subclass only replaces the completion transport
    with an OpenAI-compatible HTTP call.
    """

    strict_failures = True

    def __init__(
        self,
        model_id: str,
        *,
        base_url: str = "http://localhost:8000/v1",
        api_key: str | None = None,
        temperature: float = 0.3,
        timeout_seconds: int = 180,
        max_tokens_distribution: int = 2048,
        max_tokens_edit: int = 4096,
        max_tokens_batch: int = 12000,
        retries: int = 1,
        edit_protocol: str = "structured_edits",
        use_response_format: bool = True,
        allow_response_format_retry: bool = True,
        extra_body: dict[str, Any] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(
            model_id=model_id,
            transport="openai_compatible",
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            max_tokens_distribution=max_tokens_distribution,
            max_tokens_edit=max_tokens_edit,
            max_budget_usd=None,
            retries=retries,
            edit_protocol=edit_protocol,
            max_tokens_batch=max_tokens_batch,
            **kwargs,
        )
        self.base_url = os.environ.get("OPENAI_COMPATIBLE_BASE_URL", base_url).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_COMPATIBLE_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.use_response_format = bool(use_response_format)
        self.allow_response_format_retry = bool(allow_response_format_retry)
        self.extra_body = extra_body or {}

    def _complete(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        """Return model text plus normalized usage metadata."""
        errors: list[str] = []
        attempts = [self.use_response_format]
        if self.use_response_format and self.allow_response_format_retry:
            attempts.append(False)
        for include_response_format in attempts:
            try:
                return self._complete_openai_compatible(
                    prompt,
                    schema,
                    max_tokens,
                    include_response_format=include_response_format,
                )
            except RuntimeError as exc:
                errors.append(str(exc))
                if "response_format" not in str(exc) or not include_response_format:
                    break
        raise RuntimeError("openai_compatible_completion_failed:" + " | ".join(errors))

    def _complete_openai_compatible(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        *,
        include_response_format: bool,
    ) -> tuple[str, dict[str, Any]]:
        body: dict[str, Any] = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only valid JSON matching the user's schema. "
                        "Do not include markdown or commentary."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt + "\n\nRequired JSON schema:\n" + json.dumps(schema, sort_keys=True),
                },
            ],
            "temperature": self.temperature,
            "max_tokens": int(max_tokens),
        }
        if include_response_format:
            body["response_format"] = {"type": "json_object"}
        if self.extra_body:
            body.update(self.extra_body)

        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"openai_compatible_http_error:{exc.code}:{detail[-2000:]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"openai_compatible_url_error:{exc.reason}") from exc
        elapsed = time.perf_counter() - started

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("openai_compatible_no_choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if isinstance(text, list):
            text = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in text)
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("openai_compatible_empty_message_content")

        usage = _normalize_openai_usage(payload.get("usage"))
        return text, {
            "transport": "openai_compatible",
            "usage": usage,
            "cost_usd": None,
            "elapsed_wall_seconds": elapsed,
            "model": payload.get("model", self.model_id),
            "endpoint": self.base_url,
            "response_format_json": include_response_format,
        }


def _normalize_openai_usage(raw_usage: object) -> dict[str, Any]:
    if not isinstance(raw_usage, dict):
        return {}
    usage = dict(raw_usage)
    if "prompt_tokens" in raw_usage:
        usage["input_tokens"] = raw_usage.get("prompt_tokens", 0)
    if "completion_tokens" in raw_usage:
        usage["output_tokens"] = raw_usage.get("completion_tokens", 0)
    return usage
