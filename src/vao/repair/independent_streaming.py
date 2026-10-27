"""Prospective independent streaming cells; never retry or resume an old bank."""
from decimal import Decimal
import json
import math
import time

from .environment import identity
from .provider import dollars
from .records import append, rows
from .streaming import StreamingOpenRouterTransport

POLICY = {
    'maximum_retained_errors_before_continuing': 7,
    'maximum_consecutive_errors_before_continuing': 2,
    'cooldown_seconds': 120,
    'retry': False, 'resume': False, 'replace_missing': False,
    'allowed_transport_kinds': ['TimeoutError', 'URLError', 'RemoteDisconnected', 'IncompleteRead', 'ConnectionResetError'],
    'allowed_phases': ['awaiting_response_headers', 'reading_stream'],
}


def validate_retention(output, event, errors, *, already_retained, consecutive_retained):
    key = event['attempt_id']
    matches = [e for e in errors if e['attempt_id'] == key]
    if (len(matches) != 1 or already_retained >= POLICY['maximum_retained_errors_before_continuing']
            or consecutive_retained >= POLICY['maximum_consecutive_errors_before_continuing']):
        raise ValueError('Independent-cell total/consecutive error limit reached')
    error = matches[0]
    elapsed = event.get('cooldown_elapsed_seconds')
    if (error.get('http_status') is not None or error.get('transport_kind') not in POLICY['allowed_transport_kinds']
            or error.get('transport_phase') not in POLICY['allowed_phases']
            or error.get('reservation_retained') is not True or event.get('error_sha256') != identity(error)
            or event.get('cooldown_seconds') != POLICY['cooldown_seconds']
            or type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < POLICY['cooldown_seconds']
            or any((output / 'receipts' / (key + suffix)).exists() for suffix in ('.raw.json', '.json'))):
        raise ValueError('Only declared no-receipt network errors may unlock a new cell')
    metric = json.loads((output / 'stream-metrics' / (key + '.json')).read_text())
    if (metric.get('protocol_error') is not None or metric.get('usage_received') is not False
            or metric.get('done_received') is not False or metric.get('stream_complete') is not False
            or dollars(metric.get('reported_cost_usd', '-1')) != Decimal(0)
            or event.get('metric_sha256') != identity(metric)):
        raise ValueError('Partial accounting or a stream validation error is terminal')


class IndependentStreamingTransport(StreamingOpenRouterTransport):
    def __init__(self, *args, **kwargs):
        self.retained = set()
        self.consecutive_retained = 0
        super().__init__(*args, **kwargs)

    def available(self, calls=1):
        return (self.ready and not self.stopped and set(self.pending) == self.retained
                and self.conservative_committed_usd + calls * self.reserve <= self.limit)

    def complete(self, request, metadata):
        receipt = super().complete(request, metadata)
        # Any validated receipt, including an unusable artifact, resets only the
        # network-error streak. Scientific outcomes never enter this rule.
        self.consecutive_retained = 0
        return receipt

    def retain_missing_before_next(self, attempt):
        if (not self.stopped or attempt not in self.pending or attempt in self.retained
                or set(self.pending) != self.retained | {attempt} or attempt in self.observed_costs):
            return False
        errors = rows(self.output / 'provider-errors.jsonl')
        matches = [e for e in errors if e['attempt_id'] == attempt]
        metric_path = self.output / 'stream-metrics' / (attempt + '.json')
        if len(matches) != 1 or not metric_path.exists():
            return False
        event = {'event': 'retain_unknown', 'attempt_id': attempt, 'usd': str(self.pending[attempt]),
            'currency': 'USD', 'error_sha256': identity(matches[0]),
            'metric_sha256': identity(json.loads(metric_path.read_text())),
            'cooldown_seconds': POLICY['cooldown_seconds'], 'cooldown_elapsed_seconds': POLICY['cooldown_seconds']}
        try:
            validate_retention(self.output, event, errors, already_retained=len(self.retained),
                               consecutive_retained=self.consecutive_retained)
        except (ValueError, KeyError):
            return False
        # The error and reservation are already durable. A crash during cooldown
        # cannot resume and leaves the request missing/reserved without another call.
        start = time.monotonic()
        time.sleep(POLICY['cooldown_seconds'])
        event['cooldown_elapsed_seconds'] = time.monotonic() - start
        validate_retention(self.output, event, errors, already_retained=len(self.retained),
                           consecutive_retained=self.consecutive_retained)
        append(self.output / 'ledger.jsonl', event)
        self.retained.add(attempt)
        self.consecutive_retained += 1
        self.stopped = False
        return True
