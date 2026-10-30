"""Opt-in bounded traces balanced across executed functions, not known fault sites.

Standalone sandbox worker. The historical tail-trace worker stays unchanged.
Compact values and execution/scoring boundaries intentionally match that worker.
"""
from __future__ import annotations

import contextlib
import importlib
import itertools
import json
import math
import os
import re
import resource
import sys

VERSION = 'function-balanced-temporal-v1'
EVENT_LIMIT = 32
EVENT_BYTES = 12000
CAPTURE_LIMIT = 512
BUFFER_BYTES = 1048576


def compact(value, depth=0):
    """Bound size and recursion without executing arbitrary object protocols."""
    kind = type(value)
    if value is None or kind is bool:
        return value
    if kind is int:
        return value if value.bit_length() <= 256 else {"omitted": "large_integer"}
    if kind is float:
        return value if math.isfinite(value) else {"omitted": "nonfinite_float"}
    if kind is str:
        return value if len(value) <= 96 else {"prefix": value[:96], "length": len(value)}
    if depth < 2 and kind in (list, tuple):
        return {"items": [compact(v, depth + 1) for v in value[:6]], "length": len(value)}
    if depth < 2 and kind is dict:
        return {"items": [[compact(k, depth + 1), compact(v, depth + 1)]
                          for k, v in itertools.islice(value.items(), 6)], "length": len(value)}
    return {"omitted": "object_or_depth_limit"}


def priority_order(events):
    """Final state, first exception, first state, then recursive time midpoints."""
    if not events:
        return []
    order = [len(events) - 1]
    exceptions = [i for i, e in enumerate(events) if e['event'] == 'exception']
    if exceptions:
        order.append(exceptions[0])
    order.append(0)
    pending = [(0, len(events) - 1)]
    while pending:
        start, end = pending.pop(0)
        if end - start > 1:
            middle = (start + end) // 2
            order.append(middle)
            pending.extend([(start, middle), (middle, end)])
    return [events[i] for i in dict.fromkeys(order)]


def select_events(events):
    """Round-robin function coverage; return unchanged sampled observations.

    Function identity includes source definition line to distinguish same-named
    methods. It is a region, not an invocation/stack identity. Only captured
    candidate events are inputs: no test label, reference or fault annotation.
    """
    regions = {}
    for row in events:
        key = (row['file'], row['function_line'], row['function'])
        regions.setdefault(key, []).append(row)
    queues = [priority_order(group) for group in regions.values()]
    selected, size, rejected_bytes = [], 0, 0
    position = 0
    while len(selected) < EVENT_LIMIT and any(position < len(q) for q in queues):
        for queue in queues:
            if position >= len(queue):
                continue
            row = queue[position]
            count = len(json.dumps(row, ensure_ascii=True, allow_nan=False).encode())
            if size + count <= EVENT_BYTES:
                selected.append(row); size += count
            else:
                rejected_bytes += 1
            if len(selected) == EVENT_LIMIT:
                break
        position += 1
    selected.sort(key=lambda r: r['sequence'])
    represented = {(r['file'], r['function_line'], r['function']) for r in selected}
    return selected, {'captured_functions': len(regions), 'retained_functions': len(represented),
        'omitted_functions': len(regions) - len(represented), 'selected_event_bytes': size,
        'event_candidates_rejected_for_bytes': rejected_bytes}


class Trace:
    def __init__(self, files):
        self.files = {os.path.abspath(name): name for name in files}
        self.events = []
        self.seen = self.buffer_bytes = 0
        self.capture_limit_reached = self.buffer_limit_reached = False

    def __call__(self, frame, event, arg):
        filename = self.files.get(frame.f_code.co_filename)
        if filename is None:
            return None
        if event not in {'line', 'return', 'exception'}:
            return self
        self.seen += 1
        if self.seen > CAPTURE_LIMIT:
            self.capture_limit_reached = True
            return None
        if self.buffer_limit_reached:
            return None
        row = {'file': filename, 'function': frame.f_code.co_name[:96],
            'function_line': frame.f_code.co_firstlineno, 'sequence': self.seen,
            'line': frame.f_lineno, 'event': event,
            'locals': {k: compact(v) for k, v in itertools.islice(frame.f_locals.items(), 8)}}
        if event == 'return':
            row['returned'] = compact(arg)
        elif event == 'exception':
            row['exception'] = type(arg[1]).__name__[:96]
        size = len(json.dumps(row, ensure_ascii=True, allow_nan=False).encode())
        if size > EVENT_BYTES:
            row['locals'] = {'omitted': 'event_byte_limit'}
            size = len(json.dumps(row, ensure_ascii=True, allow_nan=False).encode())
        if self.buffer_bytes + size > BUFFER_BYTES:
            self.buffer_limit_reached = True
            return None
        self.events.append(row); self.buffer_bytes += size
        return self

    def export(self, intact):
        selected, retention = select_events(self.events)
        return {'version': VERSION, 'events': selected, 'events_seen': self.seen,
            'events_captured': len(self.events), 'events_dropped': len(self.events) - len(selected),
            'capture_limit_reached': self.capture_limit_reached, 'buffer_limit_reached': self.buffer_limit_reached,
            'buffer_event_bytes': self.buffer_bytes, 'retention': retention, 'intact': intact,
            'line_semantics': 'locals before executing the reported line; sequence indexes captured execution events, not adjacent program steps',
            'selection_semantics': 'function definition regions in first-executed order; round-robin final, first exception, initial, then time-midpoint samples; retained events chronological; no complete-coverage guarantee',
            'limits': {'events': EVENT_LIMIT, 'event_bytes': EVENT_BYTES, 'captured_events': CAPTURE_LIMIT,
                'buffer_event_bytes': BUFFER_BYTES, 'locals_per_event': 8, 'value_depth': 2,
                'container_items': 6, 'string_chars': 96}}


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    sys.dont_write_bytecode = True
    payload = json.load(sys.stdin)
    # The unchanged parent writes only 1–2 validated candidate module names and
    # its underscore-prefixed runner. Inventory BEFORE importing candidate code.
    files = sorted(n for n in os.listdir('.') if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*\.py', n))
    if not 1 <= len(files) <= 2:
        raise ValueError('Invalid isolated candidate inventory')
    sys.path.insert(0, os.getcwd())
    tracer = Trace(files)
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            module = importlib.import_module(payload['entrypoint']['module'])
            function = getattr(module, payload['entrypoint']['function'])
        except BaseException as exc:
            observed = {'status': 'load_error', 'exception': type(exc).__name__}
            intact = True
        else:
            sys.settrace(tracer)
            try:
                value = function(*payload['args'], **payload['kwargs'])
            except BaseException as exc:
                observed = {'status': 'exception', 'exception': type(exc).__name__}
            else:
                observed = {'status': 'returned', 'value': value}
            finally:
                intact = sys.gettrace() is tracer
                sys.settrace(None)
            try:
                encoded = json.dumps(observed, allow_nan=False)
            except (TypeError, ValueError, RecursionError):
                observed = {'status': 'non_json_output'}
            else:
                if len(encoded.encode()) > 65536:
                    observed = {'status': 'output_limit'}
        result = json.dumps({'observed': observed, 'trace': tracer.export(intact)}, allow_nan=False)
    sys.__stdout__.write(result + '\n')


if __name__ == '__main__':
    main()
