"""Explicit commands for the frozen stdin pilot; no default collection."""
import argparse
import json
from pathlib import Path

from vao.repair import stdin_collection as collection
from vao.repair import stdin_results as results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('freeze'); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('live'); p.add_argument('--input', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('progress'); p.add_argument('--input', type=Path, required=True)
    p = sub.add_parser('verify'); p.add_argument('--input', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    for name in ('audit', 'publish'):
        p = sub.add_parser(name); p.add_argument('--input', type=Path, required=True); p.add_argument('--verification', type=Path, required=True)
        if name == 'publish':
            p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'freeze':
        answer = collection.freeze(args.output.resolve())
    elif args.command == 'live':
        answer = collection.collect(collection.read(args.input), args.output.resolve())
    elif args.command == 'progress':
        frozen = collection.read(args.input / 'manifest.json')['freeze']
        money = collection.accounting(args.input, frozen)
        answer = {k:v for k,v in money.items() if k not in {'settled_attempts', 'admitted_attempts'}}
        answer['maximum_slots'] = 110
        answer['model_terminal'] = (args.input/'completion.json').exists() or (args.input/'interruption.json').exists()
    elif args.command == 'verify':
        answer = results.verify(args.input.resolve(), args.output.resolve())
    elif args.command == 'audit':
        answer = results.analyze(args.input.resolve(), args.verification.resolve())
    else:
        answer = results.publish(args.input.resolve(), args.verification.resolve(), args.output.resolve())
    print(json.dumps(answer, indent=2))


if __name__ == '__main__':
    main()
