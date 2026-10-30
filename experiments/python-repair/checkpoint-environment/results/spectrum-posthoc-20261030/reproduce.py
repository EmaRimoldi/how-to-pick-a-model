"""Offline, inert post hoc audit of every cell in the closed spectrum screen.

No candidate execution, model calls, or imports from collector modules. The
original publication has its own independent receipt/prompt/replay audit.
"""
import argparse
import ast
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import zipfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def case_map(cases):
    result = {c['id']: c for c in cases}
    require(len(result) == len(cases), 'Duplicate case ID')
    return result


def join_cases(definitions, result, baseline=None):
    """Join by identity, never list position; missing execution stays missing."""
    if result is None:
        return None
    expected = case_map(definitions)
    observed = case_map(result['cases'])
    require(expected.keys() == observed.keys(), 'Case identities differ')
    require(result['total_cases'] == len(expected), 'Suite size differs')
    require(result['passed_cases'] == sum(c['passed'] for c in observed.values()),
            'Suite count differs')
    require(result['passed'] == all(c['passed'] for c in observed.values()),
            'Suite acceptance differs')
    if baseline is not None:
        require(expected.keys() == baseline.keys(), 'Baseline identities differ')
    return [{**expected[k], **observed[k],
             'baseline_passed': baseline[k]['passed'] if baseline is not None else None}
            for k in expected]


def ast_same(before, after):
    try:
        return ast.dump(ast.parse(before)) == ast.dump(ast.parse(after))
    except SyntaxError:
        return None


def edits(before, after):
    result = []
    for name in sorted(before.keys() | after.keys()):
        old, new = before.get(name, ''), after.get(name, '')
        a, b = old.splitlines(), new.splitlines()
        changed, insertions = [], []
        for tag, i, j, k, l in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag in ('replace', 'delete'):
                changed.extend(range(i + 1, j + 1))
            if tag == 'insert':
                insertions.append({'after_old_line': i, 'new_lines': list(range(k + 1, l + 1))})
        result.append({'file': name, 'text_identical': old == new,
                       'ast_identical': ast_same(old, new),
                       'changed_old_lines': changed, 'insertions': insertions,
                       'diff': '\n'.join(difflib.unified_diff(a, b, fromfile='source/' + name,
                                                            tofile='response/' + name, lineterm=''))})
    return result


def build(directory):
    plan = json.loads((directory / 'audit-plan.json').read_text())
    source = directory.parent / 'spectrum-screen-20261030'
    evidence = source / 'evidence.zip'
    require(hashlib.sha256(evidence.read_bytes()).hexdigest() == plan['archive_sha256'],
            'Archive differs from the recorded audit plan')
    for name, sha in json.loads((source / 'manifest.json').read_text()).items():
        require(hashlib.sha256((source / name).read_bytes()).hexdigest() == sha,
                'Original publication checksum differs: ' + name)
    original = json.loads((source / 'analysis.json').read_text())
    scores = {c['attempt_id']: c for c in original['cells']}
    with zipfile.ZipFile(evidence) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), 'Duplicate archive member')
        def read(name):
            return json.loads(z.read(name))
        frozen = read('collection/manifest.json')['freeze']['plan']
        records = {r['id']: r for r in frozen['records']}
        require(len(records) == 8 and len(frozen['candidate_inventory']) == 12,
                'Source population differs')
        requests = frozen['requests']
        ids = [q['metadata']['attempt_id'] for q in requests]
        grid = {(q['metadata']['task_id'], q['metadata']['arm'], q['metadata']['draw']) for q in requests}
        expected = {(t, a, d) for t in records for a in ('feedback', 'spectrum') for d in range(3)}
        require(len(ids) == len(set(ids)) == 48 and grid == expected and set(ids) == scores.keys(),
                'Incomplete, repeated or unexpected cell population')
        cells = []
        for q in requests:
            meta = q['metadata']; aid = meta['attempt_id']; r = records[meta['task_id']]
            c = read('collection/cells/' + aid + '.json')
            require(c['metadata'] == meta, 'Cell metadata differs')
            valid = c['decoded']['artifact_valid']
            baseline = case_map(r['stored']['feedback']['cases'])
            public = join_cases(r['public']['public_cases'], c['public'], baseline)
            evaluator = join_cases(r['evaluator']['cases'], c['evaluator'])
            require(valid == (public is not None and evaluator is not None), 'Execution/validity differs')
            full = valid and c['public']['passed'] and c['evaluator']['passed']
            false_acceptance = valid and c['public']['passed'] and not c['evaluator']['passed']
            regression = [v['id'] for v in public if v['baseline_passed'] and not v['passed']] if valid else None
            gains = [v['id'] for v in public if not v['baseline_passed'] and v['passed']] if valid else None
            for key, value in [('full_pass', full), ('false_acceptance', false_acceptance),
                               ('artifact_valid', valid), ('public_regressions', len(regression) if valid else None)]:
                require(scores[aid][key] == value, 'Original score differs: ' + key)
            changes = edits(r['public']['files'], c['decoded']['files']) if valid else None
            top = r['diagnostic']['ranking'][0]['locations']
            changed_locs = {(e['file'], n) for e in changes or [] for n in e['changed_old_lines']}
            receipt = read('collection/receipts/' + aid + '.json')
            syntax_errors = []
            if valid:
                require(json.loads(receipt['content']) == c['decoded']['files'],
                        'Saved files differ from literal JSON response')
                for filename, content in c['decoded']['files'].items():
                    try:
                        ast.parse(content)
                    except SyntaxError as error:
                        syntax_errors.append({'file': filename, 'message': error.msg,
                                              'line': error.lineno, 'text': error.text})
                require(c['decoded']['syntax_valid'] == (not syntax_errors), 'Syntax flag differs')
            failed_statuses = Counter(v['observed']['status'] for v in public or [] if not v['passed'])
            failure_class = ('invalid_contract_or_incomplete' if not valid else
                'public_load_error' if failed_statuses.get('load_error') else
                'public_runtime_failure' if any(k != 'returned' for k in failed_statuses) else
                'public_behavior_failure' if failed_statuses else
                'public_pass_evaluator_failure' if false_acceptance else 'full_pass')
            cells.append({'task_id': meta['task_id'], 'draw': meta['draw'], 'arm': meta['arm'],
                'attempt_id': aid, 'artifact_valid': valid, 'invalid_reason': c['decoded']['reason'],
                'syntax_valid': c['decoded']['syntax_valid'] if valid else None,
                'syntax_errors': syntax_errors if valid else None,
                'response_finish_reason': receipt['finish_reason'],
                'literal_json_equals_artifact': True if valid else None,
                'failure_class': failure_class, 'failed_public_statuses': dict(sorted(failed_statuses.items())) if valid else None,
                'full_pass': full, 'false_acceptance': false_acceptance,
                'public_gains': gains, 'public_regressions': regression,
                'text_identical': all(e['text_identical'] for e in changes) if valid else None,
                'ast_identical': all(e['ast_identical'] for e in changes) if valid else None,
                'top_rank_changed_old_lines': [v for v in top if (v['file'], v['line']) in changed_locs] if valid else None,
                'edits': changes, 'public_cases': public, 'evaluator_cases': evaluator,
                'invalid_response': receipt.get('content') if not valid else None,
                'cost_usd': scores[aid]['cost_usd']})
    summaries = {}
    for arm in ('feedback', 'spectrum'):
        selected = [c for c in cells if c['arm'] == arm]
        summaries[arm] = {'cells': len(selected),
            **{k: sum(c[k] is True for c in selected) for k in
               ('artifact_valid', 'full_pass', 'false_acceptance', 'text_identical', 'ast_identical')},
            'outputs_gaining_public_case': sum(bool(c['public_gains']) for c in selected),
            'outputs_regressing_public_case': sum(bool(c['public_regressions']) for c in selected),
            'public_case_gains': sum(len(c['public_gains'] or []) for c in selected),
            'public_case_regressions': sum(len(c['public_regressions'] or []) for c in selected),
            'syntax_valid_outputs': sum(c['syntax_valid'] is True for c in selected),
            'failure_classes': dict(sorted(Counter(c['failure_class'] for c in selected).items()))}
    pairs = []
    for task in records:
        for draw in range(3):
            pair = {c['arm']: c for c in cells if c['task_id'] == task and c['draw'] == draw}
            pairs.append({'task_id': task, 'draw': draw,
                'feedback_attempt': pair['feedback']['attempt_id'], 'spectrum_attempt': pair['spectrum']['attempt_id'],
                'spectrum_minus_feedback': int(pair['spectrum']['full_pass']) - int(pair['feedback']['full_pass'])})
    return {'kind': plan['kind'], 'archive_sha256': plan['archive_sha256'],
        'candidate_inventory': frozen['candidate_inventory'], 'source_records': [{
            'id': r['id'], 'public': r['public'], 'stored_public_feedback': r['stored']['feedback'],
            'diagnostic': r['diagnostic'], 'source_attempt_id': r['source_attempt_id']}
            for r in records.values()],
        'cells': cells, 'paired_cells': pairs, 'summary': summaries,
        'unchanged_primary_gate': original['gate'], 'api_calls': 0,
        'interpretation': 'Retrospective artifact/test facts. Code-edit overlap does not identify attention or causal mechanism.'}


def render(data):
    out = ['# Complete retrospective case ledger', '',
        'Generated from the frozen evidence without executing candidate code or making API calls.',
        'Evaluator witnesses are retrospective outcome explanations, never acquisition inputs.',
        'Line numbers refer to each supplied source; diffs are textual, AST equality ignores comments/formatting.',
        'Markdown display trims trailing whitespace; audit.json preserves exact source and diff text.',
        'Insertions have no changed old line; rank overlap is not a causal attribution.', '']
    for r in data['source_records']:
        out += ['## ' + r['id'], '', r['public']['instruction'], '', '### Supplied source', '']
        for name, content in r['public']['files'].items():
            out += [name, '', '```text', '\n'.join(f'{i:3}: {s}' for i, s in enumerate(content.splitlines(), 1)), '```', '']
        out += ['Top-ranked locations: `' + json.dumps(r['diagnostic']['ranking'][0]['locations']) + '`.', '',
                'Initial failing public cases: ' + ', '.join(c['id'] for c in r['stored_public_feedback']['cases'] if not c['passed']) + '.', '']
        for c in sorted((c for c in data['cells'] if c['task_id'] == r['id']), key=lambda c: (c['draw'], c['arm'])):
            out += [f"### {c['arm']} draw {c['draw']}", '', f"Attempt: `{c['attempt_id']}`.", '',
                f"Full repair: {c['full_pass']}; valid file mapping: {c['artifact_valid']}; valid syntax: {c['syntax_valid']}; unchanged text: {c['text_identical']}; unchanged AST: {c['ast_identical']}.",
                f"Observed category: {c['failure_class']}. These categories prioritize load/runtime errors over wrong returned values.",
                f"Public gains: {c['public_gains']}; public regressions: {c['public_regressions']}; false acceptance: {c['false_acceptance']}.", '']
            if not c['artifact_valid']:
                out += ['Invalid reason: `' + c['invalid_reason'] + '`. No tests executed for this cell.', '',
                        'Raw response is preserved in audit.json and the original receipt.', '']
            for edit in c['edits'] or []:
                if edit['diff']:
                    out += ['```diff', edit['diff'], '```', '']
            for name in ('public_cases', 'evaluator_cases'):
                failures = [v for v in c[name] or [] if not v['passed']]
                out += [name + ' failures:', '', '```json', json.dumps(failures, indent=2, ensure_ascii=False), '```', '']
    return '\n'.join(line.rstrip() for part in out for line in part.split('\n')).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Write derived audit.json and CASES.md; default verifies them')
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    data = build(directory)
    artifacts = {'audit.json': json.dumps(data, indent=2, ensure_ascii=False) + '\n', 'CASES.md': render(data)}
    for name, content in artifacts.items():
        path = directory / name
        if args.write:
            path.write_text(content)
        else:
            require(path.read_text() == content, 'Derived audit differs: ' + name)
    print(json.dumps({'verified_cells': len(data['cells']), 'summary': data['summary'],
                      'primary_gate': data['unchanged_primary_gate'], 'api_calls': 0}, indent=2))


if __name__ == '__main__':
    main()
