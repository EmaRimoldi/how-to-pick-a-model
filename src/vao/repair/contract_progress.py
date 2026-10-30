"""Read-only operational audit; never summarizes treatment outcomes or calls APIs."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from vao.repair.contract_collection import validate_freeze, ContractSettings, settled_receipt
from vao.repair.provider import dollars
from vao.repair.contracts import EXTENSION_TRACE_STUDY, INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY, SNAPSHOT_TRACE_STUDY
from vao.repair.independent_transport import validate_retention
from vao.repair.records import rows


def progress(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    packet, limit, carried = validate_freeze(manifest['freeze'])
    original_reserve = Decimal(0)
    original_calls = 0
    requests = packet['requests']
    if 'continuation' in manifest:
        from vao.repair.information_continuation import validate_continuation
        packet, limit, carried, requests = validate_continuation(manifest['continuation'], root / 'parent')
        original_reserve = dollars(manifest['continuation']['retained_original_study_commitment_usd'])
        original_calls = 1
    settings = ContractSettings(**packet['provider_settings'])
    planned = {r['metadata']['attempt_id']: r for r in requests}
    # Snapshot one ledger read; files precede their corresponding reserve/settle event.
    ledger = rows(root / 'ledger.jsonl')
    pending, settled, admitted, generations = {}, {}, [], set()
    retained = set()
    independent = packet["study"] in (EXTENSION_TRACE_STUDY, INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY, SNAPSHOT_TRACE_STUDY)
    consecutive_retained = 0
    errors = rows(root / "provider-errors.jsonl")
    for event in ledger:
        key, amount = event['attempt_id'], dollars(event['usd'])
        if event['currency'] != 'USD' or key not in planned:
            raise ValueError('Unexpected billing currency or request')
        if event['event'] == 'reserve':
            if key in admitted or (pending and (not independent or set(pending) != retained)) or amount != settings.reserve:
                raise ValueError('Duplicate admission, overlapping call or changed reservation')
            if sum(settled.values(), Decimal(0)) + sum(pending.values(), Decimal(0)) + amount > limit:
                raise ValueError('Admission exceeded the frozen cap')
            if json.loads((root / 'requests' / (key + '.json')).read_text()) != planned[key]:
                raise ValueError('Prepared request drift')
            if json.loads((root / 'requests' / (key + '.provider.json')).read_text()) != planned[key]['provider_body']:
                raise ValueError('Provider payload drift')
            admitted.append(key); pending[key] = amount
        elif event['event'] == 'settle':
            if key not in pending or key in retained or amount > pending[key]:
                raise ValueError('Unreserved settlement')
            receipt = settled_receipt(root, key, amount, settings)
            if receipt['generation_id'] in generations:
                raise ValueError('Duplicate generation identity')
            generations.add(receipt['generation_id'])
            pending.pop(key); settled[key] = amount
            consecutive_retained = 0
        elif event['event'] == 'retain_unknown':
            if not independent or key not in pending or key in retained or key != admitted[-1] or amount != pending[key]:
                raise ValueError('Invalid prospective missing-cell disposition')
            if packet['study'] in (INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY, SNAPSHOT_TRACE_STUDY):
                from vao.repair.independent_streaming import validate_retention as validate_independent
                validate_independent(root, event, errors, already_retained=len(retained), consecutive_retained=consecutive_retained)
            else:
                validate_retention(root, event, errors, already_retained=len(retained))
            retained.add(key)
            consecutive_retained += 1
        else:
            raise ValueError('Unexpected ledger event')
    if admitted != list(planned)[:len(admitted)]:
        raise ValueError('Request order drift')
    unresolved = Decimal(0)
    for key, reserve in pending.items():
        raw = root / 'receipts' / (key + '.raw.json')
        known = Decimal(0)
        if raw.exists():
            try:
                known = dollars(json.loads(raw.read_text())['usage']['cost'])
            except (KeyError, TypeError, ValueError):
                pass
        metric = root / 'stream-metrics' / (key + '.json')
        if metric.exists():
            known = max(known, dollars(json.loads(metric.read_text())['reported_cost_usd']))
        unresolved += max(reserve, known)
    paid = sum(settled.values(), Decimal(0))
    observations = root / 'observations.jsonl'
    # Count line records, deliberately do not load success/format fields.
    count = sum(bool(line.strip()) for line in observations.open()) if observations.exists() else 0
    return {'utc': datetime.now(timezone.utc).isoformat(),
        'kind': 'operational_integrity_only_no_treatment_analysis',
        'admissions': len(admitted) + original_calls, 'segment_admissions': len(admitted), 'settled_responses': len(settled), 'observations': count,
        'planned_requests': len(packet['requests']), 'segment_planned_requests': len(planned), 'requests_exact_and_unique': True,
        'settled_receipts_reconciled': True, 'known_charges_usd': str(paid),
        'pending_reserves_usd': str(original_reserve + unresolved), 'study_commitment_usd': str(original_reserve + paid + unresolved),
        'cumulative_commitment_usd': str(carried + paid + unresolved),
        'study_cap_usd': str(limit + original_reserve), 'segment_cap_usd': str(limit), 'cap_exceeded': paid + unresolved > limit,
        'segment_complete': (root / 'pilot-completion.json').exists(),
        'complete': (root / 'pilot-completion.json').exists() and not original_calls,
        'interrupted': (root / 'interruption.json').exists(),
        'snapshot_note': 'Ledger and line count are read separately; a live writer can advance between reads. No outcome statistics or eligibility gate are computed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(progress(args.input), indent=2))


if __name__ == '__main__':
    main()
