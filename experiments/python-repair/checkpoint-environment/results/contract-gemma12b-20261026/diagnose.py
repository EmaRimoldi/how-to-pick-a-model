"""Post hoc structural diagnostic; AST equality is not semantic equivalence."""
import argparse, ast, json
from collections import Counter
from pathlib import Path
from vao.analysis.contract_diagnostic import summarize
from vao.repair.records import rows


def diagnose(source):
    report = summarize(source)  # Terminal-only full integrity audit.
    packet = json.loads((source / 'manifest.json').read_text())['freeze']['packet']
    records = []
    for row in rows(source / 'observations.jsonl'):
        if not row['decoded']['syntax_valid']:
            continue
        artifact = json.loads((source / 'cells' / row['attempt_id'] / 'objects' / (row['artifact'] + '.json')).read_text())
        original = packet['tasks'][row['task_index']]['public']['files']
        same = all(ast.dump(ast.parse(original[k]), include_attributes=False) ==
                   ast.dump(ast.parse(v), include_attributes=False) for k, v in artifact['files'].items())
        records.append({'attempt_id': row['attempt_id'], 'task_index': row['task_index'],
                        'contract': row['contract'], 'artifact': row['artifact'], 'ast_unchanged': same})
    return {'post_hoc': True, 'api_calls': 0, 'study': report['study'],
            'freeze_id': report['freeze_id'], 'syntax_valid_artifacts': len(records),
            'ast_unchanged_artifacts': sum(r['ast_unchanged'] for r in records), 'records': records,
            'limitations': ['AST equality ignores formatting; it is not a general semantic-equivalence test.',
                            'Different ASTs may behave identically; no changed-source row is assumed to be a useful repair.',
                            'No observation is filtered and the prespecified gate remains unchanged.']}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); result=diagnose(a.input)
    with a.output.open('x') as stream: json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'records'},indent=2))
