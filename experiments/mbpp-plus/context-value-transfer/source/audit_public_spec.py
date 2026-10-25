"""Check public prompt assertions against official references in a macOS sandbox; no model calls."""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import re
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def audit(problems):
    from evalplus.eval.utils import time_limit
    rows=[]
    for p in problems:
        row={"task_id":p["task_id"],"assertions":0,"status":"pass","failures":[]}
        match=re.fullmatch(r"(?s)\s*[ru]*(\x22\x22\x22|\x27\x27\x27)(.*)\1\s*",p["prompt"])
        if not match:
            row["status"]="parse_error";rows.append(row);continue
        lines=match.group(2).splitlines();tests=[];i=0
        while i<len(lines):
            if lines[i].lstrip().startswith("assert "):
                code=lines[i].strip()
                while True:
                    try:
                        tree=ast.parse(code)
                        if len(tree.body)!=1 or not isinstance(tree.body[0],ast.Assert):raise ValueError()
                        tests.append(code);break
                    except (SyntaxError,ValueError):
                        i+=1
                        if i>=len(lines):row["status"]="parse_error";break
                        code+="\n"+lines[i]
            i+=1
        # math belongs to the assertion harness, not to the generated solution.
        ns={"math":__import__("math")}
        try:
            with contextlib.redirect_stdout(io.StringIO()),time_limit(1):
                exec(compile(p["prompt"]+p["canonical_solution"],"reference","exec"),ns)
            for code in tests:
                row["assertions"]+=1
                try:
                    with contextlib.redirect_stdout(io.StringIO()),time_limit(1):
                        exec(compile(code,"public_prompt_assertion","exec"),ns)
                except BaseException as exc:
                    row["status"]="fail"
                    row["failures"].append({"assertion":code,"error":type(exc).__name__+": "+str(exc)[:500]})
        except BaseException as exc:
            row["status"]="error";row["failures"].append({"error":type(exc).__name__+": "+str(exc)[:500]})
        if not tests and row["status"]=="pass":row["status"]="no_assertion"
        rows.append(row)
    return rows


def main():
    if "--worker" in sys.argv:
        resource.setrlimit(resource.RLIMIT_CPU,(20,20))
        resource.setrlimit(resource.RLIMIT_FSIZE,(1_048_576,1_048_576))
        print(json.dumps(audit(json.load(sys.stdin))))
        return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    from evalplus.data import get_mbpp_plus,get_mbpp_plus_hash
    from vao.decisions.verification import sandbox_profile
    if sys.platform!="darwin" or not shutil.which("sandbox-exec"):
        parser.error("This reference audit requires macOS sandbox-exec")
    if get_mbpp_plus_hash()!="ee43ecabebf20deef4bb776a405ac5b1":
        parser.error("Pinned MBPP+ changed")
    problems=[{k:p[k] for k in ("task_id","prompt","canonical_solution")} for p in get_mbpp_plus().values()]
    with tempfile.TemporaryDirectory(prefix="decision-verifier-") as temp:
        work=Path(temp);script=work/"audit.py";shutil.copyfile(__file__,script)
        result=subprocess.run(["sandbox-exec","-p",sandbox_profile(work),sys.executable,"-I",str(script),"--worker"],
            input=json.dumps(problems),capture_output=True,text=True,cwd=work,timeout=60,
            env={"PATH":"/usr/bin:/bin","HOME":temp,"TMPDIR":temp,"OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1"})
        if result.returncode:raise RuntimeError("Reference audit subprocess failed: "+result.stderr[-1000:])
        rows=json.loads(result.stdout)
    with args.output.open("x") as f:f.write(json.dumps(rows,sort_keys=True,indent=2)+"\n")
    from collections import Counter
    print(json.dumps(dict(Counter(r["status"] for r in rows))))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
