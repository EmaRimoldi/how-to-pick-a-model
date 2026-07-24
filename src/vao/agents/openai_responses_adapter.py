"""OpenAI Responses API adapter for GPT/Codex model backends."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from vao.agents.anthropic_adapter import ClaudeHaikuAdapter
from vao.agents.openai_compatible_adapter import _normalize_openai_usage


class OpenAIResponsesAdapter(ClaudeHaikuAdapter):
    """Strict single-prompt adapter for OpenAI hosted GPT/Codex models.

    The parent class owns the C(a) batch protocol, parsing, materialization, and
    logging. This subclass only implements `_complete` through `/v1/responses`.
    """

    strict_failures = True

    def __init__(
        self,
        model_id: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        temperature: float = 0.2,
        include_temperature: bool = False,
        timeout_seconds: int = 600,
        max_tokens_distribution: int = 2048,
        max_tokens_edit: int = 4096,
        max_tokens_batch: int = 12000,
        retries: int = 1,
        edit_protocol: str = "structured_edits",
        use_json_schema: bool = True,
        reasoning_effort: str | None = None,
        extra_body: dict[str, Any] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(
            model_id=model_id,
            transport="openai_responses",
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
        self.base_url = os.environ.get("OPENAI_BASE_URL", base_url).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.include_temperature = bool(include_temperature)
        self.use_json_schema = bool(use_json_schema)
        self.reasoning_effort = reasoning_effort
        self.extra_body = extra_body or {}

    def _complete(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        body = self._request_body(prompt, schema, max_tokens)
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "authorization": f"Bearer {self.api_key}",
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
            raise RuntimeError(f"openai_responses_http_error:{exc.code}:{detail[-2000:]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"openai_responses_url_error:{exc.reason}") from exc
        elapsed = time.perf_counter() - started
        text = _extract_responses_text(payload)
        if not text.strip():
            raise RuntimeError("openai_responses_empty_output_text")
        return text, {
            "transport": "openai_responses",
            "usage": _normalize_openai_usage(payload.get("usage")),
            "cost_usd": None,
            "elapsed_wall_seconds": elapsed,
            "model": payload.get("model", self.model_id),
            "endpoint": self.base_url,
            "json_schema": self.use_json_schema,
            "reasoning_effort": self.reasoning_effort,
        }

    def _request_body(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> dict[str, Any]:
        user_text = prompt + "\n\nRequired JSON schema:\n" + json.dumps(schema, sort_keys=True)
        body: dict[str, Any] = {
            "model": self.model_id,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Return only valid JSON matching the user's schema. Do not include markdown or commentary.",
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_text}],
                },
            ],
            "max_output_tokens": int(max_tokens),
        }
        if self.include_temperature:
            body["temperature"] = self.temperature
        if self.use_json_schema:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "vao_step_batch",
                    "schema": schema,
                    "strict": True,
                }
            }
        if self.reasoning_effort:
            body["reasoning"] = {"effort": self.reasoning_effort}
        if self.extra_body:
            body.update(self.extra_body)
        return body


def _extract_responses_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text

    parts: list[str] = []
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if isinstance(text, str):
                    parts.append(text)
    if parts:
        return "".join(parts)

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if isinstance(text, str):
            return text
    return ""
