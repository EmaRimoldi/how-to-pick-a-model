"""Pinned OpenRouter completions with an append-only dollar reservation ledger."""

from __future__ import annotations

import json
import time
import threading
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any


API_ROOT = "https://openrouter.ai/api/v1"
_APPEND_LOCK = threading.Lock()
ZERO_ERROR_POLICY = "https://openrouter.ai/blog/announcements/never-pay-for-empty-ai-responses-again/"


def insured_empty_error(record: dict) -> bool:
    """Normalize only explicit empty provider errors covered by published zero-charge insurance.

    This is a policy-backed zero, not a reported token receipt. Raw usage and
    billing provenance remain visible; ordinary missing billing still stops.
    """
    if ((record.get("usage") or {}).get("cost") is None and record.get("finish_reason") == "error"
            and not record.get("content") and record.get("generation_id") and record.get("provider")):
        record["reported_usage"] = record.get("usage") or {}
        record["usage"] = {"cost": 0, "prompt_tokens": None, "completion_tokens": None}
        record["billing_source"] = "published_zero_completion_insurance"
        record["billing_policy_url"] = ZERO_ERROR_POLICY
        return True
    return False


def read_stream(response) -> dict:
    """Assemble OpenRouter SSE chunks, keeping the final authoritative usage."""
    payload: dict[str, Any] = {}
    content = []
    finish = None
    for raw in response:
        line = raw.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue  # Includes keepalive comments.
        data = line[5:].strip()
        if data == "[DONE]":
            break
        event = json.loads(data)
        for field in ("id", "provider", "model", "usage"):
            if event.get(field) is not None:
                payload[field] = event[field]
        if event.get("error"):
            if payload.get("id") and payload.get("provider"):
                finish = "error"
                break  # Preserve explicit failure identity; never retry inference.
            raise BackendStopped("OpenRouter streaming error; billing unresolved")
        for choice in event.get("choices", []):
            if choice.get("index", 0) != 0:
                raise BackendStopped("Unexpected multiple completion choices")
            delta = choice.get("delta") or {}
            if delta.get("content"):
                content.append(delta["content"])
            if choice.get("finish_reason") is not None:
                finish = choice["finish_reason"]
    payload["choices"] = [{"message": {"content": "".join(content)}, "finish_reason": finish}]
    return payload


class BudgetStopped(RuntimeError):
    """The remaining budget or billing uncertainty forbids another request."""


class BackendStopped(RuntimeError):
    """A strict backend failure; no implicit retry or provider substitution."""


def append_json(path: Path, record: dict) -> None:
    """Append and flush one public experiment record, never request headers."""
    with _APPEND_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()


class BudgetLedger:
    """Reserve a worst-case token charge before each serial request.

    Pending reservations survive process failure in the journal. An existing
    journal cannot be reused: automatic resume could duplicate paid requests.
    """

    def __init__(self, path: Path, limit_usd: float, *, maximum_limit_usd: float = 2) -> None:
        self.limit = Decimal(str(limit_usd))
        maximum = Decimal(str(maximum_limit_usd))
        if not maximum.is_finite() or not 0 < maximum <= 5:
            raise ValueError("Explicit campaign maximum must be in (0, 5] USD")
        if not self.limit.is_finite() or not 0 < self.limit <= maximum:
            raise ValueError("Run budget exceeds the explicit campaign maximum")
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=False)
        self.spent = Decimal(0)
        self.pending: dict[int, Decimal] = {}
        self.stopped = False
        self.calls = 0
        self._lock = threading.RLock()

    def reserve(self, dollars: Decimal, model: str) -> int:
        """Persist admission before network activity; account for unresolved calls."""
        with self._lock:
            return self._reserve(dollars, model)

    def _reserve(self, dollars: Decimal, model: str) -> int:
        if not dollars.is_finite() or dollars <= 0:
            raise ValueError("Reservation must be finite and positive")
        committed = self.spent + sum(self.pending.values())
        if self.stopped or committed + dollars > self.limit:
            raise BudgetStopped("Insufficient uncommitted budget")
        self.calls += 1
        self.pending[self.calls] = dollars
        append_json(self.path, {"event": "reserve", "call": self.calls,
                               "model": model, "reserved_usd": float(dollars)})
        return self.calls

    def settle(self, call: int, cost: object) -> None:
        """Use measured account charge; stop on missing/invalid/over-ceiling usage."""
        with self._lock:
            self._settle(call, cost)

    def _settle(self, call: int, cost: object) -> None:
        try:
            amount = Decimal(str(cost))
        except Exception:
            amount = Decimal("NaN")
        if not amount.is_finite() or amount < 0:
            self.stopped = True
            raise BudgetStopped("Missing trustworthy billing; reservation retained")
        reserved = self.pending.pop(call)
        self.spent += amount
        append_json(self.path, {"event": "settle", "call": call,
                               "cost_usd": float(amount)})
        if amount > reserved or self.spent > self.limit:
            self.stopped = True
            raise BudgetStopped("Provider charge exceeded the reserved ceiling")


class NoRedirects(urllib.request.HTTPRedirectHandler):
    """Keep bearer credentials on the declared API origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenRouterClient:
    """Single-request transport with provider, precision, and price constraints."""

    def __init__(self, key: str, config: dict, output: Path, ledger: BudgetLedger):
        self._key = key
        self.config = config
        self.output = output
        self.ledger = ledger

    def request(self, endpoint: str, body: dict | None = None) -> dict:
        """Send only to OpenRouter; omit response bodies from transport exceptions."""
        request = urllib.request.Request(
            API_ROOT + endpoint,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + self._key,
                     "Content-Type": "application/json"},
            method="GET" if body is None else "POST",
        )
        try:
            with urllib.request.build_opener(NoRedirects).open(request, timeout=180) as response:
                return read_stream(response) if body and body.get("stream") else json.loads(response.read())
        except urllib.error.HTTPError as exc:
            failure = BackendStopped(f"OpenRouter HTTP {exc.code}; no automatic retry")
            failure.http_status = exc.code
            failure.retry_after = (exc.headers or {}).get("Retry-After")
            try:
                metadata = (json.loads(exc.read()).get("error") or {}).get("metadata") or {}
                failure.http_metadata = {k: metadata[k] for k in ("error_type", "provider_code", "limit_source")
                    if isinstance(metadata.get(k), str) and len(metadata[k]) < 100 and "sk-" not in metadata[k]}
            except (ValueError, TypeError, AttributeError):
                failure.http_metadata = {}
            raise failure from None
        except (OSError, ValueError) as exc:
            raise BackendStopped(f"OpenRouter {type(exc).__name__}; no automatic retry") from None

    def preflight(self) -> dict:
        """Check real shared-account credit and the requested endpoint's current price."""
        key = self.request("/key")["data"]
        credits = self.request("/credits")["data"]
        balance = Decimal(str(credits["total_credits"])) - Decimal(str(credits["total_usage"]))
        remaining = key.get("limit_remaining")
        if remaining is not None:
            balance = min(balance, Decimal(str(remaining)))
        effective = key.get("effective_budget") or {}
        if effective.get("remaining_usd") is not None:
            balance = min(balance, Decimal(str(effective["remaining_usd"])))
        if balance < self.ledger.limit:
            raise BudgetStopped("Account/key funds below the declared run budget")
        snapshots = {}
        for name, model in self.config["models"].items():
            endpoints = self.request("/models/" + model["id"] + "/endpoints")["data"]["endpoints"]
            provider = model.get("provider", self.config["provider"])
            precision = model.get("quantization", "fp8")
            found = [e for e in endpoints if e.get("tag") == provider]
            if len(found) != 1 or found[0].get("quantization") != precision:
                raise BackendStopped("The declared provider/precision endpoint is unavailable")
            endpoint = found[0]
            for field, ceiling in (("prompt", model["input_per_million"]),
                                   ("completion", model["output_per_million"])):
                if Decimal(endpoint["pricing"][field]) * 1_000_000 > Decimal(str(ceiling)):
                    raise BackendStopped("Endpoint price increased; revise the protocol before running")
            required = {"max_tokens", "response_format", "temperature"}
            if model.get("reasoning_parameter", True):
                required.add("reasoning")
            if self.config.get("request_seed", False):
                required.add("seed")
            if not required <= set(endpoint.get("supported_parameters", [])):
                raise BackendStopped("Endpoint does not support all protocol parameters")
            snapshots[name] = endpoint
        # Personal account identifiers, key labels, and keys are not persisted.
        return {"available_usd_before": float(balance), "endpoints": snapshots}

    def complete(self, model_name: str, messages: list[dict], seed: int, metadata: dict) -> dict:
        """Record all billed responses, including invalid or truncated solutions."""
        model = self.config["models"][model_name]
        provider = model.get("provider", self.config["provider"])
        precision = model.get("quantization", "fp8")
        input_cap = int(self.config["input_token_ceiling"])
        max_tokens = int(self.config["max_tokens"])
        # UTF-8 byte bound plus generous framing allowance; no images or tools.
        if sum(len(m["content"].encode("utf-8")) for m in messages) + 4096 > input_cap:
            raise BudgetStopped("Prompt exceeds the conservative input-token ceiling")
        reserve = (Decimal(input_cap) * Decimal(str(model["input_per_million"]))
                   + Decimal(max_tokens) * Decimal(str(model["output_per_million"]))) / 1_000_000
        call = self.ledger.reserve(reserve, model["id"])
        body = {
            "model": model["id"], "messages": messages, "max_tokens": max_tokens,
            "stream": self.config.get("stream", False),
            "temperature": self.config["temperature"],
            "response_format": {"type": "json_object"},
            "provider": {"only": [provider], "allow_fallbacks": False,
                         "require_parameters": True, "quantizations": [precision],
                         "max_price": {"prompt": model["input_per_million"],
                                       "completion": model["output_per_million"]}},
        }
        if model.get("reasoning_parameter", True):
            body["reasoning"] = {"enabled": False}
        if self.config.get("request_seed", False):
            body["seed"] = seed
        start = time.perf_counter()
        try:
            payload = self.request("/chat/completions", body)
        except BackendStopped as exc:
            append_json(self.output / "transport.jsonl", {**metadata, "call": call,
                "http_status": getattr(exc, "http_status", None),
                "http_metadata": getattr(exc, "http_metadata", {}),
                "retry_after": getattr(exc, "retry_after", None),
                "outcome": "no_preserved_response_identity; reservation retained"})
            self.ledger.stopped = True  # Unknown billing: keep the reservation.
            raise
        elapsed = time.perf_counter() - start
        usage = payload.get("usage") or {}
        choice = (payload.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        record = {**metadata, "call": call, "model": model["id"],
                  "returned_model": payload.get("model"), "provider": payload.get("provider"),
                  "generation_id": payload.get("id"), "messages": messages,
                  "content": content, "finish_reason": choice.get("finish_reason"),
                  "usage": usage, "elapsed_seconds": elapsed, "draw_seed": seed,
                  "seed_sent": body.get("seed")}
        insured_empty_error(record)
        usage = record["usage"]
        append_json(self.output / "calls.jsonl", record)
        self.ledger.settle(call, usage.get("cost"))
        expected_provider = model.get("provider_name", "SiliconFlow")
        if str(payload.get("provider") or "").lower() != expected_provider.lower():
            raise BackendStopped("Returned provider differs from the pinned provider")
        if (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0):
            raise BackendStopped("Reasoning tokens returned despite disabled reasoning")
        if record.get("billing_source") != "published_zero_completion_insurance" and (
                usage.get("prompt_tokens", input_cap + 1) > input_cap or usage.get(
                "completion_tokens", max_tokens + 1) > max_tokens):
            raise BackendStopped("Reported token usage exceeds the admitted token ceiling")
        record["cost_usd"] = usage["cost"]
        return record
