"""Audit recorded recovery results and build the separate empirical paper offline."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True,help="Fresh out-of-tree build directory")
    parser.add_argument("--pdflatex",default="pdflatex")
    args=parser.parse_args()
    source=Path(__file__).resolve().parent
    root=source.parents[2]
    evidence=root/"experiments/mbpp-plus/context-value-transfer/results/replication-20261022"
    if "\\Pending" in (source/"main.tex").read_text():
        raise ValueError("Unfinished manuscript: do not build a final research artifact")
    if not (evidence/"analysis.json").exists():
        raise ValueError("Final audited evidence is not available")
    tex=shutil.which(args.pdflatex)
    if not tex:
        raise ValueError("pdflatex is required; source and evidence remain available")
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    def run(command,cwd,log):
        result=subprocess.run(command,cwd=cwd,capture_output=True,text=True)
        (output/log).write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError("Offline build failed; inspect "+str(output/log))
    command=[sys.executable,"scripts/analyze_recovery_transfer.py","--input",str(evidence),
             "--output",str(output/"evidence-audit"),"--expected-analysis",str(evidence/"analysis.json")]
    if (evidence/"semantic-control").is_dir():command += ["--forecasts",str(evidence/"semantic-control")]
    run(command,root,"evidence-audit.log")
    run([sys.executable,str(source/"build_tables.py"),"--input",str(output/"evidence-audit/analysis.json"),
         "--output",str(output/"generated"),"--allow-incomplete-descriptive"],root,"tables.log")
    shutil.copyfile(source/"main.tex",output/"recovery-value.tex")
    for i in (1,2,3):
        run([tex,"-interaction=nonstopmode","-halt-on-error","recovery-value.tex"],output,f"latex-pass-{i}.log")
    print(json.dumps({"pdf":str(output/"recovery-value.pdf"),"offline_audit":"matched recorded analysis",
                      "data":str(evidence),"manuscript":"separate from the existing NeurIPS sources"}))


if __name__=="__main__":
    main()
