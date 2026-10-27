"""Funded contract diagnostic: exact prepared requests, durable billing, no retries."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil

from .contracts import STUDY, DEEPINFRA_STUDY, GEMMA12B_STUDY, GEMMA27B_STUDY, TRACE_STUDY, INTERFACE_STUDY, SOLVER_STUDY, QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY, STREAM_TRACE_STUDY, INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY, COVERAGE_PREFIX_STUDY, decode, provenance, provider_body, public_feedback, task_from_record, validate, study_settings, study_spacing
from .environment import RepairRun, audit_run, identity
from .pilot import file_hashes, source_commit
from .provider import OpenRouterTransport, ProviderStopped, Settings, dollars
from .records import append, rows, save
from .verifier import RepairVerifier

ROOT = Path(__file__).resolve().parents[3]


class ContractSettings(Settings):
    def body(self, request, metadata):
        return provider_body(self, request, metadata)


def read(path):
    return json.loads(path.read_text())


def content_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authorization(config, packet, prior):
    if (config.get('status') != 'authorized_contract_diagnostic' or config.get('live_calls_enabled') is not True
            or not isinstance(config.get('authorization_reference'), str) or not config['authorization_reference'].strip()):
        raise ValueError('Explicit authorization for the new contract study is required')
    limit = dollars(config['monetary_authorization_usd'])
    if config.get('study', packet['study']) != packet['study']:
        raise ValueError('Authorization belongs to another study')
    if not dollars(packet['maximum_new_reservations_usd']) <= limit <= study_settings(packet['study'])[1]:
        raise ValueError('New study cap must cover the whole design without exceeding the proposal')
    if config.get('minimum_request_interval_seconds') != study_spacing(packet['study']):
        raise ValueError('The contract study requires its declared request spacing')
    if packet['study'] == COVERAGE_PREFIX_STUDY:
        if (prior.get('study') != CONTRASTIVE_TRACE_STUDY or prior.get('model_results') is not True
                or prior.get('gate') != 'no_completion_meets_development_screen'
                or prior.get('fit_selector') is not False or prior.get('accounting', {}).get('sealed') is not True):
            raise ValueError('Coverage prefix must carry the closed complete contrastive bank')
        carried = dollars(prior['accounting']['cumulative_committed_usd'])
    elif packet['study'] == CONTRASTIVE_TRACE_STUDY:
        if (prior.get('study') != INDEPENDENT_TRACE_STUDY or prior.get('status') != 'complete_development_information_probe'
                or prior.get('gate') != 'no_completion_meets_development_screen' or prior.get('fit_selector') is not False
                or prior.get('accounting', {}).get('sealed') is not True):
            raise ValueError('Contrastive study must carry the closed complete trace bank')
        carried = dollars(prior['accounting']['cumulative_committed_usd'])
    elif packet['study'] == INDEPENDENT_TRACE_STUDY:
        if (prior.get('study') != STREAM_TRACE_STUDY or prior.get('status') != 'incomplete_development_information_probe'
                or prior.get('gate') != 'inconclusive_incomplete_bank' or prior.get('fit_selector') is not False):
            raise ValueError('Independent calibration must carry the closed streaming bank')
        carried = dollars(prior['accounting']['cumulative_committed_usd'])
    elif packet['study'] == STREAM_TRACE_STUDY:
        if (prior.get('study') != 'repair-sse-wire-envelope-v1'
                or prior.get('status') != 'complete_compatibility_probe'
                or prior.get('gate') != 'larger_wire_envelope_observed'
                or prior.get('scientific_results') is not False or prior.get('cap_exceeded') is not False
                or prior.get('old_limit_crossed_with_complete_receipt') is not True):
            raise ValueError('Streaming calibration requires the closed wire-envelope check')
        carried = dollars(prior['cumulative_committed_usd'])
    elif packet['study'] == EXTENSION_TRACE_STUDY:
        if (prior.get('study') != QWEN_TRACE_STUDY or prior.get('status') != 'incomplete_development_information_probe'
                or prior.get('gate') != 'inconclusive_incomplete_bank' or prior.get('fit_selector') is not False):
            raise ValueError('Extension calibration must carry the closed Qwen information bank')
        carried = dollars(prior['accounting']['cumulative_committed_usd'])
    elif packet['study'] == QWEN_TRACE_STUDY:
        if (prior.get('study') != SOLVER_STUDY or prior.get('status') != 'complete_development_solver_probe'
                or prior.get('gate') != 'candidate_for_separate_intervention_calibration' or prior.get('fit_selector') is not False):
            raise ValueError('Qwen information calibration requires the closed successful compatibility screen')
        carried = dollars(prior['accounting']['cumulative_committed_usd'])
    elif packet['study'] == SOLVER_STUDY:
        if (prior.get('study') != INTERFACE_STUDY or prior.get('status') != 'incomplete_development_interface_probe'
                or prior.get('gate') != 'inconclusive_incomplete_bank' or prior.get('fit_selector') is not False):
            raise ValueError('Solver control must carry the closed incomplete interface bank')
        carried = dollars(prior['accounting']['cumulative_committed_usd'])
    elif packet['study'] == INTERFACE_STUDY:
        if (prior.get('study') != TRACE_STUDY or prior.get('status') != 'incomplete_development_information_probe'
                or prior.get('gate') != 'inconclusive_incomplete_bank' or prior.get('fit_selector') is not False):
            raise ValueError('Interface study must carry the closed incomplete information bank')
        carried = dollars(prior['accounting']['cumulative_committed_usd'])
    elif packet['study'] == DEEPINFRA_STUDY:
        if prior.get('study') != STUDY or prior.get('status') != 'incomplete_development_diagnostic':
            raise ValueError('DeepInfra study must carry the closed Parasail diagnostic')
        carried = dollars(prior['accounting']['cumulative_committed_usd'])
    elif packet['study'] in (GEMMA12B_STUDY, GEMMA27B_STUDY, TRACE_STUDY):
        previous = {GEMMA12B_STUDY: DEEPINFRA_STUDY, GEMMA27B_STUDY: GEMMA12B_STUDY,
                    TRACE_STUDY: GEMMA27B_STUDY}[packet['study']]
        if (prior.get('study') != previous or prior.get('status') != 'development_diagnostic_complete'
                or prior.get('gate') != 'no_contract_meets_engineering_checks'):
            raise ValueError('Capability calibration must carry the completed unsuccessful preceding contract diagnostic')
        carried = dollars(prior['accounting']['cumulative_committed_usd'])
    else:
        carried = dollars(prior['conservative_committed_usd'])
    if ((packet['study'] != STREAM_TRACE_STUDY and prior.get('model_results') is not True)
            or carried != dollars(packet['closed_pilot_commitment_usd'])):
        raise ValueError('Closed-pilot commitment is not preserved')
    cumulative = dollars(config['cumulative_limit_usd'])
    if carried + limit > cumulative or cumulative > Decimal('.60'):
        raise ValueError('Cumulative cap omits prior charges/reserves or exceeds 0.60 USD')
    return limit, carried


def freeze(packet, config, output: Path):
    validate(packet)
    if packet['study'] == COVERAGE_PREFIX_STUDY:
        from .coverage_prefix import validate_origin
        validate_origin(packet)
    if packet['study'] == CONTRASTIVE_TRACE_STUDY:
        from .contrastive_study import validate_origin
        validate_origin(packet)
    if packet['study'] in (QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY, STREAM_TRACE_STUDY, INDEPENDENT_TRACE_STUDY):
        if packet['study'] == INDEPENDENT_TRACE_STUDY:
            from .independent_information_study import validate_origin
        elif packet['study'] == STREAM_TRACE_STUDY:
            from .stream_information_study import validate_origin
        elif packet['study'] == EXTENSION_TRACE_STUDY:
            from .extension_information_study import validate_origin
        else:
            from .qwen_information_study import validate_origin
        validate_origin(packet)
    if packet['study'] == SOLVER_STUDY:
        from .solver_study import validate_origin
        validate_origin(packet)
    if packet['study'] == INTERFACE_STUDY:
        from .interface_study import validate_origin
        validate_origin(packet)
    if packet['study'] == TRACE_STUDY:
        from .diagnostic_study import validate_origin
        validate_origin(packet)
    tasks = [task_from_record(t) for t in packet['tasks']]
    if packet['source_provenance'] != provenance(tasks, packet['study']):
        raise ValueError('Rebuild the offline packet after source changes')
    prior_path = Path(config['closed_pilot_report'])
    prior = read(prior_path)
    limit, carried = authorization(config, packet, prior)
    record = {'schema_version': 1, 'study': packet['study'], 'created_at': datetime.now(timezone.utc).isoformat(),
              'source_commit': source_commit(), 'packet': packet, 'config': config,
              'authorized_limit_usd': str(limit), 'carried_commitment_usd': str(carried),
              'prior_report_sha256': content_hash(prior_path), 'prior_report': prior}
    record['freeze_id'] = identity(record)
    save(output, record)
    return record


def validate_freeze(frozen, *, current=False):
    if (frozen['study'] != frozen['packet']['study'] or frozen['schema_version'] != 1
            or identity({k:v for k,v in frozen.items() if k != 'freeze_id'}) != frozen['freeze_id']):
        raise ValueError('Contract freeze identity changed')
    packet = frozen['packet']
    validate(packet)
    limit, carried = authorization(frozen['config'], packet, frozen['prior_report'])
    if dollars(frozen['authorized_limit_usd']) != limit or dollars(frozen['carried_commitment_usd']) != carried:
        raise ValueError('Frozen financial projection differs')
    if current:
        if packet['study'] == COVERAGE_PREFIX_STUDY:
            from .coverage_prefix import validate_origin
            validate_origin(packet)
        if packet['study'] == CONTRASTIVE_TRACE_STUDY:
            from .contrastive_study import validate_origin
            validate_origin(packet)
        if packet['study'] in (QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY, STREAM_TRACE_STUDY, INDEPENDENT_TRACE_STUDY):
            if packet['study'] == INDEPENDENT_TRACE_STUDY:
                from .independent_information_study import validate_origin
            elif packet['study'] == STREAM_TRACE_STUDY:
                from .stream_information_study import validate_origin
            elif packet['study'] == EXTENSION_TRACE_STUDY:
                from .extension_information_study import validate_origin
            else:
                from .qwen_information_study import validate_origin
            validate_origin(packet)
        if source_commit() != frozen['source_commit'] or provenance([task_from_record(t) for t in packet['tasks']], packet['study']) != packet['source_provenance']:
            raise ValueError('Current source differs from the reviewed freeze')
        prior_path = Path(frozen['config']['closed_pilot_report'])
        if content_hash(prior_path) != frozen['prior_report_sha256'] or read(prior_path) != frozen['prior_report']:
            raise ValueError('Closed prior evidence changed')
        if packet['study'] == TRACE_STUDY:
            from .diagnostic_study import validate_origin
            validate_origin(packet)
        if packet['study'] == INTERFACE_STUDY:
            from .interface_study import validate_origin
            validate_origin(packet)
        if packet['study'] == SOLVER_STUDY:
            from .solver_study import validate_origin
            validate_origin(packet)
    return packet, limit, carried


def collect(frozen, output: Path, *, claim_root=None, continuation=None):
    if continuation is None:
        packet, limit, carried = validate_freeze(frozen, current=True)
        planned_requests = packet['requests']
        expected_provenance = packet['source_provenance']
        claim_name = packet['study']
    else:
        from .information_continuation import validate_continuation, CLAIM
        packet, limit, carried, planned_requests = validate_continuation(
            continuation, Path(continuation['parent_run']), current=True)
        if frozen != continuation['original_freeze']:
            raise ValueError('Continuation changed original freeze')
        expected_provenance = continuation['source_provenance']
        claim_name = CLAIM
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise ValueError('Set the authorized key privately in the process environment')
    if output.exists():
        raise ValueError('Existing output cannot be resumed')
    verifier = RepairVerifier()
    verifier.preflight()
    tasks = [task_from_record(t) for t in packet['tasks']]
    # Check frozen initial feedback before any provider operation; never retune it.
    for task, record in zip(tasks, packet['tasks']):
        actual = verifier.check(task.public['files'], task.public['entrypoint'], task.public['public_cases'])
        if public_feedback(actual) != public_feedback(record['initial_public_result']):
            raise ValueError('Initial feedback no longer reproduces')
    if packet['study'] in (TRACE_STUDY, QWEN_TRACE_STUDY, EXTENSION_TRACE_STUDY, STREAM_TRACE_STUDY, INDEPENDENT_TRACE_STUDY):
        from .diagnostic_study import validate_diagnostics
        validate_diagnostics(packet, verifier)
    if packet['study'] == CONTRASTIVE_TRACE_STUDY:
        from .contrastive_study import validate_diagnostics
        validate_diagnostics(packet, verifier)
    claims = claim_root or ROOT / 'runs' / 'repair-contract-admissions'
    claims.mkdir(parents=True, exist_ok=True)
    # Fixed study identity, not caller-controlled campaign names: one attempt only.
    save(claims / (claim_name + '.json'), {'freeze_id': frozen['freeze_id'], 'output': str(output.resolve()),
                                   'created_at': datetime.now(timezone.utc).isoformat(), 'resume_allowed': False})
    output.mkdir(parents=True, exist_ok=False)
    for name in ('requests', 'receipts', 'cells'):
        (output / name).mkdir()
    extra = {}
    if continuation is not None:
        shutil.copytree(continuation['parent_run'], output / 'parent')
        from .information_continuation import validate_continuation
        validate_continuation(continuation, output / 'parent')
        extra['continuation'] = continuation
    save(output / 'manifest.json', {'mode': 'model_contract_diagnostic', 'model_results': True,
                                    'currency': 'USD', 'freeze': frozen, **extra})
    transport_type = OpenRouterTransport
    if packet['study'] == EXTENSION_TRACE_STUDY:
        from .independent_transport import IndependentCellTransport
        transport_type = IndependentCellTransport
    settings, options = ContractSettings(**packet['provider_settings']), {}
    if packet['study'] in (STREAM_TRACE_STUDY, INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY, COVERAGE_PREFIX_STUDY):
        from .streaming import StreamingOpenRouterTransport, StreamingSettings
        transport_type = StreamingOpenRouterTransport
        settings = StreamingSettings(**packet['provider_settings'])
        options['max_wire_bytes'] = packet['design']['wire_limit_bytes']
        if packet['study'] in (INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY):
            from .independent_streaming import IndependentStreamingTransport
            transport_type = IndependentStreamingTransport
    transport = transport_type(output, key, settings,
        authorized_limit_usd=str(limit), minimum_interval_seconds=study_spacing(packet['study']), **options)
    try:
        transport.preflight()
        generation_ids = set()
        for planned in planned_requests:
            meta = planned['metadata']; attempt = meta['attempt_id']
            task = tasks[meta['task_index']]
            save(output / 'requests' / (attempt + '.json'), planned)
            try:
                receipt = transport.complete(planned['request'], meta)
            except ProviderStopped:
                if (packet['study'] in (EXTENSION_TRACE_STUDY, INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY)
                        and transport.retain_missing_before_next(attempt)):
                    continue
                raise
            if receipt['generation_id'] in generation_ids:
                raise ProviderStopped('Repeated provider generation identity; stop without another call')
            generation_ids.add(receipt['generation_id'])
            decoded = decode(task, receipt['content'], receipt['finish_reason'], meta['contract'])
            run = RepairRun(output / 'cells' / attempt, task, verifier, mode='model_pilot')
            artifact = public = evaluator = None
            full_pass = False
            if decoded['artifact_valid']:
                artifact = run.snapshot(decoded['files'])
                public, evaluator = run.evaluate(artifact, 'public'), run.evaluate(artifact, 'evaluator')
                full_pass = run.get(public)['result']['passed'] and run.get(evaluator)['result']['passed']
            result = {**meta, 'decoded': {k:v for k,v in decoded.items() if k != 'files'},
                      'artifact': artifact, 'public': public, 'evaluator': evaluator,
                      'full_pass': full_pass, 'cost_usd': receipt['cost_usd']}
            append(output / 'observations.jsonl', result)
            save(run.root / 'completion.json', {'audit': audit_run(run.root), 'mode': 'model_pilot'})
        if provenance(tasks, packet['study']) != expected_provenance:
            raise ValueError('Source changed during collection')
    except Exception as exc:
        interruption = {'exception_type': type(exc).__name__, 'resume_allowed': False,
            'settled_usd': str(transport.spent), 'pending': {k:str(v) for k,v in transport.pending.items()},
            'study_commitment_usd': str(transport.conservative_committed_usd),
            'cumulative_commitment_usd': str(carried + transport.conservative_committed_usd)}
        if continuation is not None:
            original_accounting = audit(output / 'parent')
            interruption.update(segment_commitment_usd=interruption['study_commitment_usd'],
                segment_pending=dict(interruption['pending']),
                pending={**original_accounting['pending'], **interruption['pending']},
                study_commitment_usd=str(dollars(original_accounting['study_committed_usd'])
                                        + transport.conservative_committed_usd))
        save(output / 'interruption.json', interruption)
        raise
    if transport.pending:
        # All scheduled cells were visited, but transport uncertainty is not a complete bank.
        save(output / 'interruption.json', {'exception_type': 'ScheduleExhaustedWithMissing',
            'resume_allowed': False, 'scheduled_requests_exhausted': True,
            'settled_usd': str(transport.spent), 'pending': {k: str(v) for k, v in transport.pending.items()},
            'study_commitment_usd': str(transport.conservative_committed_usd),
            'cumulative_commitment_usd': str(carried + transport.conservative_committed_usd)})
    else:
        save(output / 'pilot-completion.json', {'observations': len(planned_requests), 'file_hashes': file_hashes(output)})
    return audit(output)



def settled_receipt(output, key, amount, settings):
    receipt = read(output / 'receipts' / (key + '.json'))
    raw = read(output / 'receipts' / (key + '.raw.json'))
    if (receipt['attempt_id'] != key or receipt['mode'] != 'model_pilot'
            or receipt['model'] != settings.model or receipt['provider'] != settings.provider_name
            or dollars(receipt['cost_usd']) != amount
            or raw['model'] != settings.model or raw['provider'] != settings.provider_name
            or len(raw['choices']) != 1 or receipt['generation_id'] != raw['id']
            or receipt['usage'] != raw['usage']
            or dollars(raw['usage']['cost']) != amount
            or receipt['content'] != raw['choices'][0].get('message', {}).get('content')
            or receipt['finish_reason'] != raw['choices'][0].get('finish_reason')):
        raise ValueError('Receipt projection or accounting differs')
    for field, bound in [('prompt_tokens', settings.input_token_ceiling), ('completion_tokens', settings.max_tokens)]:
        if type(raw['usage'][field]) is not int or not 0 <= raw['usage'][field] <= bound:
            raise ValueError('Unreserved token usage')
    return receipt


def audit(output: Path):
    manifest = read(output / 'manifest.json')
    if manifest['mode'] != 'model_contract_diagnostic' or not manifest['model_results'] or manifest['currency'] != 'USD':
        raise ValueError('Incorrect evidence mode/currency')
    if 'continuation' in manifest:
        from .information_continuation import audit_continuation
        return audit_continuation(output, manifest)
    packet, limit, carried = validate_freeze(manifest['freeze'])
    return _audit_records(output, packet, limit, carried, packet['requests'])


def _audit_records(output, packet, limit, carried, requests):
    """Audit one already validated segment; admission lists are never inferred."""
    manifest = read(output / 'manifest.json')
    settings = ContractSettings(**packet['provider_settings'])
    planned = {r['metadata']['attempt_id']: r for r in requests}
    pending, settled, admitted = {}, {}, []
    retained = set()
    independent = packet["study"] in (EXTENSION_TRACE_STUDY, INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY)
    consecutive_retained = 0
    errors = rows(output / "provider-errors.jsonl")
    for event in rows(output / 'ledger.jsonl'):
        key, amount = event['attempt_id'], dollars(event['usd'])
        if key not in planned or event['currency'] != 'USD':
            raise ValueError('Undeclared admission or currency')
        if event['event'] == 'reserve':
            if ((bool(pending) and (not independent or set(pending) != retained)) or key in admitted
                    or amount != settings.reserve or sum(settled.values()) + sum(pending.values()) + amount > limit):
                raise ValueError('Repeated admission or violated cap')
            pending[key] = amount; admitted.append(key)
            request = read(output / 'requests' / (key + '.json'))
            body = read(output / 'requests' / (key + '.provider.json'))
            if request != planned[key] or body != planned[key]['provider_body']:
                raise ValueError('Admitted request differs from packet')
        elif event['event'] == 'settle':
            if key not in pending or key in retained or amount > pending[key]:
                raise ValueError('Invalid settlement')
            pending.pop(key); settled[key] = amount
            consecutive_retained = 0
        elif event['event'] == 'retain_unknown':
            if not independent or key not in pending or key in retained or key != admitted[-1] or amount != pending[key]:
                raise ValueError('Undeclared missing-cell disposition')
            if packet['study'] in (INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY):
                from .independent_streaming import validate_retention
                validate_retention(output, event, errors, already_retained=len(retained),
                                   consecutive_retained=consecutive_retained)
            else:
                from .independent_transport import validate_retention
                validate_retention(output, event, errors, already_retained=len(retained))
            retained.add(key)
            consecutive_retained += 1
        else:
            raise ValueError('Unknown ledger event')
    if admitted != list(planned)[:len(admitted)]:
        raise ValueError('Collection order changed')
    seen, generations, receipts = set(), set(), {}
    for key, amount in settled.items():
        receipt = settled_receipt(output, key, amount, settings)
        if receipt['generation_id'] in generations:
            raise ValueError('Repeated provider generation identity')
        generations.add(receipt['generation_id']); receipts[key] = receipt
    for row in rows(output / 'observations.jsonl'):
        key = row['attempt_id']
        if key in seen or key not in settled:
            raise ValueError('Repeated or unaccounted observation')
        seen.add(key)
        expected = planned[key]; meta = expected['metadata']
        if any(row.get(k) != v for k,v in meta.items()):
            raise ValueError('Observation metadata drift')
        receipt = receipts[key]
        if dollars(row['cost_usd']) != settled[key]:
            raise ValueError('Observation charge differs')
        task = task_from_record(packet['tasks'][meta['task_index']])
        decoded = decode(task, receipt['content'], receipt['finish_reason'], meta['contract'])
        if row['decoded'] != {k:v for k,v in decoded.items() if k != 'files'}:
            raise ValueError('Decoder drift or altered classification')
        cell = output / 'cells' / key
        audit_run(cell)
        obj = lambda ref: read(cell / 'objects' / (ref + '.json'))
        task_obj = obj(read(cell / 'events' / '000000.json')['objects'][0])
        if task_obj['public'] != task.public or task_obj['evaluator'] != json.loads(task.evaluator_json):
            raise ValueError('Verifier task differs from prepared task')
        if decoded['artifact_valid']:
            if obj(row['artifact'])['files'] != decoded['files']:
                raise ValueError('Evaluated code differs from decoded response')
            pub, ev = obj(row['public']), obj(row['evaluator'])
            if (pub['artifact'] != row['artifact'] or ev['artifact'] != row['artifact']
                    or pub['channel'] != 'public' or ev['channel'] != 'evaluator'
                    or row['full_pass'] != (pub['result']['passed'] and ev['result']['passed'])):
                raise ValueError('Verifier outcome or attachment mismatch')
        elif any(row[k] is not None for k in ('artifact','public','evaluator')) or row['full_pass']:
            raise ValueError('Malformed output given fabricated success/artifact')
    for cell in (output / 'cells').glob('*'):
        if cell.name not in settled:
            raise ValueError('Unaccounted verifier cell')
        audit_run(cell)
    committed_by_attempt = dict(settled)
    committed = sum(settled.values(), Decimal(0))
    for key, reserve in pending.items():
        known = Decimal(0)
        raw = output / 'receipts' / (key + '.raw.json')
        if raw.exists():
            try:
                known = dollars(read(raw)['usage']['cost'])
            except (KeyError, TypeError, ValueError, ProviderStopped):
                pass
        if packet['study'] in (STREAM_TRACE_STUDY, INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY, COVERAGE_PREFIX_STUDY):
            metric = output / 'stream-metrics' / (key + '.json')
            if metric.exists():
                known = max(known, dollars(read(metric)['reported_cost_usd']))
        committed_by_attempt[key] = max(reserve, known)
        committed += max(reserve, known)
    if packet['study'] in (STREAM_TRACE_STUDY, INDEPENDENT_TRACE_STUDY, CONTRASTIVE_TRACE_STUDY, COVERAGE_PREFIX_STUDY):
        from .stream_information_audit import validate_stream_evidence
        validate_stream_evidence(output, packet, admitted, settled, pending, receipts, committed, carried)
    completion = output / 'pilot-completion.json'
    if completion.exists():
        saved = read(completion)
        if pending or seen != set(planned) or set(settled) != seen or saved['observations'] != len(seen) or saved['file_hashes'] != file_hashes(output):
            raise ValueError('Sealed bank is incomplete or modified')
    return {'observations': len(seen), 'admissions': len(admitted), 'planned_calls': len(planned),
            'paid_without_outcome': sorted(set(settled) - seen),
            'pending': {k:str(v) for k,v in pending.items()}, 'settled_usd': str(sum(settled.values(), Decimal(0))),
            'study_committed_usd': str(committed),
            'committed_by_attempt_usd': {k:str(v) for k,v in committed_by_attempt.items()},
            'carried_committed_usd': str(carried),
            'cumulative_committed_usd': str(carried + committed), 'sealed': completion.exists(),
            'cap_exceeded': committed > limit or carried + committed > dollars(manifest['freeze']['config']['cumulative_limit_usd'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze','live','audit'))
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'freeze':
        if not args.config or not args.output:
            parser.error('freeze requires --config and fresh --output')
        frozen = freeze(read(args.input), read(args.config), args.output)
        result = {k:frozen[k] for k in ('freeze_id','source_commit','authorized_limit_usd')}
    elif args.action == 'live':
        if not args.output:
            parser.error('live requires fresh --output')
        result = collect(read(args.input), args.output)
    else:
        result = audit(args.input)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
