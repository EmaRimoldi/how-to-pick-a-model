"""Prospective missing-cell handling for a separately frozen independent design.

Historical collectors never use this adapter. An uncertain request is never
retried or settled. At most one uncertain cell may be retained while proceeding
to the remaining independent scheduled cells.
"""

import time

from .environment import identity
from .provider import OpenRouterTransport
from .records import append, rows

POLICY = {
    "maximum_retained_errors_before_continuing": 1,
    "cooldown_seconds": 120,
    "retry": False,
    "resume": False,
    "replace_missing": False,
    "allowed_transport_kinds": ["TimeoutError", "URLError", "RemoteDisconnected",
                                "IncompleteRead", "ConnectionResetError"],
    "allowed_phases": ["awaiting_response_headers", "reading_response"],
}


def validate_retention(output, event, errors, *, already_retained):
    """A durable error may excuse only a new cell, never release its reserve."""
    key = event["attempt_id"]
    matches = [e for e in errors if e["attempt_id"] == key]
    if len(matches) != 1 or already_retained >= POLICY["maximum_retained_errors_before_continuing"]:
        raise ValueError("Missing-cell policy limit or error identity differs")
    error = matches[0]
    if (error.get("http_status") is not None or error.get("transport_kind") not in POLICY["allowed_transport_kinds"]
            or error.get("transport_phase") not in POLICY["allowed_phases"]
            or error.get("reservation_retained") is not True
            or event.get("error_sha256") != identity(error)
            or event.get("cooldown_seconds") != POLICY["cooldown_seconds"]
            or any((output / "receipts" / (key + suffix)).exists() for suffix in (".raw.json", ".json"))):
        raise ValueError("Only a declared no-receipt transport uncertainty can unlock the next cell")


class IndependentCellTransport(OpenRouterTransport):
    def __init__(self, *args, **kwargs):
        self.retained = set()
        super().__init__(*args, **kwargs)

    def available(self, calls=1):
        return (self.ready and not self.stopped and set(self.pending) == self.retained
                and self.conservative_committed_usd + calls * self.reserve <= self.limit)

    def retain_missing_before_next(self, attempt):
        if (not self.stopped or attempt not in self.pending or attempt in self.retained
                or set(self.pending) != self.retained | {attempt}
                or attempt in self.observed_costs):
            return False
        errors = rows(self.output / "provider-errors.jsonl")
        matches = [e for e in errors if e["attempt_id"] == attempt]
        if len(matches) != 1:
            return False
        event = {"event": "retain_unknown", "attempt_id": attempt, "usd": str(self.pending[attempt]),
                 "currency": "USD", "error_sha256": identity(matches[0]),
                 "cooldown_seconds": POLICY["cooldown_seconds"]}
        try:
            validate_retention(self.output, event, errors, already_retained=len(self.retained))
        except ValueError:
            return False
        append(self.output / "ledger.jsonl", event)
        self.retained.add(attempt)
        # The launched process sleeps; the UI/monitor remains free to report.
        # A crash here cannot resume: the study claim and reservation persist.
        time.sleep(POLICY["cooldown_seconds"])
        self.stopped = False
        return True
