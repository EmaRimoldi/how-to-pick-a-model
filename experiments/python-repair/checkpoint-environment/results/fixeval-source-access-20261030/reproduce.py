# /// script
# requires-python = ">=3.10"
# dependencies = ["ijson==3.4.0"]
# ///
"""Audit source catalogs offline; optionally replay all original submission metadata.

Dataset source and test members are never opened or executed. This is not a
model experiment, candidate qualification or certification of a final holdout.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def report_bytes(name):
    return gzip.decompress((HERE / (name + '.gz')).read_bytes())


def report_json(name):
    return json.loads(report_bytes(name))


class DirectoryOnly(io.RawIOBase):
    """Sparse ZIP view; every read outside directory/end metadata fails closed."""
    def __init__(self, size, offset, metadata):
        self.size, self.offset, self.metadata, self.position = size, offset, metadata, 0
        if offset + len(metadata) != size:
            raise ValueError('Directory/end records do not reach archive end')

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        if whence not in (0, 1, 2):
            raise ValueError('Invalid seek mode')
        position = offset + (0 if whence == 0 else self.position if whence == 1 else self.size)
        if not 0 <= position <= self.size:
            raise ValueError('Seek outside archive')
        self.position = position
        return position

    def read(self, size=-1):
        end = self.size if size < 0 else min(self.position + size, self.size)
        if self.position < self.offset:
            raise ValueError('Candidate/test member bytes are not available in this metadata view')
        raw = self.metadata[self.position-self.offset:end-self.offset]
        self.position = end
        return raw


def audit():
    manifest = json.loads((HERE / 'evidence-manifest.json').read_text())
    if sha((HERE / 'evidence.zip').read_bytes()) != manifest['archive_sha256']:
        raise ValueError('Evidence archive changed')
    with zipfile.ZipFile(HERE / 'evidence.zip') as z:
        if sorted(z.namelist()) != sorted(manifest['members']):
            raise ValueError('Evidence member inventory changed')
        blobs = {n: z.read(n) for n in manifest['members']}
    for name, digest in manifest['members'].items():
        if sha(blobs[name]) != digest:
            raise ValueError('Evidence member changed: ' + name)
    for name, digest in manifest['published_reports'].items():
        if sha((HERE / name).read_bytes()) != digest:
            raise ValueError('Published report changed: ' + name)
    member_counts = {}
    for name in ('python', 'tests'):
        recorded = json.loads(blobs[name + '-inventory.json'])
        directory = blobs[name + '-directory.bin']
        if sha(directory) != recorded['directory_sha256'] or len(directory) != recorded['directory_bytes']:
            raise ValueError('Directory fingerprint differs')
        view = DirectoryOnly(recorded['archive_bytes'], recorded['directory_offset'],
                             directory + blobs[name + '-end-records.bin'])
        with zipfile.ZipFile(view) as archive:
            parsed = [{'name': i.filename, 'bytes': i.file_size, 'compressed_bytes': i.compress_size,
                       'crc32': i.CRC, 'header_offset': i.header_offset,
                       'compression': i.compress_type, 'flags': i.flag_bits} for i in archive.infolist()]
            if parsed != recorded['members']:
                raise ValueError('Independent stdlib ZIP/ZIP64 decoding differs from collection parser')
            try:
                archive.read(next(i for i in archive.infolist() if not i.is_dir()))
            except ValueError as exc:
                if 'member bytes are not available' not in str(exc):
                    raise
            else:
                raise ValueError('Metadata view unexpectedly allowed a candidate/test body')
        member_counts[name] = len(parsed)
    for manifest_name in ('mapping-documents.json', 'duplicates-documents.json'):
        for doc in json.loads(blobs[manifest_name]):
            raw = blobs[doc['local']]
            if sha(raw) != doc['sha256'] or len(raw) != doc['bytes']:
                raise ValueError('Documentation or mapping bytes changed')
            if 'git_blob' in doc:
                identity = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
                if identity != doc['git_blob']:
                    raise ValueError('Pinned Git source differs')
    catalog = report_json('metadata-catalog.json')
    if (sum(catalog['languages'].values()) != catalog['metadata_submissions']
            or sum(catalog['verdicts_all_languages'].values()) != catalog['metadata_submissions']
            or sum(catalog['python_runtimes'].values()) != catalog['python_submissions']
            or sum(r.get('python_submissions', 0) for r in catalog['problems'].values()) != catalog['python_submissions']
            or len(catalog['problems']) != catalog['problem_ids']):
        raise ValueError('Metadata catalog accounting differs')
    frozen = json.loads(blobs['metadata-reader-freeze.json'])
    if (sha(blobs['catalog_metadata.py.txt']) != frozen['script_sha256']
            or frozen != catalog['source']
            or frozen['archive_sha256'] != manifest['raw_processed_archive']['archive_sha256']):
        raise ValueError('Metadata reader/source identity changed')
    joined = report_json('joined-catalog.json')
    rows = joined['rows']
    if len({r['problem_id'] for r in rows}) != len(rows) or len({r['test_group'] for r in rows}) != len(rows):
        raise ValueError('Non-injective problem/directory mapping')
    if (sum(r['paired_cases'] for r in rows) != joined['input_output_pairs']
            or sum(r['directory_layout_complete'] for r in rows) != joined['complete_layout_problems']
            or sum(r['metadata_feasible_not_qualified'] for r in rows) != joined['metadata_feasible_problems_not_qualified']):
        raise ValueError('Join summary differs')
    queue = report_json('development-inspection-queue.json')
    plan = json.loads(blobs['development-inspection-plan.json'])
    if queue['plan_sha256'] != sha(blobs['development-inspection-plan.json']):
        raise ValueError('Queue does not bind its prior plan')
    for name, digest in plan['inputs_sha256'].items():
        raw = report_bytes(name) if name == 'joined-catalog.json' else blobs[name]
        if sha(raw) != digest:
            raise ValueError('Queue input differs from prospective plan')
    selected = [g['group'] for g in queue['selected_development_groups']]
    reserved = queue['reserved_unopened_eligible_groups']
    if (selected != queue['ordered_eligible_groups'][:12]
            or selected + reserved != queue['ordered_eligible_groups']
            or set(selected) & set(reserved)
            or set(selected + reserved) & set(queue['quarantined_group_ids'])):
        raise ValueError('Group selection/reservation boundary differs')
    if any(g['selected_problem_id'] not in g['all_group_problem_ids'] for g in queue['selected_development_groups']):
        raise ValueError('Selected problem not in recorded group')
    selected_file = json.loads((HERE / 'selected-development.json').read_text())
    if (selected_file['groups'] != queue['selected_development_groups']
            or selected_file['reserved_group_count'] != len(reserved)
            or selected_file['plan_sha256'] != queue['plan_sha256']):
        raise ValueError('Readable selection differs from full frozen queue')
    return {'verified_zip_directory_members': member_counts,
            'metadata_submissions': catalog['metadata_submissions'], 'python_submissions': catalog['python_submissions'],
            'python_problem_ids': catalog['python_problem_ids'],
            'provisional_mapped_problems': len(rows),
            'metadata_feasible_not_qualified': joined['metadata_feasible_problems_not_qualified'],
            'selected_development_groups': len(selected), 'reserved_groups_not_certified_holdout': len(reserved),
            'candidate_pairs': sum(len(g['candidate_pairs']) for g in queue['selected_development_groups']),
            'new_model_calls': 0, 'candidate_or_test_members_opened': 0}, blobs


def replay_metadata(source, blobs):
    manifest = json.loads((HERE / 'evidence-manifest.json').read_text())
    expected = manifest['raw_processed_archive']
    if source.stat().st_size != expected['archive_bytes'] or sha(source.read_bytes()) != expected['archive_sha256']:
        raise ValueError('Supplied original metadata archive differs')
    with tempfile.TemporaryDirectory(prefix='fixeval-metadata-replay-') as temporary:
        work = Path(temporary)
        for name, raw in blobs.items():
            if Path(name).name != name:
                raise ValueError('Unexpected nested evidence path')
            (work / name).write_bytes(raw)
        (work / 'processed.zip').symlink_to(source.resolve())
        for name in ('catalog_metadata.py', 'join_catalog.py', 'select_development.py'):
            shutil.copyfile(work / (name + '.txt'), work / name)
            result = subprocess.run([sys.executable, str(work / name)], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError('Metadata replay failed at ' + name + ': ' + result.stderr[-1000:])
        for name in ('metadata-catalog.json', 'joined-catalog.json', 'development-inspection-queue.json'):
            original = report_json(name)
            replay = json.loads((work / name).read_text())
            if name == 'metadata-catalog.json':
                # Execution measurements are not deterministic semantic fields.
                for field in ('elapsed_seconds', 'database_bytes'):
                    original.pop(field); replay.pop(field)
            if original != replay:
                raise ValueError('Full raw-metadata replay differs: ' + name)
    return {'original_archive_submissions_replayed': 13916868,
            'catalog_join_and_group_queue_discrepancies': 0,
            'source_or_test_execution': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-archive', type=Path, help='Also replay the full original processed.zip; needs temporary disk and ~1-2 minutes')
    args = parser.parse_args()
    result, blobs = audit()
    if args.metadata_archive:
        result['full_metadata_replay'] = replay_metadata(args.metadata_archive, blobs)
    else:
        result['full_metadata_replay'] = 'not_run; default audits archived evidence and internal consistency only'
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
