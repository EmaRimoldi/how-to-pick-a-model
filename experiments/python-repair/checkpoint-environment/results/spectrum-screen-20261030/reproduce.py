"""Verify published hashes and reproduce all frozen outcomes without model APIs."""
from pathlib import Path
import argparse
import hashlib
import json
import tempfile
import zipfile

from vao.repair.spectrum_study import audit, render


def reproduce(directory, sandbox=False):
    manifest=json.loads((directory/'manifest.json').read_text())
    for name,sha in manifest.items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('Published artifact checksum differs')
    with tempfile.TemporaryDirectory(prefix='spectrum-evidence-') as temp:
        root=Path(temp)
        with zipfile.ZipFile(directory/'evidence.zip') as z:
            names=z.namelist()
            if len(names)!=len(set(names)) or sum(i.file_size for i in z.infolist())>50_000_000:
                raise ValueError('Archive layout or size differs')
            for name in names:
                path=root/name
                if not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError('Archive path escapes temporary evidence directory')
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(z.read(name))
        result=audit(root/'collection',replay=sandbox)
        saved=json.loads((directory/'analysis.json').read_text())
        if saved['independent_replay'] is not True:
            raise ValueError('Publication lacks the original independent sandbox replay')
        result['independent_replay']=saved['independent_replay']
        if result!=saved or render(result)!=(directory/'REPORT.md').read_text():
            raise ValueError('Published analysis/report does not reproduce')
    return {'hashes_verified':True,'analysis_and_report_reproduced':True,
        'sandbox_reexecuted_now':sandbox,'original_publication_sandbox_replay':True,
        'selected_cells':48,'missing':sum(a['missing'] for a in result['arms'].values()),
        'gate':result['gate'],'api_calls':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sandbox',action='store_true',help='Also rerun candidate suites in the supported macOS sandbox')
    args=parser.parse_args()
    print(json.dumps(reproduce(Path(__file__).resolve().parent,args.sandbox),indent=2))
