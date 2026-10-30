"""Freeze and execute offline public diagnostic preparation on qualified sources.

No provider client, model request or paid authorization exists in this command.
The freeze fixes all eleven source-qualified groups and retains all twelve
original group decisions; flat/unavailable spectra cannot change the selection.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import html.parser
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

from vao.repair import stdin_ablation as ablation
from vao.repair.stdin_verifier import StdinVerifier
from vao.repair.stdin_monitoring import MonitoringStdinVerifier

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / 'experiments/python-repair/checkpoint-environment/results/fixeval-source-qualification-20261030'
SOURCES = ['scripts/prepare_stdin_ablation.py', 'src/vao/repair/stdin_ablation.py',
           'src/vao/repair/stdin_verifier.py', 'src/vao/repair/stdin_worker.py',
           'src/vao/repair/coverage_worker.py', 'src/vao/repair/spectra.py',
           'src/vao/repair/environment.py', 'src/vao/decisions/verification.py', 'uv.lock',
           'src/vao/repair/stdin_monitoring.py', 'src/vao/repair/stdin_monitoring_worker.py',
           'src/vao/repair/monitoring_coverage.py']


def sha(raw): return hashlib.sha256(raw).hexdigest()


class Statement(html.parser.HTMLParser):
    """Render only text from a locally saved public statement; never follow links."""
    BLOCKS = {'p','div','section','h1','h2','h3','h4','li','pre','br','hr','tr'}

    def __init__(self): super().__init__(); self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCKS: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in self.BLOCKS: self.parts.append('\n')
    def handle_data(self, text): self.parts.append(text)
    def text(self): return '\n'.join(line.strip() for line in ''.join(self.parts).splitlines() if line.strip())


def freeze(output, engine):
    if output.exists(): raise ValueError('Never overwrite a preparation freeze')
    subprocess.run([sys.executable, str(BANK / 'reproduce.py')], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    manifest = json.loads((BANK / 'manifest.json').read_text())
    if sha((BANK / 'evidence.zip').read_bytes()) != manifest['archive_sha256']:
        raise ValueError('Source bank archive changed')
    with zipfile.ZipFile(BANK / 'evidence.zip') as archive:
        old = json.loads(archive.read('qualification-freeze.json'))
        source_entries = json.loads(archive.read('source-extraction.json'))['selected']
        qualification = json.loads((BANK / 'analysis.json').read_text())
        rows = []
        for decision in qualification['groups']:
            if decision['selected_pair_index'] is None: continue
            group = next(g for g in old['groups'] if g['problem_id'] == decision['problem_id'])
            pair = next(p for p in group['pairs'] if p['pair_index'] == decision['selected_pair_index'])
            source = pair['sources']['buggy']
            raw_source = base64.b64decode(source['source_b64'], validate=True)
            if sha(raw_source) != source['sha256']: raise ValueError('Source differs from qualification')
            entry = source_entries[f'Project_CodeNet/problem_descriptions/{group["problem_id"]}.html']
            raw_statement = archive.read(entry['path'])
            if sha(raw_statement) != entry['sha256']: raise ValueError('Statement differs from qualification')
            reader = Statement(); reader.feed(raw_statement.decode('utf-8'))
            selected = [c for c in group['cases'] if c['split'] == 'public']
            public = {'schema_version': 3, 'instruction': reader.text(),
                      'files': {'main.py': raw_source.decode('utf-8')}, 'comparator': 'ascii_whitespace_tokens',
                      'public_cases': [{'id': f'case_{i:03}',
                                        'stdin': base64.b64decode(c['input_b64'], validate=True).decode('utf-8'),
                                        'expected_stdout': base64.b64decode(c['expected_b64'], validate=True).decode('utf-8')}
                                       for i,c in enumerate(selected, 1)]}
            bound = ablation.binding(public)
            rows.append({'problem_id': group['problem_id'], 'pair_index': pair['pair_index'],
                         'source_sha256': source['sha256'], 'raw_statement_sha256': entry['sha256'],
                         'public_case_origin': {p['id']: c['id'] for p,c in zip(public['public_cases'], selected)},
                         'binding': bound, 'public': public})
    if len(rows) != 11: raise ValueError('This development preparation requires all eleven qualified groups')
    result = {'kind': 'offline_stdin_ablation_preparation_not_model_study',
              'coverage_engine': engine,
              'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'qualification_archive_sha256': manifest['archive_sha256'],
              'qualification_analysis_sha256': sha((BANK / 'analysis.json').read_bytes()),
              'all_original_group_decisions': [{k:g[k] for k in ['problem_id','group_id','selected_pair_index']}
                                               for g in qualification['groups']],
              'tasks': rows, 'implementation_sha256': {name: sha((ROOT / name).read_bytes()) for name in SOURCES},
              'python_version': sys.version, 'python_executable_sha256': sha(Path(sys.executable).read_bytes()),
              'wall_timeout_seconds': 5, 'planned_observation_executions': sum(len(r['public']['public_cases']) for r in rows),
              'planned_acquisition_executions': 2*sum(len(r['public']['public_cases']) for r in rows),
              'rules': ['One fresh observation, then ordinary and covered execution of every public case.',
                        'Keep every group, tie, zero score, unavailable diagnostic and observation mismatch.',
                        'F/N/S share all task/source/case/feedback fields. N/S share locations and canonical order.',
                        'Only S receives exact public pass/fail associations; no evaluator/reference or provenance enters any request.',
                        'No model collection, selection fitting, resource conversion or efficacy inference.',
                        'Any engineering exception stops preparation, retains partial records and requires audit. No silent retries.'],
              'new_model_calls': 0, 'provider_call_enabled': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['kind','planned_observation_executions','planned_acquisition_executions','new_model_calls']}))


def run(plan_path, output):
    if output.exists(): raise ValueError('Never overwrite or resume a preparation run')
    raw_plan = plan_path.read_bytes(); plan = json.loads(raw_plan)
    for name, digest in plan['implementation_sha256'].items():
        if sha((ROOT / name).read_bytes()) != digest: raise ValueError('Frozen implementation changed')
    if plan['python_version'] != sys.version or plan['python_executable_sha256'] != sha(Path(sys.executable).read_bytes()):
        raise ValueError('Frozen runtime changed')
    for row in plan['tasks']:
        if row['binding'] != ablation.binding(row['public']): raise ValueError('Frozen public state changed')
    output.mkdir(parents=True)
    (output / 'plan.json').write_bytes(raw_plan)
    cls = {'legacy': StdinVerifier, 'monitoring': MonitoringStdinVerifier}[plan['coverage_engine']]
    verifier = cls(plan['wall_timeout_seconds']); started = time.monotonic()
    state = {'plan_sha256': sha(raw_plan), 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'new_model_calls': 0, 'completed_tasks': 0, 'candidate_executions': 0}
    with (output / 'records.jsonl').open('x') as journal:
        try:
            preflight_start = time.monotonic(); state['preflight'] = verifier.preflight()
            state['preflight_seconds'] = time.monotonic()-preflight_start
            for task in plan['tasks']:
                public = task['public']; stored = ablation.observe(public, verifier)
                # Persist the base observation before diagnostics, so a later error loses no completed phase.
                partial = {'problem_id': task['problem_id'], 'phase': 'observed', 'stored': stored}
                with (output / 'phase-journal.jsonl').open('a') as phases:
                    phases.write(json.dumps(partial)+'\n')
                acquisition = ablation.acquire(public, stored, verifier)
                with (output / 'phase-journal.jsonl').open('a') as phases:
                    phases.write(json.dumps({'problem_id': task['problem_id'], 'phase':'acquired','acquisition':acquisition})+'\n')
                projection_start = time.monotonic()
                diagnostic = ablation.analyze(public, stored, acquisition)
                requests = ablation.triplet(public, stored, acquisition)
                row = {'problem_id': task['problem_id'], 'binding': task['binding'], 'stored': stored,
                       'acquisition': acquisition, 'diagnostic': diagnostic, 'requests': requests,
                       'analysis_projection_seconds': time.monotonic()-projection_start}
                journal.write(json.dumps(row)+'\n'); journal.flush()
                state['completed_tasks'] += 1
                state['candidate_executions'] += stored['candidate_executions']+acquisition['candidate_executions']
                print(json.dumps({'completed_tasks':state['completed_tasks'], 'candidate_executions':state['candidate_executions']}), flush=True)
            state['status'] = 'completed'
        except Exception as exc:
            state['status'] = 'interrupted'; state['error_type'] = type(exc).__name__
            raise
        finally:
            state['wall_seconds'] = time.monotonic()-started
            state['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            (output / 'completion.json').write_text(json.dumps(state, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('freeze'); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--engine', choices=['legacy','monitoring'], required=True)
    p = sub.add_parser('run'); p.add_argument('--input', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'freeze': freeze(args.output.resolve(), args.engine)
    else: run(args.input.resolve(), args.output.resolve())


if __name__ == '__main__': main()
