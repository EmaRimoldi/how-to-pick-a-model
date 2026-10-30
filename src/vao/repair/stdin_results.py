"""Terminal private verification, reproducible analysis and inert evidence export."""
from __future__ import annotations

import base64
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
import zipfile
from decimal import Decimal
import tempfile
from pathlib import PurePosixPath

from . import stdin_ablation as ablation
from . import stdin_collection as collection
from . import stdin_pilot as pilot
from .environment import canonical, identity
from .records import save
from .stdin_monitoring import MonitoringStdinVerifier
from .stdin_verifier import compare_stdout


def inventory(root):
    return {str(p.relative_to(root)): collection.digest(p) for p in sorted(root.rglob('*')) if p.is_file()}


def verify(model, output):
    audit = collection.audit_collection(model); frozen = audit['frozen']
    collection.validate_freeze(frozen, current=True)
    if output.exists():
        raise ValueError('Never overwrite a terminal verification')
    output.mkdir(); (output / 'cells').mkdir()
    save(output / 'manifest.json', {'freeze_id': frozen['freeze_id'], 'model_inventory': inventory(model),
                                    'runtime': collection.runtime(), 'new_model_calls': 0})
    verifier = collection.JournalVerifier(MonitoringStdinVerifier(5), output)
    tasks = {t['problem_id']: t for t in frozen['inputs']['tasks']}
    start = time.monotonic()
    try:
        save(output / 'preflight.json', verifier.preflight())
        for slot in frozen['inputs']['design']['slots']:
            k = slot['id']
            if k not in audit['accounting']['settled_attempts']:
                continue
            task = tasks[slot['problem_id']]
            receipt = collection.read(model / 'receipts' / (k+'.json'))
            artifact = pilot.parse_artifact(receipt['content'])
            result = {'slot': slot, 'artifact': artifact, 'public': None, 'private': None,
                      'public_matches_collected': None, 'full_repair': False}
            if artifact is not None:
                public = {**task['public'], 'files': artifact}
                verifier.context = {'phase': 'terminal_public', 'attempt_id': k, 'task_binding': task['binding']}
                stored = ablation.observe(public, verifier)
                result['public'] = stored
                old = audit['cells'].get(k)
                if old is not None:
                    result['public_matches_collected'] = all(
                        ablation.observable_key(a['execution']['observed']) == ablation.observable_key(b['execution']['observed'])
                        for a, b in zip(stored['cases'], old['stored']['cases'], strict=True))
                verifier.context = {'phase': 'terminal_private', 'attempt_id': k, 'task_binding': task['binding']}
                private = []
                for case in task['private_cases']:
                    execution = verifier.invoke(artifact['main.py'].encode(), base64.b64decode(case['input_b64'], validate=True))
                    private.append({'id': case['id'], 'execution': execution,
                        'passed': compare_stdout(execution['observed'], base64.b64decode(case['expected_b64'], validate=True),
                                                 mode=task['public']['comparator'])})
                result['private'] = private
                result['full_repair'] = ablation.current_feedback(public, stored)['passed'] and all(c['passed'] for c in private)
                if old is not None:
                    result['full_repair'] = result['full_repair'] and old['status'] == 'public_pass'
            save(output / 'cells' / (k+'.json'), result)
        if inventory(model) != collection.read(output / 'manifest.json')['model_inventory']:
            raise ValueError('Model bank changed during terminal verification')
    except Exception as exc:
        save(output / 'interruption.json', {'exception_type': type(exc).__name__, 'seconds': time.monotonic()-start, 'new_model_calls': 0})
        raise
    save(output / 'completion.json', {'verified_settled_receipts': len(audit['accounting']['settled_attempts']),
                                     'seconds': time.monotonic()-start, 'new_model_calls': 0})
    return {'verified_settled_receipts': len(audit['accounting']['settled_attempts']), 'new_model_calls': 0}


def execution_key(source, stdin, covered, execution, context):
    return canonical({'source_sha256': hashlib.sha256(source).hexdigest(),
                      'input_sha256': hashlib.sha256(stdin).hexdigest(), 'coverage': covered,
                      'result': execution, 'context': context})


def check_journal(journal, expected, *, complete):
    actual = Counter(canonical({k: row['start'][k] for k in ('source_sha256', 'input_sha256', 'coverage', 'context')}
                              | {'result': row['finish']['result']}) for row in journal['executions'])
    if expected - actual or (complete and (actual != expected or journal['unknown_execution_counts'])):
        raise ValueError('Saved executions do not match durable execution journal')
    return sum((actual - expected).values())


def collected_execution_inventory(audit, model):
    expected = Counter(); frozen = audit['frozen']
    tasks = {t['problem_id']: t for t in frozen['inputs']['tasks']}
    initial_slots = {s['problem_id']: s for s in frozen['inputs']['design']['slots'] if s['phase'] == 'initial'}
    for task in tasks.values():
        k = initial_slots[task['problem_id']]['id']
        p = model / 'original-feedback' / (task['binding']+'.json')
        if p.exists():
            stored = collection.read(p)
            context = {'phase': 'original_public', 'attempt_id': k, 'task_binding': task['binding']}
            for case, row in zip(task['public']['public_cases'], stored['cases'], strict=True):
                expected[execution_key(task['public']['files']['main.py'].encode(), case['stdin'].encode(), False, row['execution'], context)] += 1
        p = model / 'acquisitions' / (task['binding']+'.json')
        if p.exists():
            checkpoint = audit['cells'][k]
            acquisition = collection.read(p)
            context = {'phase': 'acquisition', 'task_binding': task['binding']}
            for case, row in zip(checkpoint['public']['public_cases'], acquisition['cases'], strict=True):
                for covered, name in [(False, 'ordinary'), (True, 'covered')]:
                    expected[execution_key(checkpoint['artifact']['main.py'].encode(), case['stdin'].encode(), covered, row[name], context)] += 1
    for k, cell in audit['cells'].items():
        if cell['stored'] is None:
            continue
        task = tasks[cell['slot']['problem_id']]
        context = {'phase': 'generated_public', 'attempt_id': k, 'task_binding': task['binding']}
        for case, row in zip(cell['public']['public_cases'], cell['stored']['cases'], strict=True):
            expected[execution_key(cell['artifact']['main.py'].encode(), case['stdin'].encode(), False, row['execution'], context)] += 1
    return expected


def analyze(model, verification):
    audit = collection.audit_collection(model); frozen = audit['frozen']
    manifest = collection.read(verification / 'manifest.json')
    if (manifest['model_inventory'] != inventory(model) or manifest['freeze_id'] != frozen['freeze_id']
            or manifest['runtime'] != frozen['runtime'] or manifest['new_model_calls'] != 0):
        raise ValueError('Terminal verification source/runtime differs')
    complete_verification = (verification / 'completion.json').exists() and not (verification / 'interruption.json').exists()
    tasks = {t['problem_id']: t for t in frozen['inputs']['tasks']}
    expected, outcomes, observations, mismatches = Counter(), {}, {}, []
    regressions = {a: 0 for a in ablation.ARMS}; false_acceptances = {a: 0 for a in ablation.ARMS}
    invalid = {a: 0 for a in ablation.ARMS}
    for slot in frozen['inputs']['design']['slots']:
        k = slot['id']; task = tasks[slot['problem_id']]
        p = verification / 'cells' / (k+'.json')
        if not p.exists():
            continue
        if k not in audit['accounting']['settled_attempts']:
            raise ValueError('Private verification of an unsettled response')
        result = collection.read(p); artifact = pilot.parse_artifact(collection.read(model / 'receipts' / (k+'.json'))['content'])
        if result['slot'] != slot or result['artifact'] != artifact:
            raise ValueError('Private evaluation changed the received source')
        if artifact is None:
            if result['public'] is not None or result['private'] is not None or result['full_repair'] is not False:
                raise ValueError('Invalid response became a solution')
            outcome = False
            if slot['phase'] == 'recovery':
                invalid[slot['arm']] += 1
        else:
            public = {**task['public'], 'files': artifact}
            feedback = ablation.current_feedback(public, result['public'])
            if len(result['private']) != len(task['private_cases']):
                raise ValueError('Private case inventory changed')
            for case, row in zip(public['public_cases'], result['public']['cases'], strict=True):
                context = {'phase': 'terminal_public', 'attempt_id': k, 'task_binding': task['binding']}
                expected[execution_key(artifact['main.py'].encode(), case['stdin'].encode(), False, row['execution'], context)] += 1
            for case, row in zip(task['private_cases'], result['private'], strict=True):
                ablation.execution(row['execution'])
                score = compare_stdout(row['execution']['observed'], base64.b64decode(case['expected_b64'], validate=True), mode=public['comparator'])
                if row['id'] != case['id'] or row['passed'] is not score:
                    raise ValueError('Forged private test score')
                context = {'phase': 'terminal_private', 'attempt_id': k, 'task_binding': task['binding']}
                expected[execution_key(artifact['main.py'].encode(), base64.b64decode(case['input_b64'], validate=True), False, row['execution'], context)] += 1
            outcome = feedback['passed'] and all(c['passed'] for c in result['private'])
            old = audit['cells'].get(k)
            if old is not None:
                outcome = outcome and old['status'] == 'public_pass'
            agreement = None if old is None else all(
                ablation.observable_key(a['execution']['observed']) == ablation.observable_key(b['execution']['observed'])
                for a, b in zip(result['public']['cases'], old['stored']['cases'], strict=True))
            if agreement != result['public_matches_collected']:
                raise ValueError('Forged public replay agreement flag')
            if agreement is False:
                mismatches.append(k)
            observations[k] = feedback
            if slot['phase'] == 'recovery':
                initial_slot = next(s for s in frozen['inputs']['design']['slots'] if s['phase'] == 'initial' and s['problem_id'] == slot['problem_id'])
                before = audit['cells'].get(initial_slot['id'])
                if before is not None:
                    old_feedback = ablation.current_feedback(before['public'], before['stored'])
                    regressions[slot['arm']] += any(a['passed'] and not b['passed'] for a, b in zip(old_feedback['cases'], feedback['cases'], strict=True))
                false_acceptances[slot['arm']] += feedback['passed'] and not outcome
        if result['full_repair'] is not outcome:
            raise ValueError('Full-repair outcome differs from raw observations')
        outcomes[k] = outcome
    files = list((verification / 'cells').glob('*.json'))
    if len(files) != len(outcomes) or (complete_verification and set(outcomes) != set(audit['accounting']['settled_attempts'])):
        raise ValueError('Verification lost or invented settled outcomes')
    collection_extras = check_journal(audit['execution_journal'], collected_execution_inventory(audit, model), complete=audit['terminal']['status'] == 'completed')
    journal = collection.audit_executions(verification, frozen, allowed_phases={'terminal_public', 'terminal_private'})
    verification_extras = check_journal(journal, expected, complete=complete_verification)
    panel = []
    for task in frozen['inputs']['tasks']:
        initial = next(s for s in frozen['inputs']['design']['slots'] if s['phase'] == 'initial' and s['problem_id'] == task['problem_id'])
        k = initial['id']
        if k not in outcomes:
            initial_result = {'status': 'missing', 'full_repair': None}
        elif k not in observations:
            initial_result = {'status': 'invalid', 'full_repair': False}
        else:
            original = audit['cells'].get(k)
            status = original['status'] if original is not None else 'public_pass' if observations[k]['passed'] else 'public_fail'
            initial_result = {'status': status, 'full_repair': outcomes[k]}
        recovery = {a: [None]*3 for a in ablation.ARMS}
        if initial_result['status'] == 'public_fail':
            for slot in frozen['inputs']['design']['slots']:
                if slot['phase'] == 'recovery' and slot['problem_id'] == task['problem_id']:
                    recovery[slot['arm']][slot['draw']] = outcomes.get(slot['id'])
        panel.append({'problem_id': task['problem_id'], 'initial': initial_result, 'recovery': recovery})
    evidence_ok = (complete_verification and not mismatches and not audit['local_incomplete_phases']
                   and audit['terminal']['status'] == 'completed' and not audit['accounting']['cap_exceeded'])
    scientific = pilot.analyze(frozen['inputs']['design']['roster'], panel, evidence_audited=evidence_ok)
    return {'study': collection.STUDY, 'freeze_id': frozen['freeze_id'], 'analysis': scientific,
            'panel': panel, 'regressions': regressions, 'false_acceptances': false_acceptances,
            'invalid_recovery_outputs': invalid, 'public_replay_mismatches': mismatches,
            'accounting': audit['accounting'], 'collection_resources': audit['resources'],
            'collection_execution_journal': {k:v for k,v in audit['execution_journal'].items() if k not in {'executions', 'errors', 'pending'}},
            'verification_execution_journal': {k:v for k,v in journal.items() if k not in {'executions', 'errors', 'pending'}},
            'unmaterialized_collection_executions_retained': collection_extras,
            'unmaterialized_verification_executions_retained': verification_extras,
            'model_terminal': audit['terminal'], 'verification_complete': complete_verification,
            'policy_resource_paths': policy_resources(audit, model, panel),
            'new_model_calls_by_analysis': 0, 'selector_training_allowed': False,
            'limits': ['Inspected development submissions, at most eleven problem groups; not independent evaluation.',
                       'Three draws do not create three independent bugs.',
                       'Equal generation allowances are not equal realized or total resources.',
                       'All acquisition work is retained; sharing a snapshot across research draws is not a deployment discount.',
                       'No exact Gemma tokenizer capacity guarantee; all admission rejections remain missing.']}


def policy_resources(audit, model, panel):
    """Count shared initial work and the full acquisition once for each policy path."""
    slots = audit['frozen']['inputs']['design']['slots']
    task_map = {t['problem_id']: t for t in audit['frozen']['inputs']['tasks']}
    flow = {r['problem_id']: r for r in panel}
    result = []
    for arm in ablation.ARMS:
        for draw in range(3):
            selected = [s for s in slots if s['phase'] == 'initial' or s['arm'] == arm and s['draw'] == draw]
            known, reserved, unresolved = Decimal(0), Decimal(0), []
            public_executions = audit['resources']['original_public_executions']
            public_seconds = audit['resources']['original_public_seconds']
            acquisition_executions, acquisition_seconds, projection_seconds, parse_seconds = 0, 0.0, 0.0, 0.0
            latency, prompt_tokens, completion_tokens = 0.0, 0, 0
            for slot in selected:
                k = slot['id']
                if k in audit['accounting']['settled_attempts']:
                    receipt = collection.read(model / 'receipts' / (k+'.json'))
                    known += collection.dollars(receipt['cost_usd'])
                    latency += receipt['elapsed_seconds']
                    prompt_tokens += receipt['usage']['prompt_tokens']; completion_tokens += receipt['usage']['completion_tokens']
                elif k in audit['accounting']['pending']:
                    reserved += collection.dollars(audit['accounting']['pending'][k]); unresolved.append(k)
                elif slot['phase'] == 'initial' or flow[slot['problem_id']]['initial']['status'] in {'missing', 'public_fail'}:
                    unresolved.append(k)
                cell = audit['cells'].get(k)
                if cell is not None:
                    parse_seconds += cell['parse_seconds']
                    if cell['stored'] is not None:
                        public_executions += cell['stored']['candidate_executions']; public_seconds += cell['stored']['seconds']
                p = model / 'requests' / (k+'.json')
                if p.exists():
                    projection_seconds += collection.read(p)['projection_seconds']
            if arm != 'feedback':
                for task in task_map.values():
                    p = model / 'acquisitions' / (task['binding']+'.json')
                    if p.exists():
                        acquisition = collection.read(p)
                        acquisition_executions += acquisition['candidate_executions']
                        acquisition_seconds += acquisition['seconds']
            result.append({'arm': arm, 'draw': draw, 'known_api_usd': str(known),
                'uncertain_api_reserve_usd': str(reserved), 'unresolved_opportunities': unresolved,
                'known_provider_seconds': latency, 'known_prompt_tokens': prompt_tokens, 'known_completion_tokens': completion_tokens,
                'recorded_public_executions': public_executions, 'recorded_public_seconds': public_seconds,
                'recorded_acquisition_executions': acquisition_executions, 'recorded_acquisition_seconds': acquisition_seconds,
                'recorded_projection_seconds': projection_seconds, 'recorded_parse_seconds': parse_seconds,
                'acquisition_divided_by_draws': False, 'research_private_verification_excluded_from_deployed_feedback': True,
                'partial_phase_costs_reported_in_collection_journal_not_imputed': True})
    return result


def render(report):
    a, money = report['analysis'], report['accounting']
    lines = ['# Whole-program diagnostic pilot', '', f"Criterion: **{a['gate']}**.", '',
             f"Eleven selected development groups; {a['known_eligible_generated_checkpoints']} known generated public-failure checkpoints.",
             'Three draws are repeated samples within a checkpoint, not independent bugs.', '',
             f"Initial flow: `{json.dumps(a['initial_flow'], sort_keys=True)}`.", '',
             '| Condition | Conditional full-repair rate |', '| --- | ---: |']
    for arm in ablation.ARMS:
        value = ('not estimable: no materializable generated failures'
                 if a['known_outcomes_complete'] and a['known_eligible_generated_checkpoints'] == 0
                 else 'not reported: incomplete/unaudited bank') if a['conditional_means'] is None else f"{100*a['conditional_means'][arm]:.2f}%"
        lines.append(f'| {arm} | {value} |')
    lines += ['', f"Primary S−N: `{None if a['conditional_contrasts'] is None else a['conditional_contrasts']['scored_minus_neutral']}`.",
              f"Safety S−F: `{None if a['conditional_contrasts'] is None else a['conditional_contrasts']['scored_minus_feedback']}`.",
              f"Repeatability: `{json.dumps(a['repeatability'], sort_keys=True)}`.", '',
              'Finite completion bounds on the selected eleven-group end-to-end panel (not confidence intervals):',
              f"`{json.dumps(a['end_to_end_selected_bounds'], sort_keys=True)}`", '',
              f"Known API spend: ${money['known_usd']}; study commitment including uncertain reserves: ${money['study_committed_usd']} / $0.32.",
              f"Cumulative commitment including fourteen prior unresolved reserves: ${money['cumulative_committed_usd']} / $0.60.", '',
              f"Public regressions: `{json.dumps(report['regressions'], sort_keys=True)}`.",
              f"Public false acceptances: `{json.dumps(report['false_acceptances'], sort_keys=True)}`.",
              f"Invalid recovery output: `{json.dumps(report['invalid_recovery_outputs'], sort_keys=True)}`.",
              f"Public replay discrepancies: {len(report['public_replay_mismatches'])}.", '',
              'All known, missing, rejected, untriggered and interrupted opportunities remain in the panel.',
              'Private tests never triggered a provider request. Independent verification and all partial execution work are recorded separately.',
              'Per-policy resource paths include shared initial work and full acquisition costs; acquisition is never divided by the number of research draws.',
              'API dollars, local execution counts/time and provider latency are separate quantities, not a fabricated common resource budget.', '',
              *['- '+s for s in report['limits']], '',
              'A passed criterion permits only independent replication planning. **No selector training is enabled.**', '']
    return '\n'.join(lines)


def figure(report, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a = report['analysis']; fig, ax = plt.subplots(figsize=(7.5, 4.4))
    if a['conditional_means'] is not None:
        values = [100*a['conditional_means'][arm] for arm in ablation.ARMS]
        bars = ax.bar(['Feedback', 'Neutral excerpts', 'Scored excerpts'], values, color=['#64748b', '#38bdf8', '#0f766e'])
        ax.bar_label(bars, labels=[f'{v:.1f}%' for v in values], padding=4)
        ax.set_ylim(0, 110); ax.set_ylabel('Full repairs (%)')
        ax.set_title(f"{a['known_eligible_generated_checkpoints']} generated failure checkpoints; three draws")
    else:
        labels = ['S − N', 'S − F']
        for i, key in enumerate(('scored_minus_neutral', 'scored_minus_feedback')):
            lo, hi = [100*v for v in a['end_to_end_selected_bounds'][key]]
            ax.plot([lo, hi], [i, i], color='#64748b', linewidth=4)
            ax.scatter([lo, hi], [i, i], color='#64748b', s=35)
        ax.set_yticks([0, 1], labels); ax.set_xlim(-105, 105)
        ax.axvline(0, color='black', linewidth=.7)
        ax.set_xlabel('Selected-panel completion bounds (percentage points)')
        ax.set_title('No conditional effect estimate: '+a['gate'].replace('_', ' '))
    fig.text(.5, .025, 'Development pilot • '+a['gate'].replace('_', ' ')+' • not an independent policy test', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .07, 1, 1)); fig.savefig(output, dpi=170); plt.close(fig)


def publish(model, verification, output):
    report = analyze(model, verification)
    if output.exists():
        raise ValueError('Never overwrite a published study')
    frozen = collection.read(model / 'manifest.json')['freeze']
    blobs = {}
    for label, root in [('collection', model), ('verification', verification)]:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                blobs[label+'/'+str(path.relative_to(root))] = path.read_bytes()
    for name, digest in frozen['runtime']['files'].items():
        path = collection.ROOT / name
        if collection.digest(path) != digest:
            raise ValueError('Frozen implementation is unavailable for export')
        blobs['implementation/'+name+'.txt'] = path.read_bytes()
    dependencies = [collection.BANK/'evidence.zip', collection.BANK/'manifest.json', collection.BANK/'pilot-design.json',
                    collection.BASE/'results/fixeval-source-qualification-20261030/evidence.zip']
    for name in dependencies:
        blobs['dependencies/'+str(name)] = (collection.ROOT/name).read_bytes()
    output.mkdir()
    with zipfile.ZipFile(output/'evidence.zip', 'x', zipfile.ZIP_DEFLATED) as z:
        for name, raw in sorted(blobs.items()):
            z.writestr(name, raw)
    save(output/'evidence-manifest.json', {'archive_sha256': collection.digest(output/'evidence.zip'),
        'members': {n: hashlib.sha256(b).hexdigest() for n,b in sorted(blobs.items())}})
    save(output/'analysis.json', report)
    (output/'REPORT.md').write_text(render(report))
    figure(report, output/'results.png')
    (output/'reproduce.py').write_text('''"""Audit saved JSON evidence; no candidate execution or model call."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / 'src'))
from vao.repair.stdin_results import reproduce
if __name__ == '__main__':
    print(reproduce(HERE))
''')
    (output/'README.md').write_text('''# Generated-failure stdin pilot evidence

See [REPORT.md](REPORT.md), [analysis.json](analysis.json) and [results.png](results.png).
All eleven selected groups and twelve original source decisions remain in the frozen manifest.
This is a development information-value pilot, not independent policy validation.

Run `uv run python` followed by this directory's `reproduce.py` from the repository
root. It checks archive hashes, raw/normalized receipts and costs, public-only
request projections, dynamic stopping, source/test identities, both execution
journals, the complete analysis and exact Markdown report. It executes neither
candidate code nor archived implementation and makes no network/model calls.

The archive contains collection/ and verification/ JSON data, dependency records,
and the exact frozen implementation as inert .txt files. Explicit native replay
requires the frozen runtime and sandbox; it is separate from this default audit.
The retrospective private evaluation never enabled another model attempt.
''')
    return {'output': str(output), 'gate': report['analysis']['gate'], 'new_model_calls': 0}


def reproduce(artifact):
    manifest = collection.read(artifact/'evidence-manifest.json')
    if collection.digest(artifact/'evidence.zip') != manifest['archive_sha256']:
        raise ValueError('Published archive changed')
    with zipfile.ZipFile(artifact/'evidence.zip') as z:
        if sorted(z.namelist()) != sorted(manifest['members']):
            raise ValueError('Published member inventory changed')
        blobs = {n: z.read(n) for n in z.namelist()}
    for n,b in blobs.items():
        if n.startswith('/') or '..' in PurePosixPath(n).parts or hashlib.sha256(b).hexdigest() != manifest['members'][n]:
            raise ValueError('Invalid evidence member')
    frozen = json.loads(blobs['collection/manifest.json'])['freeze']
    for n,h in frozen['runtime']['files'].items():
        if hashlib.sha256(blobs['implementation/'+n+'.txt']).hexdigest() != h:
            raise ValueError('Frozen implementation bytes differ')
    with tempfile.TemporaryDirectory(prefix='inert-stdin-evidence-') as temporary:
        root = Path(temporary)
        for n,b in blobs.items():
            if n.startswith(('collection/', 'verification/')):
                p = root/n; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
        report = analyze(root/'collection', root/'verification')
    if report != collection.read(artifact/'analysis.json') or render(report) != (artifact/'REPORT.md').read_text():
        raise ValueError('Published analysis or report differs')
    return {'gate': report['analysis']['gate'], 'admitted': report['accounting']['admitted'],
            'settled': report['accounting']['settled'], 'new_model_calls': 0, 'candidate_executions': 0}
