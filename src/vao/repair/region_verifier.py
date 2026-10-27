"""Opt-in function-balanced diagnostics; historical verifier remains unchanged."""
import json

from .environment import canonical
from .region_trace_worker import VERSION, EVENT_LIMIT, EVENT_BYTES, BUFFER_BYTES, CAPTURE_LIMIT
from .verifier import RepairVerifier


def valid_bounds(trace, files):
    """Validate bounded worker data, not its truth or the candidate's correctness."""
    limits, retention = trace.get('limits'), trace.get('retention')
    if not isinstance(limits, dict) or not isinstance(retention, dict):
        return False
    if limits != {'events': EVENT_LIMIT, 'event_bytes': EVENT_BYTES,
                  'buffer_event_bytes': BUFFER_BYTES, 'captured_events': CAPTURE_LIMIT,
                  'locals_per_event': 8, 'value_depth': 2, 'container_items': 6, 'string_chars': 96}:
        return False
    fields = ('events_seen', 'events_captured', 'buffer_event_bytes', 'events_dropped')
    if any(type(trace.get(k)) is not int or trace[k] < 0 for k in fields):
        return False
    events, captured = trace['events'], trace['events_captured']
    if not len(events) <= captured <= min(CAPTURE_LIMIT, trace['events_seen']):
        return False
    if not 0 <= trace['buffer_event_bytes'] <= BUFFER_BYTES or trace['events_dropped'] != captured - len(events):
        return False
    if any(type(trace.get(k)) is not bool for k in ('capture_limit_reached', 'buffer_limit_reached')):
        return False
    for row in events:
        if not isinstance(row, dict) or not isinstance(row.get('file'), str) or row['file'] not in files:
            return False
        if any(type(row.get(k)) is not int or row[k] < 1 for k in ('sequence', 'function_line', 'line')):
            return False
        if (not isinstance(row.get('function'), str) or len(row['function']) > 96
                or row.get('event') not in ('line', 'return', 'exception')
                or not isinstance(row.get('locals'), dict) or len(row['locals']) > 8):
            return False
    sequences = [r['sequence'] for r in events]
    if sequences != sorted(set(sequences)) or any(n > CAPTURE_LIMIT or n > trace['events_seen'] for n in sequences):
        return False
    size = sum(len(json.dumps(r, ensure_ascii=True, allow_nan=False).encode()) for r in events)
    functions = {(r['file'], r['function_line'], r['function']) for r in events}
    counts = ('captured_functions', 'retained_functions', 'omitted_functions',
              'selected_event_bytes', 'event_candidates_rejected_for_bytes')
    if any(type(retention.get(k)) is not int or retention[k] < 0 for k in counts):
        return False
    return (size == retention['selected_event_bytes'] <= min(EVENT_BYTES, trace['buffer_event_bytes'])
            and retention['retained_functions'] == len(functions)
            and len(functions) <= retention['captured_functions'] <= captured
            and retention['omitted_functions'] == retention['captured_functions'] - len(functions)
            and retention['event_candidates_rejected_for_bytes'] <= captured)


class RegionRepairVerifier(RepairVerifier):
    def trace(self, files, entrypoint, case):
        result = self._execute(files, entrypoint, case, worker='region_trace_worker.py')
        if set(result) != {'observed', 'trace'} or not isinstance(result['observed'], dict):
            return {'available': False, 'reason': 'trace_worker_failure', 'worker_result': result}
        trace = result['trace']
        if (not isinstance(trace, dict) or trace.get('version') != VERSION
                or len(canonical(trace).encode()) > 16384 or not isinstance(trace.get('events'), list)
                or len(trace['events']) > EVENT_LIMIT or type(trace.get('intact')) is not bool):
            return {'available': False, 'reason': 'invalid_trace'}
        if not valid_bounds(trace, files):
            return {'available': False, 'reason': 'invalid_trace_bounds'}
        return {'available': trace['intact'], 'reason': None if trace['intact'] else 'tracing_disabled',
                'observed': self._observation(result['observed']), 'trace': trace}
