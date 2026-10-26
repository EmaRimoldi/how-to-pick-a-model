"""Verify and independently re-execute terminal archived contract evidence; no API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from vao.analysis.contract_diagnostic import summarize, render
from vao.repair.environment import identity
from vao.repair.verifier import RepairVerifier


def read(path):
    return json.loads(path.read_text())


def stable(result):
    return {k: v for k, v in result.items() if k != 'verifier_seconds'}


def reproduce(source, output):
    manifest = read(source / 'evidence-manifest.json')
    archive = source / 'evidence.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['archive_sha256']
    with tempfile.TemporaryDirectory(prefix='contract-independent-replay-') as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(archive) as zipped:
            assert len(zipped.namelist()) == len(set(zipped.namelist()))
            assert set(zipped.namelist()) == set(manifest['files'])
            for name, expected in manifest['files'].items():
                path = Path(name)
                assert not path.is_absolute() and '..' not in path.parts
                content = zipped.read(name)
                assert hashlib.sha256(content).hexdigest() == expected
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        from vao.repair.contracts import TRACE_STUDY, INTERFACE_STUDY
        frozen = read(root / 'collection/manifest.json')['freeze']
        summarizer, renderer = summarize, render
        trace_study = frozen['study'] == TRACE_STUDY
        if trace_study:
            from vao.analysis.repair_information import summarize as summarizer, render as renderer
        if frozen['study'] == INTERFACE_STUDY:
            from vao.analysis.repair_interface import summarize as summarizer, render as renderer
        report = summarizer(root / 'collection')
        assert report == read(source / 'analysis.json')
        assert renderer(report) == (source / 'REPORT.md').read_text()
        verifier = RepairVerifier()
        preflight = verifier.preflight()
        if trace_study:
            from vao.repair.diagnostic_study import validate_diagnostics
            validate_diagnostics(frozen['packet'], verifier)
        results, checks, discrepancies = {}, [], []
        # File-only archives omit empty directories. A stopped first request
        # legitimately has no cells; summarize() above still audits all receipts.
        for cell in sorted((root / 'collection/cells').glob('*')):
            def obj(key):
                return read(cell / 'objects' / (key + '.json'))
            event = read(cell / 'events/000000.json')
            task = next(obj(k) for k in event['objects'] if obj(k)['kind'] == 'task')
            for path in sorted((cell / 'objects').glob('*.json')):
                value = read(path)
                if value['kind'] != 'evaluation':
                    continue
                files = obj(value['artifact'])['files']
                cases = task['public']['public_cases'] if value['channel'] == 'public' else task['evaluator']['cases']
                entrypoint = task['public']['entrypoint']
                key = identity({'files': files, 'entrypoint': entrypoint, 'cases': cases})
                if key not in results:
                    results[key] = verifier.check(files, entrypoint, cases)
                match = stable(results[key]) == stable(value['result'])
                check = {'evaluation': str(path.relative_to(root)), 'input_id': key, 'matched': match}
                checks.append(check)
                if not match:
                    discrepancies.append(check)
        result = {'mode': 'offline_sandbox_reverification', 'api_calls': 0,
                  'archive_sha256': manifest['archive_sha256'],
                  'full_analysis_and_markdown_reproduced': True,
                  'preflight': preflight, 'checked_evaluation_records': len(checks),
                  'unique_input_suites': len(results), 'discrepancies': discrepancies,
                  'checks': checks, 'reexecuted_results': results}
        if trace_study:
            result['public_diagnostic_projections_reexecuted'] = True
        with output.open('x') as stream:
            json.dump(result, stream, sort_keys=True)
            stream.write('\n')
        print(json.dumps({k: v for k, v in result.items() if k not in {'checks', 'reexecuted_results'}}, indent=2))
        if discrepancies:
            raise SystemExit('Saved evaluator outcomes do not reproduce')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reproduce(args.input, args.output)


if __name__ == "__main__":
    main()
