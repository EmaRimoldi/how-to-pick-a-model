"""Post hoc edit audit of a terminal information archive; never execute candidates."""

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

from vao.repair.environment import identity
from vao.repair.records import save


def syntax(files, entrypoint, *, omit_entrypoint=False):
    """Compare syntax, not semantic equivalence; ignore comments and locations."""
    result = {}
    for name, source in files.items():
        tree = ast.parse(source)
        if omit_entrypoint and name == entrypoint['module'] + '.py':
            tree.body = [node for node in tree.body if not (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == entrypoint['function'])]
        result[name] = ast.dump(tree, include_attributes=False)
    return result


def classify(before, after, entrypoint):
    if before == after:
        return 'exact_copy'
    try:
        if syntax(before, entrypoint) == syntax(after, entrypoint):
            return 'format_or_comment_only'
        if syntax(before, entrypoint, omit_entrypoint=True) == syntax(after, entrypoint, omit_entrypoint=True):
            return 'entrypoint_only_syntax_change'
    except SyntaxError:
        return 'unparseable'
    return 'other_syntax_change'


def summarize(source):
    manifest = json.loads((source / 'evidence-manifest.json').read_text())
    raw = (source / 'evidence.zip').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['archive_sha256']:
        raise ValueError('Archive hash differs')
    with zipfile.ZipFile(source / 'evidence.zip') as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(manifest['files']):
            raise ValueError('Archive members differ')
        for name, expected in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError('Archive member hash differs')
        def read(name):
            return json.loads(archive.read('collection/' + name))
        if not any('collection/' + name in names for name in ('pilot-completion.json', 'interruption.json')):
            raise ValueError('Only terminal evidence may be inspected')
        packet = read('manifest.json')['freeze']['packet']
        requests = {r['metadata']['attempt_id']: r for r in packet['requests']}
        observations = [json.loads(line) for line in archive.read('collection/observations.jsonl').splitlines()]
        cells = []
        for row in observations:
            attempt = row['attempt_id']
            def obj(key):
                value = read('cells/' + attempt + '/objects/' + key + '.json')
                if identity(value) != key:
                    raise ValueError('Object hash differs')
                return value
            projected = json.loads(requests[attempt]['request']['messages'][1]['content'])
            artifact = obj(row['artifact']) if row['artifact'] else None
            before, entry = projected['files'], projected['entrypoint']
            category = classify(before, artifact['files'], entry) if artifact else 'no_artifact'
            public = obj(row['public'])['result'] if row['public'] else None
            baseline = packet['tasks'][row['task_index']]['source_public_result']
            delta = ((public['passed_cases'] / public['total_cases']) if public else 0) - baseline['passed_cases'] / baseline['total_cases']
            cells.append({'attempt_id': attempt, 'task_index': row['task_index'], 'arm': row['arm'],
                'draw': row['draw'], 'category': category, 'artifact_valid': row['decoded']['artifact_valid'],
                'artifact_content_id': identity(artifact['files']) if artifact else None,
                'public_fraction_delta': delta, 'full_pass': row['full_pass']})
    def group(scoped):
        return {'observed': len(scoped), 'valid': sum(c['artifact_valid'] for c in scoped),
            'edit_categories': dict(sorted(Counter(c['category'] for c in scoped).items())),
            'distinct_artifact_contents': len({c['artifact_content_id'] for c in scoped if c['artifact_content_id']}),
            'public_improvements': sum(c['public_fraction_delta'] > 0 for c in scoped),
            'public_regressions': sum(c['public_fraction_delta'] < 0 for c in scoped),
            'full_successes': sum(c['full_pass'] for c in scoped)}
    return {'kind': 'post_hoc_syntax_and_public_progress_audit', 'api_calls': 0,
        'archive_sha256': manifest['archive_sha256'], 'summary': group(cells),
        'tasks': [{'task': task['public']['task_id'], 'eligible': task['eligible'],
            **group([c for c in cells if c['task_index'] == index])}
            for index, task in enumerate(packet['tasks'])], 'cells': cells,
        'limitations': ['Post hoc diagnosis after terminal state; not a frozen primary comparison.',
            'Syntax identity is not semantic equivalence. Entrypoint-only edits may alter behavior.',
            'Counts describe received answers from exposed bugs, not independent task observations.',
            'Missing outcomes remain missing in the original report; this audit does not change its gate.',
            'Neither anchoring nor prompt interpretation nor insufficient model capacity is causally identified.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.input)
    save(args.output, result)
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
