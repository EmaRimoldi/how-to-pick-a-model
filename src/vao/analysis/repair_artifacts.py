"""Post hoc structural-edit diagnostic for a closed repair bank; zero model calls."""
import argparse
import ast
import json
from pathlib import Path

from vao.analysis.repair_calibration import lineage, read_json
from vao.repair.pilot import audit, rows
from vao.repair.records import save


def same_ast(before: dict, after: dict):
    if set(before) != set(after):
        return False
    try:
        return all(ast.dump(ast.parse(before[name]), include_attributes=False) ==
                   ast.dump(ast.parse(after[name]), include_attributes=False) for name in before)
    except (SyntaxError, ValueError, TypeError, RecursionError):
        return None


def diagnose(leaf: Path) -> dict:
    if not ((leaf / 'pilot-completion.json').exists() or (leaf / 'interruption.json').exists()):
        raise ValueError('Only terminal banks may be diagnosed')
    artifacts, checkpoints = [], []
    for segment in lineage(leaf):
        audit(segment)
        for row in rows(segment / 'observations.jsonl'):
            if not row['artifact']:
                continue
            root = segment / 'trajectories' / row['trajectory']
            def obj(key):
                return read_json(root / 'objects' / (key + '.json'))
            branch = obj(row['branch'])
            before = obj(branch['starting_artifact'])['files']
            after = obj(row['artifact'])['files']
            artifacts.append({'attempt_id': row['attempt_id'], 'trajectory': row['trajectory'],
                'phase': row['phase'], 'action': branch['action'],
                'same_ast_as_supplied_files': same_ast(before, after), 'byte_identical': before == after})
        for group in rows(segment / 'groups.jsonl'):
            root = segment / 'trajectories' / group['trajectory']
            def obj(key):
                return read_json(root / 'objects' / (key + '.json'))
            initial = read_json(root / 'events' / '000000.json')['objects'][1]
            original, current = obj(initial)['files'], obj(obj(group['checkpoint'])['artifact'])['files']
            checkpoints.append({'group': group['group'], 'trajectory': group['trajectory'],
                'same_ast_between_actions': same_ast(original, current), 'byte_identical': original == current})
    return {'status': 'post_hoc_development_diagnostic', 'api_calls': 0,
            'valid_artifacts': len(artifacts), 'ast_unchanged_artifacts': sum(r['same_ast_as_supplied_files'] is True for r in artifacts),
            'syntax_uncomparable_artifacts': sum(r['same_ast_as_supplied_files'] is None for r in artifacts),
            'observed_checkpoints': len(checkpoints), 'ast_identical_action_inputs': sum(r['same_ast_between_actions'] is True for r in checkpoints),
            'by_phase': {phase: {'valid': sum(r['phase'] == phase for r in artifacts),
                                 'ast_unchanged': sum(r['phase'] == phase and r['same_ast_as_supplied_files'] is True for r in artifacts)}
                         for phase in ('prefix', 'branch')},
            'artifacts': artifacts, 'checkpoints': checkpoints,
            'limitations': ['Added after the primary descriptive report; no exclusions or comparison changes.',
                            'AST identity ignores comments, formatting and location attributes; it is not a general semantic-equivalence test.',
                            'Textually different but AST-identical inputs can still affect an LLM; these are not identical API requests.',
                            'Counts are correlated within bugs/checkpoints; no causal or population inference.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = diagnose(args.input)
    save(args.output, result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('artifacts','checkpoints','limitations')}, indent=2))


if __name__ == '__main__':
    main()
