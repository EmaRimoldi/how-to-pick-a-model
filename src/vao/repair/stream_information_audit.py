"""Receipt/stream consistency for the distinct scientific streaming bank."""
from decimal import Decimal
import re

from .contract_collection import read
from .provider import dollars
from .records import rows


def validate_stream_evidence(output, packet, admitted, settled, pending, receipts, committed, carried):
    """Validate saved projections, not a raw-wire replay (wire bytes are not saved)."""
    metrics = {p.stem: read(p) for p in (output / 'stream-metrics').glob('*.json')}
    if set(metrics) - set(admitted):
        raise ValueError('Orphan stream metrics')
    for key, metric in metrics.items():
        if (metric.get('format') != 'bounded_sse_transport_v1'
                or metric.get('wire_limit_bytes') != packet['design']['wire_limit_bytes']
                or metric.get('partial_content_persisted') is not False
                or not re.fullmatch(r'[a-f0-9]{64}', metric.get('wire_sha256', ''))):
            raise ValueError('Stream envelope or metric identity differs')
        for name in ('wire_bytes', 'parsed_chunks', 'content_characters', 'sse_comments'):
            if type(metric.get(name)) is not int or metric[name] < 0:
                raise ValueError('Invalid stream count')
        dollars(metric['reported_cost_usd'])
    for key, amount in settled.items():
        metric = metrics.get(key, {})
        raw = read(output / 'receipts' / (key + '.raw.json'))
        if (raw.get('reconstructed_from_sse') is not True
                or metric.get('stream_complete') is not True or metric.get('done_received') is not True
                or metric.get('usage_received') is not True or metric.get('protocol_error') is not None
                or not 0 < metric.get('wire_bytes', 0) <= packet['design']['wire_limit_bytes']
                or metric.get('parsed_chunks', 0) <= 0
                or metric.get('finish_reason') != receipts[key]['finish_reason']
                or dollars(metric.get('reported_cost_usd', '-1')) != amount):
            raise ValueError('Settled receipt lacks consistent complete SSE evidence')
    for path in (output / 'receipts').glob('*.json'):
        if path.name.split('.')[0] not in admitted:
            raise ValueError('Orphan stream receipt')
    errors = rows(output / 'provider-errors.jsonl')
    error_keys = [e['attempt_id'] for e in errors]
    if len(error_keys) != len(set(error_keys)) or set(error_keys) - set(pending):
        raise ValueError('Repeated or unreserved stream error')
    if any(e.get('reservation_retained') is not True for e in errors):
        raise ValueError('Uncertain request lost its reservation')
    interruption = output / 'interruption.json'
    if interruption.exists():
        terminal = read(interruption)
        if ((output / 'pilot-completion.json').exists() or terminal.get('resume_allowed') is not False
                or set(error_keys) != set(pending)
                or terminal['pending'] != {k: str(v) for k, v in pending.items()}
                or dollars(terminal['settled_usd']) != sum(settled.values(), Decimal(0))
                or dollars(terminal['study_commitment_usd']) != committed
                or dollars(terminal['cumulative_commitment_usd']) != carried + committed):
            raise ValueError('Terminal stream accounting differs')
