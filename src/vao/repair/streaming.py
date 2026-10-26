"""Opt-in SSE transport; historical collectors keep their non-streaming adapter.

This module enables no collection on import. A new protocol/freeze must opt in.
Only a completed identity/usage/terminal sequence becomes a billed observation.
Partial text is never treated as a result or retried. Wire bytes stay in memory;
safe counts and a digest are persisted, without free-form error/partial content.
"""
from dataclasses import dataclass
from decimal import Decimal
import codecs
import hashlib
import http.client
import json
import re
import time
import urllib.error
import urllib.request

from .environment import canonical
from .provider import NoRedirects, OpenRouterTransport, ProviderStopped, Settings, dollars, safe_error_details
from .records import save


class StreamProtocolError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)  # Internal fixed vocabulary, never response text.


class SSEFrames:
    """Bounded UTF-8/SSE framing, independent of HTTP read boundaries."""
    def __init__(self, max_bytes=1048576):
        self.decoder = codecs.getincrementaldecoder('utf-8-sig')()
        self.max_bytes = max_bytes
        self.bytes = self.comments = self.events = 0
        self.digest = hashlib.sha256()
        self.line = ''
        self.data = []
        self.frame_chars = 0
        self.after_cr = False

    def feed(self, chunk):
        if not isinstance(chunk, bytes):
            raise StreamProtocolError('nonbyte_stream')
        self.bytes += len(chunk)
        self.digest.update(chunk)
        if self.bytes > self.max_bytes:
            raise StreamProtocolError('wire_limit')
        text = self.decoder.decode(chunk)
        result = []
        for char in text:
            if self.after_cr:
                self.after_cr = False
                if char == '\n':
                    continue
            if char in '\r\n':
                event = self._line()
                self.after_cr = char == '\r'
                if event is not None:
                    result.append(event)
            else:
                self.line += char
                if len(self.line) > 65536:
                    raise StreamProtocolError('line_limit')
        return result

    def _line(self):
        line, self.line = self.line, ''
        if not line:
            data, self.data = self.data, []
            self.frame_chars = 0
            if data:
                self.events += 1
                if self.events > 32768:
                    raise StreamProtocolError('event_limit')
                return '\n'.join(data)
        elif line.startswith(':'):
            self.comments += 1
        else:
            field, _, value = line.partition(':')
            if value.startswith(' '):
                value = value[1:]
            if field == 'data':
                self.frame_chars += len(value) + 1
                if self.frame_chars > 262144:
                    raise StreamProtocolError('frame_limit')
                self.data.append(value)
            # SSE id/retry/other fields do not enable reconnection or retries.
        return None


def strict_json(text):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise StreamProtocolError('duplicate_json_key')
            result[k] = v
        return result
    def constant(_):
        raise StreamProtocolError('nonfinite_json')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


class ChatStream:
    """One candidate; no content after finish, except the final usage frame.

[DONE] ends the response. Later bytes/events cannot trigger another settlement.
A repeated finish_reason on the usage-only frame is valid OpenRouter framing.
"""
    def __init__(self, model, provider):
        self.expected_model, self.expected_provider = model, provider
        self.identities = {}
        self.content = []
        self.content_chars = self.frames = 0
        self.finish_reason = None
        self.usage = None
        self.done = False
        self.observed_cost = Decimal(0)

    def consume(self, event):
        if self.done:
            return
        if event == '[DONE]':
            if self.finish_reason is None or self.usage is None or set(self.identities) != {'id', 'model', 'provider'}:
                raise StreamProtocolError('premature_done')
            self.done = True
            return
        self.frames += 1
        p = strict_json(event)
        if not isinstance(p, dict):
            raise StreamProtocolError('nonobject_chunk')
        usage = p.get('usage')
        # Preserve a reported amount even if identity or terminal validation fails.
        if isinstance(usage, dict) and 'cost' in usage:
            try:
                self.observed_cost = max(self.observed_cost, dollars(usage['cost']))
            except ProviderStopped:
                pass
        if p.get('error') is not None:
            raise StreamProtocolError('provider_stream_error')
        for field in ('id', 'model', 'provider'):
            if field not in p:
                continue
            value = p[field]
            if not isinstance(value, str) or not value or len(value) > 512:
                raise StreamProtocolError('invalid_identity')
            expected = {'model': self.expected_model, 'provider': self.expected_provider}.get(field)
            if (expected is not None and value != expected) or (field in self.identities and self.identities[field] != value):
                raise StreamProtocolError('changed_identity')
            self.identities[field] = value
        choices = p.get('choices')
        if not isinstance(choices, list) or len(choices) > 1 or (not choices and usage is None):
            raise StreamProtocolError('candidate_count')
        content = None
        finish = None
        if choices:
            choice = choices[0]
            if not isinstance(choice, dict) or type(choice.get('index')) is not int or choice['index'] != 0:
                raise StreamProtocolError('candidate_index')
            if choice.get('error') is not None:
                raise StreamProtocolError('provider_stream_error')
            delta = choice.get('delta')
            if not isinstance(delta, dict):
                raise StreamProtocolError('invalid_delta')
            if delta.get('role') not in (None, 'assistant'):
                raise StreamProtocolError('invalid_role')
            for field in ('tool_calls', 'function_call', 'images', 'audio', 'reasoning', 'reasoning_details', 'refusal'):
                if delta.get(field) not in (None, '', []):
                    raise StreamProtocolError('unsupported_delta')
            content = delta.get('content')
            if content is not None and not isinstance(content, str):
                raise StreamProtocolError('invalid_content')
            finish = choice.get('finish_reason')
            if finish is not None and finish not in {'stop', 'length', 'content_filter'}:
                raise StreamProtocolError('invalid_finish')
        if self.usage is not None:
            raise StreamProtocolError('event_after_usage')
        if self.finish_reason is not None and (content or usage is None or finish not in (None, self.finish_reason)):
            raise StreamProtocolError('event_after_finish')
        if usage is not None and content:
            raise StreamProtocolError('content_on_usage_frame')
        if content is not None:
            self.content_chars += len(content)
            if self.content_chars > 524288:
                raise StreamProtocolError('content_limit')
            self.content.append(content)
        if finish is not None:
            self.finish_reason = finish
        if usage is not None:
            if not isinstance(usage, dict) or self.finish_reason is None:
                raise StreamProtocolError('premature_usage')
            try:
                dollars(usage['cost'])
                for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                    if type(usage[key]) is not int or usage[key] < 0:
                        raise StreamProtocolError('invalid_usage')
                if usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']:
                    raise StreamProtocolError('invalid_usage')
            except (KeyError, ProviderStopped):
                raise StreamProtocolError('invalid_usage') from None
            self.usage = usage

    def result(self):
        if not self.done:
            raise StreamProtocolError('incomplete_stream')
        return {**self.identities, 'object': 'chat.completion',
                'choices': [{'finish_reason': self.finish_reason,
                             'message': {'role': 'assistant', 'content': ''.join(self.content)}}],
                'usage': self.usage, 'reconstructed_from_sse': True}


@dataclass(frozen=True)
class StreamingSettings(Settings):
    def body(self, request, metadata):
        return {**super().body(request, metadata), 'stream': True}


class StreamingOpenRouterTransport(OpenRouterTransport):
    """First-error-stop transport, separate from every closed scientific study.

Uses the existing reservation/settlement lifecycle. An idle read is bounded by
180 s; a 300 s wall limit is checked at read boundaries, not a hard deadline.
A blocked read can overrun that wall limit by the socket timeout. No cancellation
or refund is inferred. Complete usage overages are retained even without DONE.
"""
    def __init__(self, output, key, settings, **kwargs):
        if not isinstance(settings, StreamingSettings):
            raise ValueError('Explicit StreamingSettings required')
        self._stream_attempt = None
        super().__init__(output, key, settings, **kwargs)
        (self.output / 'stream-metrics').mkdir()

    def complete(self, request, metadata):
        attempt = metadata.get('attempt_id')
        if not isinstance(attempt, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', attempt):
            raise ProviderStopped('Invalid attempt identity')
        self._stream_attempt = attempt
        try:
            return super().complete(request, metadata)
        finally:
            self._stream_attempt = None

    def _exchange(self, endpoint, body=None):
        if endpoint != '/chat/completions':
            return super()._exchange(endpoint, body)
        attempt = self._stream_attempt
        if (attempt not in self.pending or not isinstance(body, dict) or body.get('stream') is not True):
            raise ProviderStopped('Streaming call requires a durable reservation')
        request = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
            data=canonical(body).encode(), method='POST',
            headers={'Authorization': 'Bearer '+self._key, 'Content-Type': 'application/json',
                     'Accept': 'text/event-stream'})
        framing = SSEFrames()
        stream = ChatStream(self.settings.model, self.settings.provider_name)
        start = time.monotonic()
        phase = 'awaiting_response_headers'
        metrics = {'format': 'bounded_sse_transport_v1', 'partial_content_persisted': False,
                   'first_byte_seconds': None, 'first_content_seconds': None,
                   'stream_complete': False, 'protocol_error': None}
        try:
            with urllib.request.build_opener(NoRedirects).open(request, timeout=180) as response:
                if response.headers.get_content_type() != 'text/event-stream':
                    raise StreamProtocolError('unexpected_content_type')
                while not stream.done:
                    if time.monotonic() - start > 300:
                        raise StreamProtocolError('wall_limit_at_read_boundary')
                    phase = 'reading_stream'
                    chunk = response.read1(4096)
                    if time.monotonic() - start > 300:
                        raise StreamProtocolError('wall_limit_at_read_boundary')
                    if not chunk:
                        raise StreamProtocolError('incomplete_stream')
                    if metrics['first_byte_seconds'] is None:
                        metrics['first_byte_seconds'] = round(time.monotonic()-start, 6)
                    phase = 'parsing_stream'
                    for event in framing.feed(chunk):
                        stream.consume(event)
                        if stream.content_chars and metrics['first_content_seconds'] is None:
                            metrics['first_content_seconds'] = round(time.monotonic()-start, 6)
                        if stream.done:
                            break
                result = stream.result()
                metrics['stream_complete'] = True
                return result
        except urllib.error.HTTPError as exc:
            payload = None
            try:
                raw = exc.read(8193)
                if len(raw) <= 8192:
                    payload = json.loads(raw)
            except (OSError, ValueError, http.client.HTTPException):
                pass
            finally:
                exc.close()
            raise ProviderStopped(f'HTTP {exc.code}; no retry', http_status=exc.code,
                transport_kind='http_error', error_details=safe_error_details(payload, exc.headers),
                transport_phase=phase, exchange_elapsed_seconds=round(time.monotonic()-start, 6)) from None
        except StreamProtocolError as exc:
            metrics['protocol_error'] = exc.code
            raise ProviderStopped('SSE validation stopped; no retry', transport_kind='stream_protocol_error',
                transport_phase=phase, exchange_elapsed_seconds=round(time.monotonic()-start, 6)) from None
        except (OSError, ValueError, http.client.HTTPException) as exc:
            raise ProviderStopped('SSE read stopped; no retry', transport_kind=type(exc).__name__,
                transport_phase=phase, exchange_elapsed_seconds=round(time.monotonic()-start, 6)) from None
        finally:
            if stream.observed_cost:
                self.observed_costs[attempt] = max(self.observed_costs.get(attempt, Decimal(0)), stream.observed_cost)
            metrics.update(wire_bytes=framing.bytes, wire_sha256=framing.digest.hexdigest(),
                           sse_comments=framing.comments, parsed_chunks=stream.frames,
                           content_characters=stream.content_chars, done_received=stream.done,
                           usage_received=stream.usage is not None, finish_reason=stream.finish_reason,
                           reported_cost_usd=str(stream.observed_cost),
                           elapsed_seconds=round(time.monotonic()-start, 6))
            save(self.output/'stream-metrics'/(attempt+'.json'), metrics)
