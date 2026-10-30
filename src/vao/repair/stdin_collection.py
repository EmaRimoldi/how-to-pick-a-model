"""Single-use, prospectively frozen whole-program repair collection.

The live stage can observe public tests only. Private verification and analysis
are separate terminal operations. Imports and planning never call a provider.
"""
from __future__ import annotations

import base64
import copy
import fcntl
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

from . import stdin_ablation as ablation
from . import stdin_pilot as pilot
from .environment import canonical, identity
from .provider import ProviderStopped, dollars
from .records import append, rows, save
from .stdin_monitoring import MonitoringStdinVerifier
from .streaming import StreamingOpenRouterTransport, StreamingSettings

ROOT = Path(__file__).resolve().parents[3]
BASE = Path('experiments/python-repair/checkpoint-environment')
BANK = BASE / 'results/stdin-ablation-preparation-20261030'
CONFIG = BASE / 'STDIN-PILOT-AUTHORIZED.json'
LAUNCH = BASE / 'STDIN-PILOT-LAUNCH.md'
STUDY = 'stdin-generated-failure-fns-v1'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class PilotSettings(StreamingSettings):
    input_token_ceiling: int = pilot.INPUT_RESERVATION
    max_tokens: int = pilot.OUTPUT_LIMIT
    seed: int = 20261030

    def body(self, request, metadata):
        body = super().body(request, metadata)
        seed = metadata.get('slot_seed')
        if type(seed) is not int or not 0 <= seed < 2**31:
            raise ProviderStopped('Explicit frozen slot seed required')
        body['seed'] = seed
        return body


SETTINGS = PilotSettings()


def dispatch_timestamp(transport):
    return transport.last_dispatch


class PilotTransport(StreamingOpenRouterTransport):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        (self.output / 'dispatch').mkdir()

    def _exchange(self, endpoint, body=None):
        if endpoint == '/chat/completions':
            save(self.output / 'dispatch' / (self._stream_attempt+'.json'), {
                'attempt_id': self._stream_attempt, 'monotonic_admission': dispatch_timestamp(self),
                'recorded_utc': datetime.now(timezone.utc).isoformat(), 'body_sha256': identity(body)})
        return super()._exchange(endpoint, body)


def runtime():
    paths = list((ROOT / 'src/vao/repair').glob('*.py')) + [
        ROOT / 'src/vao/decisions/verification.py', ROOT / CONFIG, ROOT / LAUNCH,
        ROOT / BASE / 'STDIN-PILOT-PROTOCOL.md', ROOT / BANK / 'pilot-design.json',
        ROOT / 'scripts/repair_stdin_pilot.py', ROOT / 'pyproject.toml', ROOT / 'uv.lock']
    return {'files': {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)},
            'python_version': sys.version, 'python_executable_sha256': digest(Path(sys.executable))}


def source_commit():
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True).strip():
        raise ValueError('Tracked worktree must be clean before a live freeze/call')
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def load_inputs():
    manifest, design = read(ROOT / BANK / 'manifest.json'), read(ROOT / BANK / 'pilot-design.json')
    archive = ROOT / BANK / 'evidence.zip'
    if digest(archive) != manifest['archive_sha256']:
        raise ValueError('Preparation evidence changed')
    with zipfile.ZipFile(archive) as z:
        blobs = {n: z.read(n) for n in z.namelist()}
    if {n: hashlib.sha256(b).hexdigest() for n, b in blobs.items()} != manifest['members']:
        raise ValueError('Preparation members changed')
    preparation = json.loads(blobs['monitoring/plan.json'])
    expected = pilot.plan(preparation['tasks'], preparation['all_original_group_decisions'], digest(archive))
    if any(design[k] != v for k, v in expected.items()):
        raise ValueError('Prospective roster/order/criteria changed')
    if design['protocol_sha256'] != digest(ROOT / BASE / 'STDIN-PILOT-PROTOCOL.md'):
        raise ValueError('Prospective numerical protocol changed')
    qualification = ROOT / BASE / 'results/fixeval-source-qualification-20261030/evidence.zip'
    if digest(qualification) != preparation['qualification_archive_sha256']:
        raise ValueError('Qualification evidence changed')
    with zipfile.ZipFile(qualification) as z:
        source = json.loads(z.read('qualification-freeze.json'))
    tasks = []
    for task in preparation['tasks']:
        group = next(g for g in source['groups'] if g['problem_id'] == task['problem_id'])
        private = [{'id': c['id'], 'input_b64': c['input_b64'], 'expected_b64': c['expected_b64']}
                   for c in group['cases'] if c['split'] == 'evaluator']
        tasks.append({'problem_id': task['problem_id'], 'pair_index': task['pair_index'],
                      'binding': task['binding'], 'public': task['public'], 'private_cases': private})
    return {'design': design, 'tasks': tasks}


def validate_config(config):
    expected = {'study': STUDY, 'status': 'standing_authorization_suballocation',
                'allocation_usd': '0.32', 'prior_committed_usd': '0.25463059',
                'cumulative_cap_usd': '0.60', 'prior_uncertain_reserves': 14,
                'maximum_calls': 110, 'minimum_interval_seconds': 60,
                'max_wire_bytes': 8388608, 'resume_allowed': False, 'retries': 0,
                'key_rotation': False, 'new_explicit_human_numeric_approval': False}
    if any(type(config.get(k)) is not type(v) or config[k] != v for k, v in expected.items()):
        raise ValueError('Declared suballocation or operational constraints changed')
    if not config.get('authorization_reference'):
        raise ValueError('Standing authorization reference required')
    if SETTINGS.reserve * 110 > pilot.PROPOSED_ALLOCATION or pilot.PRIOR_COMMITMENT + pilot.PROPOSED_ALLOCATION > pilot.CUMULATIVE_CAP:
        raise ValueError('Reservations exceed the authorized cumulative ceiling')


def freeze(output):
    config = read(ROOT / CONFIG); validate_config(config)
    value = {'study': STUDY, 'inputs': load_inputs(), 'config': config, 'runtime': runtime(),
             'source_commit': source_commit(), 'created_utc': datetime.now(timezone.utc).isoformat()}
    value['freeze_id'] = identity(value)
    save(output, value)
    return {'freeze_id': value['freeze_id'], 'source_commit': value['source_commit'], 'maximum_calls': 110}


def validate_freeze(frozen, *, current=False):
    if frozen['study'] != STUDY or frozen['freeze_id'] != identity({k: v for k, v in frozen.items() if k != 'freeze_id'}):
        raise ValueError('Invalid freeze identity')
    validate_config(frozen['config'])
    if frozen['inputs'] != load_inputs():
        raise ValueError('Frozen input roster or source bytes changed')
    if current and (frozen['runtime'] != runtime() or frozen['source_commit'] != source_commit()
                    or frozen['config'] != read(ROOT / CONFIG)):
        raise ValueError('Source, runtime or suballocation changed after freeze')


def task_key(task):
    return task['binding']


def slot_meta(slot, task):
    return {'attempt_id': slot['id'], 'trajectory': task['binding'],
            'phase': 'initial' if slot['phase'] == 'initial' else 'branch',
            'depth': 0 if slot['phase'] == 'initial' else 1, 'draw': slot['draw'],
            'slot_seed': slot['seed']}


def request_for(slot, task, public, stored, acquisition):
    # This function deliberately receives only public solver state. The separate
    # task dictionary is used for an opaque trajectory binding, never messages.
    start = time.monotonic()
    projected = ablation.project(public, stored, slot['arm'], acquisition)
    request = {**projected, 'mode': 'model_pilot', 'provider_call_enabled': True}
    metadata = slot_meta(slot, task)
    size = sum(len(m['content'].encode()) for m in request['messages']) + 4096
    result = {'slot': slot, 'metadata': metadata, 'public_binding': ablation.binding(public),
              'stored_identity': identity(stored), 'request': request,
              'admission_bytes_plus_framing': size, 'projection_seconds': time.monotonic()-start}
    if size <= SETTINGS.input_token_ceiling:
        result['provider_body'] = SETTINGS.body(request, metadata)
    else:
        result['provider_body'] = None
    return result


def checkpoint(public, receipt, verifier):
    started = time.monotonic(); artifact = pilot.parse_artifact(receipt['content'])
    parsing = time.monotonic() - started
    if artifact is None:
        return {'artifact': None, 'status': 'invalid', 'public': None, 'stored': None,
                'parse_seconds': parsing}
    updated = {**copy.deepcopy(public), 'files': artifact}
    stored = ablation.observe(updated, verifier)
    passed = ablation.current_feedback(updated, stored)['passed']
    return {'artifact': artifact, 'status': 'public_pass' if passed else 'public_fail',
            'public': updated, 'stored': stored, 'parse_seconds': parsing}


class JournalVerifier:
    """Retain completed executions even if a higher-level phase later fails."""
    def __init__(self, verifier, output):
        self.verifier, self.output, self.context, self.sequence = verifier, output, {}, 0

    def preflight(self):
        start = time.monotonic()
        append(self.output / 'execution-journal.jsonl', {'event': 'preflight_start'})
        try:
            result = self.verifier.preflight()
        except Exception as exc:
            append(self.output / 'execution-journal.jsonl', {'event': 'preflight_error',
                'exception_type': type(exc).__name__, 'seconds': time.monotonic()-start,
                'candidate_executions': None})
            raise
        append(self.output / 'execution-journal.jsonl', {'event': 'preflight_finish',
            'result': result, 'seconds': time.monotonic()-start})
        return result

    def invoke(self, source, stdin, *, coverage=False):
        self.sequence += 1
        descriptor = {'event': 'start', 'sequence': self.sequence, 'context': self.context,
                      'source_sha256': hashlib.sha256(source).hexdigest(),
                      'input_sha256': hashlib.sha256(stdin).hexdigest(), 'coverage': coverage}
        append(self.output / 'execution-journal.jsonl', descriptor)
        start = time.monotonic()
        try:
            result = self.verifier.invoke(source, stdin, coverage=coverage)
        except Exception as exc:
            append(self.output / 'execution-journal.jsonl', {'event': 'error', 'sequence': self.sequence,
                'exception_type': type(exc).__name__, 'seconds': time.monotonic()-start,
                'candidate_executions': None})
            raise
        append(self.output / 'execution-journal.jsonl', {'event': 'finish', 'sequence': self.sequence,
                                                       'result': result, 'seconds': time.monotonic()-start})
        return result


def update_state(frozen, output, *, active, money=None):
    path = ROOT / 'runs/ACTIVE_RESEARCH_STATE.json'
    state = read(path)
    budget = state['current_repair_budget']
    budget['active_collectors'] = int(active)
    if money is not None:
        budget['cumulative_committed_usd'] = money['cumulative_committed_usd']
        budget['latest_study_spend_usd'] = money['known_usd']
        budget['total_unresolved_reservations'] = 14 + len(money['pending'])
        budget['stdin_pilot_study_cap_usd'] = str(pilot.PROPOSED_ALLOCATION)
        budget['stdin_pilot_pending_reserves'] = len(money['pending'])
    state['status'] = 'stdin_pilot_model_collection_active' if active else 'stdin_pilot_model_terminal_needs_verification'
    state['active'] = {'study': STUDY, 'run': str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output),
                       'pid': os.getpid(), 'process_running': active, 'resume_allowed': False,
                       'freeze_id': frozen['freeze_id'], 'source_commit': frozen['source_commit']}
    state['updated_utc'] = datetime.now(timezone.utc).isoformat()
    temporary = path.with_suffix('.stdin-tmp')
    with temporary.open('w') as stream:
        stream.write(json.dumps(state, indent=2)+'\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def collect(frozen, output):
    # Same-study exclusive claims prevent reuse after completion; the process
    # lock also prevents simultaneous budget admission by this collector.
    with (ROOT / 'runs/.stdin-pilot-budget.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('A stdin collector already owns the budget lock') from None
        return _collect(frozen, output)


def _collect(frozen, output):
    validate_freeze(frozen, current=True)
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise ValueError('Private credential required')
    if output.exists():
        raise ValueError('Never overwrite or resume a collection')
    state = read(ROOT / 'runs/ACTIVE_RESEARCH_STATE.json')['current_repair_budget']
    if (dollars(state['cumulative_committed_usd']) != pilot.PRIOR_COMMITMENT
            or state['total_unresolved_reservations'] != 14 or state['active_collectors']):
        raise ValueError('Prior accounting or active collector changed')
    claims = ROOT / 'runs/stdin-pilot-admissions'; claims.mkdir(exist_ok=True)
    save(claims / (STUDY + '.json'), {'freeze_id': frozen['freeze_id'], 'output': str(output.resolve()), 'resume_allowed': False})
    output.mkdir()
    for name in ('requests', 'receipts', 'cells', 'original-feedback', 'acquisitions', 'dispositions'):
        (output / name).mkdir()
    save(output / 'manifest.json', {'freeze': frozen})
    update_state(frozen, output, active=True)
    transport = PilotTransport(output, key, SETTINGS, authorized_limit_usd=str(pilot.PROPOSED_ALLOCATION),
                                            minimum_interval_seconds=60, max_wire_bytes=8388608)
    verifier = JournalVerifier(MonitoringStdinVerifier(5), output)
    task_map = {t['problem_id']: t for t in frozen['inputs']['tasks']}
    initials, acquired, seen = {}, {}, set()
    started = time.monotonic()
    try:
        preflight_started = time.monotonic()
        save(output / 'sandbox-preflight.json', {'result': verifier.preflight(), 'seconds': time.monotonic()-preflight_started})
        transport.preflight()
        for slot in frozen['inputs']['design']['slots']:
            if runtime() != frozen['runtime'] or source_commit() != frozen['source_commit']:
                raise ValueError('Frozen runtime or source changed')
            task = task_map[slot['problem_id']]; path = output / 'dispositions' / (slot['id'] + '.json')
            if slot['phase'] == 'initial':
                verifier.context = {'phase': 'original_public', 'attempt_id': slot['id'], 'task_binding': task_key(task)}
                public = task['public']; stored = ablation.observe(public, verifier); acquisition = None
                save(output / 'original-feedback' / (task_key(task)+'.json'), stored)
            else:
                initial = initials.get(task['problem_id'])
                if initial is None or initial['status'] != 'public_fail':
                    save(path, {'slot': slot, 'status': 'not_triggered',
                                'reason': 'initial_missing' if initial is None else initial['status']})
                    continue
                public, stored = initial['public'], initial['stored']
                if task['problem_id'] not in acquired:
                    verifier.context = {'phase': 'acquisition', 'task_binding': task_key(task)}
                    acquired[task['problem_id']] = ablation.acquire(public, stored, verifier)
                    save(output / 'acquisitions' / (task_key(task)+'.json'), acquired[task['problem_id']])
                acquisition = acquired[task['problem_id']]
            request = request_for(slot, task, public, stored, acquisition)
            save(output / 'requests' / (slot['id']+'.json'), request)
            if request['provider_body'] is None:
                save(path, {'slot': slot, 'status': 'missing_not_sent', 'reason': 'input_admission_bound'})
                continue
            receipt = transport.complete(request['request'], request['metadata'])
            if receipt['generation_id'] in seen:
                raise ProviderStopped('Duplicate generation identity')
            seen.add(receipt['generation_id'])
            verifier.context = {'phase': 'generated_public', 'attempt_id': slot['id'], 'task_binding': task_key(task)}
            cell = {'slot': slot, **checkpoint(public, receipt, verifier)}
            save(output / 'cells' / (slot['id']+'.json'), cell)
            append(output / 'observations.jsonl', {'attempt_id': slot['id'], 'cell_sha256': digest(output / 'cells' / (slot['id']+'.json'))})
            save(path, {'slot': slot, 'status': 'observed', 'cell_sha256': digest(output / 'cells' / (slot['id']+'.json'))})
            if slot['phase'] == 'initial':
                initials[task['problem_id']] = cell
            update_state(frozen, output, active=True, money={
                'known_usd': str(transport.spent), 'pending': transport.pending,
                'cumulative_committed_usd': str(pilot.PRIOR_COMMITMENT+transport.conservative_committed_usd)})
            print(json.dumps({'settled_responses': len(seen), 'study_committed_usd': str(transport.conservative_committed_usd)}), flush=True)
        validate_freeze(frozen, current=True)
    except Exception as exc:
        terminal = {'status': 'interrupted', 'exception_type': type(exc).__name__, 'resume_allowed': False}
    else:
        terminal = {'status': 'completed', 'resume_allowed': False}
    terminal.update(wall_seconds=time.monotonic()-started, known_usd=str(transport.spent),
                    pending={k: str(v) for k, v in transport.pending.items()},
                    study_committed_usd=str(transport.conservative_committed_usd),
                    cumulative_committed_usd=str(pilot.PRIOR_COMMITMENT+transport.conservative_committed_usd))
    save(output / ('completion.json' if terminal['status'] == 'completed' else 'interruption.json'), terminal)
    update_state(frozen, output, active=False, money=terminal)
    return terminal


def accounting(output, frozen):
    """Operational only: receipts, IDs, prompt binding and money; no treatment means."""
    slots = frozen['inputs']['design']['slots']; schedule = {s['id']: s for s in slots}
    positions = {s['id']: i for i, s in enumerate(slots)}
    order, settled, pending, identities = [], {}, {}, set()
    for event in rows(output / 'ledger.jsonl'):
        k, amount = event['attempt_id'], dollars(event['usd'])
        if k not in schedule or event['currency'] != 'USD':
            raise ValueError('Unknown ledger identity/currency')
        if event['event'] == 'reserve':
            if pending or k in settled or amount != SETTINGS.reserve or (order and positions[k] <= positions[order[-1]]):
                raise ValueError('Repeated/out-of-order admission or changed reservation')
            request = read(output / 'requests' / (k+'.json'))
            if (request['slot'] != schedule[k] or request['metadata']['attempt_id'] != k
                    or request['provider_body'] != SETTINGS.body(request['request'], request['metadata'])
                    or read(output / 'requests' / (k+'.provider.json')) != request['provider_body']):
                raise ValueError('Actual provider request differs from durable request')
            order.append(k); pending[k] = amount
        elif event['event'] == 'settle':
            if k not in pending or amount > pending[k]:
                raise ValueError('Unreserved or excessive settlement')
            raw, receipt = read(output / 'receipts' / (k+'.raw.json')), read(output / 'receipts' / (k+'.json'))
            metrics = read(output / 'stream-metrics' / (k+'.json'))
            if (not metrics['stream_complete'] or not metrics['done_received'] or not metrics['usage_received']
                    or not raw.get('reconstructed_from_sse') or raw['model'] != SETTINGS.model
                    or raw['provider'] != SETTINGS.provider_name or raw['id'] in identities
                    or receipt['generation_id'] != raw['id'] or receipt['attempt_id'] != k
                    or receipt['model'] != raw['model'] or receipt['provider'] != raw['provider']
                    or receipt['usage'] != raw['usage'] or len(raw['choices']) != 1
                    or receipt['content'] != raw['choices'][0]['message']['content']
                    or receipt['finish_reason'] != raw['choices'][0]['finish_reason']
                    or dollars(raw['usage']['cost']) != amount or dollars(receipt['cost_usd']) != amount
                    or dollars(metrics['reported_cost_usd']) != amount):
                raise ValueError('Raw/normalized receipt, stream or settlement mismatch')
            usage = receipt['usage']
            for field, ceiling in [('prompt_tokens', SETTINGS.input_token_ceiling), ('completion_tokens', SETTINGS.max_tokens)]:
                if type(usage[field]) is not int or not 0 <= usage[field] <= ceiling:
                    raise ValueError('Usage exceeds reservation')
            if type(usage['total_tokens']) is not int or usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']:
                raise ValueError('Token total mismatch')
            identities.add(raw['id']); settled[k] = amount; del pending[k]
        else:
            raise ValueError('Unknown ledger event')
    for k in pending:
        for path, extract in [(output / 'stream-metrics' / (k+'.json'), lambda x: x.get('reported_cost_usd', '0')),
                              (output / 'receipts' / (k+'.raw.json'), lambda x: x.get('usage', {}).get('cost', '0'))]:
            if path.exists():
                pending[k] = max(pending[k], dollars(extract(read(path))))
    dispatches = []
    for k in order:
        p = output / 'dispatch' / (k+'.json')
        if not p.exists():
            if k in settled:
                raise ValueError('Settled request has no admission-time evidence')
            continue
        d = read(p)
        if (d['attempt_id'] != k or d['body_sha256'] != identity(read(output / 'requests' / (k+'.provider.json')))
                or type(d['monotonic_admission']) not in (int, float) or not 0 <= d['monotonic_admission'] < float('inf')
                or dispatches and d['monotonic_admission'] - dispatches[-1]['monotonic_admission'] < 60-1e-6):
            raise ValueError('Provider dispatch identity or pacing differs')
        dispatches.append(d)
    known = sum(settled.values(), Decimal(0)); commitment = known + sum(pending.values(), Decimal(0))
    return {'admitted': len(order), 'settled': len(settled), 'admitted_attempts': order, 'settled_attempts': list(settled),
            'pending': {k: str(v) for k, v in pending.items()}, 'known_usd': str(known),
            'dispatch_timestamps': len(dispatches), 'unrecorded_pending_dispatches': len(order)-len(dispatches),
            'study_committed_usd': str(commitment), 'cumulative_committed_usd': str(pilot.PRIOR_COMMITMENT+commitment),
            'cap_exceeded': commitment > pilot.PROPOSED_ALLOCATION or pilot.PRIOR_COMMITMENT+commitment > pilot.CUMULATIVE_CAP}


def validate_cell(cell, receipt, public, slot):
    if cell['slot'] != slot or cell['artifact'] != pilot.parse_artifact(receipt['content']):
        raise ValueError('Saved cell differs from actual received artifact')
    if cell['artifact'] is None:
        if cell['status'] != 'invalid' or cell['public'] is not None or cell['stored'] is not None:
            raise ValueError('Invalid response replaced by invented state')
    else:
        expected = {**copy.deepcopy(public), 'files': cell['artifact']}
        if cell['public'] != expected:
            raise ValueError('Changed statement/cases or incorrect generated checkpoint')
        passed = ablation.current_feedback(expected, cell['stored'])['passed']
        if cell['status'] != ('public_pass' if passed else 'public_fail'):
            raise ValueError('Incorrect public stopping decision')
    if type(cell['parse_seconds']) not in (int, float) or not 0 <= cell['parse_seconds'] < float('inf'):
        raise ValueError('Invalid parser cost')


def audit_collection(output):
    frozen = read(output / 'manifest.json')['freeze']; validate_freeze(frozen)
    terminals = [p for p in (output / 'completion.json', output / 'interruption.json') if p.exists()]
    if len(terminals) != 1:
        raise ValueError('A unique model-collection terminal record is required')
    terminal = read(terminals[0]); money = accounting(output, frozen)
    if money['admitted']:
        preflight = read(output / 'provider-preflight.json')
        if (preflight['settings'] != asdict(SETTINGS) or preflight['credit_covers_declared_cap'] is not True
                or dollars(preflight['cap_usd']) != pilot.PROPOSED_ALLOCATION
                or preflight['minimum_interval_seconds'] != 60 or dollars(preflight['reservation_usd']) != SETTINGS.reserve):
            raise ValueError('Provider preflight differs from declared funding/settings')
    if terminal['status'] not in {'completed', 'interrupted'} or terminal['resume_allowed'] is not False:
        raise ValueError('Invalid terminal state')
    if any(terminal[k] != money[k] for k in ('known_usd', 'study_committed_usd', 'cumulative_committed_usd')):
        raise ValueError('Terminal accounting differs')
    task_map = {t['problem_id']: t for t in frozen['inputs']['tasks']}
    initials, cells, checked, eligible_ids, local_incomplete = {}, {}, set(), set(), []
    original_count = diagnostic_count = public_count = 0
    original_seconds = diagnostic_seconds = public_seconds = projection_seconds = parse_seconds = 0.0
    for slot in frozen['inputs']['design']['slots']:
        task = task_map[slot['problem_id']]; k = slot['id']
        request_path, disposition_path, cell_path = (output / d / (k+'.json') for d in ('requests', 'dispositions', 'cells'))
        disposition = read(disposition_path) if disposition_path.exists() else None
        if disposition is not None and disposition['slot'] != slot:
            raise ValueError('Disposition changed the frozen slot')
        if slot['phase'] == 'initial':
            public = task['public']; acquisition = None
            path = output / 'original-feedback' / (task_key(task)+'.json')
            if not path.exists():
                if request_path.exists() or cell_path.exists() or disposition is not None:
                    raise ValueError('Initial request lacks its original public observations')
                continue
            stored = read(path); ablation.current_feedback(public, stored)
            original_count += stored['candidate_executions']; original_seconds += stored['seconds']
        else:
            initial = initials.get(task['problem_id'])
            if initial is None or initial['status'] != 'public_fail':
                if request_path.exists() or cell_path.exists() or k in money['admitted_attempts']:
                    raise ValueError('Recovery triggered without a generated public failure')
                if disposition is not None and disposition != {'slot': slot, 'status': 'not_triggered',
                        'reason': 'initial_missing' if initial is None else initial['status']}:
                    raise ValueError('Invalid skip reason')
                if terminal['status'] == 'completed' and disposition is None:
                    raise ValueError('Completed bank lost a nontriggered slot')
                continue
            eligible_ids.add(task_key(task)); public, stored = initial['public'], initial['stored']
            path = output / 'acquisitions' / (task_key(task)+'.json')
            if not path.exists():
                if request_path.exists() or cell_path.exists() or disposition is not None:
                    raise ValueError('Recovery request lacks acquired snapshot')
                continue
            acquisition = read(path); ablation.analyze(public, stored, acquisition)
            if task_key(task) not in checked:
                diagnostic_count += acquisition['candidate_executions']; diagnostic_seconds += acquisition['seconds']
                checked.add(task_key(task))
        if request_path.exists():
            request = read(request_path); expected = request_for(slot, task, public, stored, acquisition)
            if {k:v for k,v in request.items() if k != 'projection_seconds'} != {k:v for k,v in expected.items() if k != 'projection_seconds'}:
                raise ValueError('Saved request is not the exact public-only projection')
            if type(request['projection_seconds']) not in (int, float) or not 0 <= request['projection_seconds'] < float('inf'):
                raise ValueError('Invalid projection cost')
            projection_seconds += request['projection_seconds']
            if request['provider_body'] is None:
                if k in money['admitted_attempts'] or cell_path.exists() or disposition != {'slot': slot, 'status': 'missing_not_sent', 'reason': 'input_admission_bound'}:
                    raise ValueError('Rejected prompt admitted or imputed')
                continue
        elif k in money['admitted_attempts'] or cell_path.exists() or disposition is not None:
            raise ValueError('Observation/admission without durable request')
        if cell_path.exists():
            if k not in money['settled_attempts']:
                raise ValueError('Unsettled receipt turned into an outcome')
            cell = read(cell_path); validate_cell(cell, read(output / 'receipts' / (k+'.json')), public, slot)
            expected = {'slot': slot, 'status': 'observed', 'cell_sha256': digest(cell_path)}
            if disposition != expected:
                if disposition is not None or terminal['status'] == 'completed':
                    raise ValueError('Observed cell/disposition differs')
                local_incomplete.append({'attempt_id': k, 'phase': 'disposition_not_recorded'})
            cells[k] = cell; parse_seconds += cell['parse_seconds']
            if cell['stored']:
                public_count += cell['stored']['candidate_executions']; public_seconds += cell['stored']['seconds']
            if slot['phase'] == 'initial':
                initials[task['problem_id']] = cell
        elif terminal['status'] == 'completed' and request_path.exists():
            raise ValueError('Completed bank lacks an expected outcome')
    slots = {s['id'] for s in frozen['inputs']['design']['slots']}
    for folder in ('requests', 'receipts', 'cells', 'dispositions', 'stream-metrics', 'dispatch'):
        if (output / folder).exists():
            for path in (output / folder).iterdir():
                k = path.name.split('.')[0]
                suffixes = {'requests': ['.json', '.provider.json'], 'receipts': ['.json', '.raw.json'],
                            'cells': ['.json'], 'dispositions': ['.json'], 'stream-metrics': ['.json'], 'dispatch': ['.json']}[folder]
                if k not in slots or path.name not in {k+s for s in suffixes}:
                    raise ValueError('Unknown artifact outside frozen slots')
                if (folder in {'receipts', 'stream-metrics', 'dispatch'} or path.name.endswith('.provider.json')) and k not in money['admitted_attempts']:
                    raise ValueError('Provider artifact without an admitted request')
    if any(p.stem not in eligible_ids for p in (output / 'acquisitions').iterdir()):
        raise ValueError('Acquisition from a private or non-failure trigger')
    expected_journal = [{'attempt_id': k, 'cell_sha256': digest(output / 'cells' / (k+'.json'))} for k in cells]
    actual_journal = rows(output / 'observations.jsonl')
    if (actual_journal != expected_journal and (terminal['status'] == 'completed'
            or actual_journal != expected_journal[:len(actual_journal)])):
        raise ValueError('Observation journal dropped/duplicated/reordered cells')
    if actual_journal != expected_journal:
        local_incomplete.append({'phase': 'observation_journal_incomplete', 'records': len(expected_journal)-len(actual_journal)})
    if terminal['status'] == 'completed' and (money['pending'] or len(list((output / 'dispositions').iterdir())) != 110):
        raise ValueError('Completed bank lacks a full disposition panel')
    journal = audit_executions(output, frozen)
    return {'frozen': frozen, 'terminal': terminal, 'accounting': money, 'cells': cells,
            'local_incomplete_phases': local_incomplete, 'execution_journal': journal,
            'resources': {'original_public_executions': original_count, 'original_public_seconds': original_seconds,
                          'acquisition_executions': diagnostic_count, 'acquisition_seconds': diagnostic_seconds,
                          'generated_public_executions': public_count, 'generated_public_seconds': public_seconds,
                          'projection_seconds': projection_seconds, 'parse_seconds': parse_seconds}}


def audit_executions(output, frozen, *, allowed_phases=None):
    pending, finished, failed = {}, [], []
    preflight = []
    last = 0
    tasks = {t['binding'] for t in frozen['inputs']['tasks']}
    slots = {s['id'] for s in frozen['inputs']['design']['slots']}
    allowed_phases = allowed_phases or {'original_public', 'generated_public', 'acquisition'}
    for row in rows(output / 'execution-journal.jsonl'):
        if row['event'].startswith('preflight_'):
            preflight.append(row)
            continue
        seq = row['sequence']
        if row['event'] == 'start':
            c = row['context']
            if (pending or seq != last+1 or c['task_binding'] not in tasks
                    or c['phase'] not in allowed_phases
                    or (c['phase'] != 'acquisition' and c.get('attempt_id') not in slots)):
                raise ValueError('Invalid execution inventory or context')
            pending[seq] = row; last = seq
        elif row['event'] in {'finish', 'error'}:
            if seq not in pending or not 0 <= row['seconds'] < float('inf'):
                raise ValueError('Invalid execution completion or duration')
            start = pending.pop(seq)
            if row['event'] == 'finish':
                ablation.execution(row['result'], covered=start['coverage'])
                finished.append({'start': start, 'finish': row})
            else:
                failed.append({'start': start, 'finish': row})
        else:
            raise ValueError('Unknown execution event')
    return {'started': last, 'finished': len(finished), 'failed': len(failed), 'unresolved': len(pending),
            'completed_candidate_executions': sum(r['finish']['result']['candidate_executions'] for r in finished),
            'recorded_seconds': sum(r['finish']['seconds'] for r in finished+failed),
            'unknown_execution_counts': len(failed)+len(pending), 'preflight': preflight,
            'executions': finished, 'errors': failed, 'pending': list(pending.values())}
