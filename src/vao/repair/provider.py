"""Pinned OpenRouter adapter for the repair pilot; no implicit calls or retries.

Constructing this adapter does not authorize a collection: the pilot launcher
enforces the separately funded source freeze and a single-use campaign claim.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

from .environment import canonical, identity
from .records import append, save


class ProviderStopped(RuntimeError):
    """Stop without exposing credentials or automatically retrying a request."""

    def __init__(self, message: str, *, http_status=None, transport_kind=None):
        super().__init__(message)
        self.http_status = http_status
        self.transport_kind = transport_kind


def dollars(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ProviderStopped("Invalid monetary amount") from None
    if not result.is_finite() or result < 0:
        raise ProviderStopped("Invalid monetary amount")
    return result


@dataclass(frozen=True)
class Settings:
    model: str = "google/gemma-3-4b-it"
    endpoint: str = "parasail/bf16"
    provider_name: str = "Parasail"
    quantization: str = "bf16"
    input_per_million: str = "0.04"
    output_per_million: str = "0.05"
    input_token_ceiling: int = 32768
    max_tokens: int = 4096
    temperature: float = 0.7
    seed: int = 43117

    def __post_init__(self):
        if (self.model != "google/gemma-3-4b-it" or self.endpoint != "parasail/bf16"
                or self.provider_name != "Parasail" or self.quantization != "bf16"):
            raise ValueError("This development adapter requires the declared Gemma/Parasail endpoint")
        for name in ("input_token_ceiling", "max_tokens", "seed"):
            if type(getattr(self, name)) is not int:
                raise ValueError("Token bounds and seed must be integers")
        if not (4096 <= self.input_token_ceiling <= 65536 and 1 <= self.max_tokens <= 8192
                and 0 <= self.seed < 2**31 and type(self.temperature) in (int, float)
                and 0 < self.temperature <= 2):
            raise ValueError("Invalid generation settings")
        if dollars(self.input_per_million) <= 0 or dollars(self.output_per_million) <= 0:
            raise ValueError("Positive price bounds required")

    @property
    def reserve(self) -> Decimal:
        return (self.input_token_ceiling * dollars(self.input_per_million)
                + self.max_tokens * dollars(self.output_per_million)) / 1_000_000

    def body(self, request: dict, metadata: dict) -> dict:
        if request.get("mode") != "model_pilot" or request.get("provider_call_enabled") is not True:
            raise ProviderStopped("Offline requests cannot enable a provider call")
        messages = request["messages"]
        if (len(messages) != 2 or [m.get("role") for m in messages] != ["system", "user"]
                or any(set(m) != {"role", "content"} or not isinstance(m["content"], str) for m in messages)):
            raise ProviderStopped("Only the two declared text messages are supported")
        # A conservative byte/framing admission bound, checked against reported
        # native token usage after the call. This is not a tokenizer identity.
        if sum(len(m["content"].encode()) for m in messages) + 4096 > self.input_token_ceiling:
            raise ProviderStopped("Prompt exceeds the frozen admission bound; not sent")
        # Paired action draws receive the same seed. Seed support does not promise
        # deterministic providers or identical random draws for different prompts.
        sampling = {"seed": self.seed, **{k: metadata[k] for k in ("trajectory", "phase", "depth")}}
        if metadata["phase"] == "branch":
            sampling["draw"] = metadata["draw"]
        seed = int(identity(sampling)[:8], 16) % (2**31)
        return {"model": self.model, "messages": messages, "max_tokens": self.max_tokens,
                "temperature": self.temperature, "seed": seed, "stream": False,
                "response_format": {"type": "json_object"},
                "provider": {"only": [self.endpoint], "allow_fallbacks": False,
                             "require_parameters": True, "quantizations": [self.quantization],
                             "max_price": {"prompt": float(self.input_per_million),
                                           "completion": float(self.output_per_million)}}}


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenRouterTransport:
    """Single-writer adapter with durable reservations and explicit preflight."""

    mode = "model_pilot"

    def __init__(self, output: Path, key: str, settings: Settings, *, authorized_limit_usd: str):
        self.output, self._key, self.settings = output, key, settings
        self.limit, self.reserve = dollars(authorized_limit_usd), settings.reserve
        if not key or not 0 < self.limit <= 5 or self.reserve > self.limit:
            raise ValueError("A key and an explicitly declared sufficient pilot cap are required")
        if (output / "ledger.jsonl").exists() or (output / "provider-preflight.json").exists():
            raise ValueError("Existing provider state cannot be resumed")
        self.spent, self.pending, self.seen = Decimal(0), {}, set()
        self.observed_costs = {}
        self.ready, self.stopped = False, False

    def _exchange(self, endpoint: str, body: dict | None = None) -> dict:
        if endpoint not in {"/key", "/credits", f"/models/{self.settings.model}/endpoints", "/chat/completions"}:
            raise ProviderStopped("Undeclared API endpoint")
        request = urllib.request.Request("https://openrouter.ai/api/v1" + endpoint,
            data=None if body is None else canonical(body).encode(),
            headers={"Authorization": "Bearer " + self._key, "Content-Type": "application/json"},
            method="GET" if body is None else "POST")
        try:
            with urllib.request.build_opener(NoRedirects).open(request, timeout=180) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise ProviderStopped(f"HTTP {exc.code}; no retry; admission remains reserved",
                                  http_status=exc.code, transport_kind="http_error") from None
        except (OSError, ValueError) as exc:
            raise ProviderStopped(f"{type(exc).__name__}; no retry; admission remains reserved",
                                  transport_kind=type(exc).__name__) from None

    def preflight(self) -> dict:
        if self.ready or self.stopped or self.seen:
            raise ProviderStopped("Preflight is single-use")
        try:
            data = self._exchange(f"/models/{self.settings.model}/endpoints")["data"]
            endpoints = [e for e in data["endpoints"] if e.get("tag") == self.settings.endpoint]
            if len(endpoints) != 1 or data["id"] != self.settings.model:
                raise ProviderStopped("Pinned endpoint unavailable")
            endpoint = endpoints[0]
            if endpoint.get("provider_name") != self.settings.provider_name or endpoint.get("quantization") != self.settings.quantization:
                raise ProviderStopped("Endpoint identity changed")
            required = {"max_tokens", "temperature", "seed", "response_format"}
            if not required <= set(endpoint["supported_parameters"]):
                raise ProviderStopped("Endpoint lacks a required generation parameter")
            if (endpoint["context_length"] < self.settings.input_token_ceiling + self.settings.max_tokens
                    or endpoint["max_completion_tokens"] < self.settings.max_tokens):
                raise ProviderStopped("Endpoint context/output limits too small")
            pricing = endpoint["pricing"]
            for field, bound in (("prompt", self.settings.input_per_million),
                                 ("completion", self.settings.output_per_million)):
                if dollars(pricing[field]) * 1_000_000 > dollars(bound):
                    raise ProviderStopped("Pinned price ceiling exceeded")
            # Cache reads/writes may not exceed the already reserved input price.
            for field, value in pricing.items():
                if field in {"prompt", "completion", "discount"}:
                    continue
                bound = dollars(self.settings.input_per_million) / 1_000_000 if field in {"input_cache_read", "input_cache_write"} else Decimal(0)
                if dollars(value) > bound:
                    raise ProviderStopped("Unreserved endpoint charge")
            key = self._exchange("/key")["data"]
            credits = self._exchange("/credits")["data"]
            balance = dollars(credits["total_credits"]) - dollars(credits["total_usage"])
            if key.get("limit_remaining") is not None:
                balance = min(balance, dollars(key["limit_remaining"]))
            if balance < self.limit:
                raise ProviderStopped("Account/key balance below the declared pilot cap")
            # No key label, identifier or account balance is persisted.
            record = {"settings": asdict(self.settings), "endpoint": endpoint,
                      "credit_covers_declared_cap": True, "cap_usd": str(self.limit),
                      "reservation_usd": str(self.reserve)}
            save(self.output / "provider-preflight.json", record)
            self.ready = True
            return record
        except Exception:
            self.stopped = True
            raise

    def available(self, calls=1) -> bool:
        return self.ready and not self.stopped and not self.pending and self.spent + calls * self.reserve <= self.limit

    @property
    def conservative_committed_usd(self) -> Decimal:
        return self.spent + sum((max(amount, self.observed_costs.get(key, Decimal(0)))
                                 for key, amount in self.pending.items()), Decimal(0))

    def complete(self, request: dict, metadata: dict) -> dict:
        if not self.available() or metadata["attempt_id"] in self.seen:
            raise ProviderStopped("Duplicate attempt, missing preflight or unavailable budget")
        body = self.settings.body(request, metadata)  # Bounds checked before admission.
        attempt = metadata["attempt_id"]
        self.seen.add(attempt)
        self.pending[attempt] = self.reserve
        save(self.output / "requests" / (attempt + ".provider.json"), body)
        append(self.output / "ledger.jsonl", {"event": "reserve", "attempt_id": attempt,
               "usd": str(self.reserve), "currency": "USD"})
        start = time.perf_counter()
        try:
            payload = self._exchange("/chat/completions", body)
            # Preserve a received payload before validating or settling. Never
            # persist the bearer key, even if a server unexpectedly echoes it.
            payload = json.loads(canonical(payload).replace(self._key, "[REDACTED]"))
            save(self.output / "receipts" / (attempt + ".raw.json"), payload)
            # Account for any trustworthy amount even if later identity/usage
            # checks reject the response. An overrun must never be hidden behind
            # the smaller original reserve.
            cost = dollars(payload["usage"]["cost"])
            self.observed_costs[attempt] = cost
            if payload.get("model") != self.settings.model or payload.get("provider") != self.settings.provider_name:
                raise ProviderStopped("Response model/provider differs from the frozen endpoint")
            usage = payload["usage"]
            if cost > self.reserve:
                raise ProviderStopped("Reported charge exceeds reservation; retain receipt and stop")
            for field, bound in (("prompt_tokens", self.settings.input_token_ceiling), ("completion_tokens", self.settings.max_tokens)):
                if type(usage[field]) is not int or not 0 <= usage[field] <= bound:
                    raise ProviderStopped("Reported token usage exceeds the reserved bound")
            if not isinstance(payload.get("id"), str) or len(payload["choices"]) != 1:
                raise ProviderStopped("Ambiguous response identity or candidate count")
            choice = payload["choices"][0]
            # Malformed/truncated model output is still a billed observation.
            record = {"attempt_id": attempt, "model": payload["model"], "provider": payload["provider"],
                      "generation_id": payload["id"], "content": choice.get("message", {}).get("content"),
                      "finish_reason": choice.get("finish_reason"), "usage": usage,
                      "cost_usd": str(cost), "elapsed_seconds": time.perf_counter() - start,
                      "mode": self.mode}
            save(self.output / "receipts" / (attempt + ".json"), record)
            append(self.output / "ledger.jsonl", {"event": "settle", "attempt_id": attempt,
                   "usd": str(cost), "currency": "USD"})
            self.pending.pop(attempt)
            self.spent += cost
            return record
        except Exception as exc:
            self.stopped = True
            append(self.output / "provider-errors.jsonl", {"attempt_id": attempt,
                   "exception_type": type(exc).__name__, "reservation_retained": attempt in self.pending,
                   "http_status": getattr(exc, "http_status", None),
                   "transport_kind": getattr(exc, "transport_kind", None),
                   "conservative_committed_usd": str(self.conservative_committed_usd)})
            raise ProviderStopped("Provider call stopped; inspect saved receipt/reservation; no retry") from None
