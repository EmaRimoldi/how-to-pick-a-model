"""Archive exact recorded collector sources from Git, without reading outcomes or calling APIs."""
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path, PurePosixPath


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(ref, path):
    if not re.fullmatch(r"[0-9a-f]{40}",ref):
        raise ValueError("Expected a full recorded Git commit")
    parts=PurePosixPath(path)
    if parts.is_absolute() or ".." in parts.parts:
        raise ValueError("Source path must remain inside the repository")
    return subprocess.check_output(["git","show",ref+":"+path])


def export(root, output, forecasts=None):
    manifest=json.loads((root/"manifest.json").read_text())
    prefix=json.loads((root/"prefix-continuation.json").read_text())
    spec=importlib.util.spec_from_file_location("transfer_audit","scripts/analyze_recovery_transfer.py")
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    recoveries=audit.recovery_lineages(root)
    runtime=json.loads((root/"runtime-snapshot.json").read_text())
    identity=sha((root/"manifest.json").read_bytes())
    if identity!=prefix["source_manifest_sha256"] or any(identity!=r["source_manifest_sha256"] for r in recoveries):
        raise ValueError("Segment manifest identity changed")
    entries=[]
    def add(relative,ref,path,expected=None):
        data=blob(ref,path)
        if expected is not None and sha(data)!=expected:
            raise ValueError("Recorded source/runtime hash does not match Git: "+path)
        if relative.endswith(".py"):relative+=".txt"
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        entries.append({"archive_path":relative,"source_path":path,"git_commit":ref,"sha256":sha(data),
                        "bytes":len(data),"anchor":"recorded_sha256" if expected else "frozen_git_commit"})
    output.mkdir(parents=True,exist_ok=False)
    for path,expected in manifest["source_sha256"].items():
        add("original/"+path,manifest["git_sha"],path,expected)
    for path in ("src/vao/decisions/pilot.py","src/vao/decisions/context_value.py","pyproject.toml"):
        add("original/"+path,manifest["git_sha"],path)
    add("original/uv.lock",manifest["git_sha"],"uv.lock",runtime["uv_lock_sha256"])
    add("prefix-collector/transfer.py",prefix["new_collector_git_sha"],"src/vao/decisions/transfer.py",prefix["new_collector_sha256"])
    refs=[prefix["new_collector_git_sha"]]
    for i,recovery in enumerate(recoveries,1):
        ref=recovery["source_collector_git_sha"];refs.append(ref)
        add(f"recovery-collector-{i}/transfer_continuation.py",ref,
            "src/vao/decisions/transfer_continuation.py",recovery["source_collector_sha256"])
        add(f"recovery-collector-{i}/transfer.py",ref,"src/vao/decisions/transfer.py")
    semantic=None
    if forecasts is not None:
        semantic=json.loads((forecasts/"manifest.json").read_text())
        if semantic["source_manifest_sha256"]!=identity:
            raise ValueError("Semantic source identity changed")
        ref=semantic["git_sha"];refs.append(ref)
        add("semantic-collector/transfer_forecast.py",ref,"src/vao/decisions/transfer_forecast.py",semantic["source_file_sha256"])
        add("semantic-collector/transfer.py",ref,"src/vao/decisions/transfer.py")
    shared=[]
    helpers={k:v for k,v in manifest["source_sha256"].items() if not k.endswith("/transfer.py")}
    for path in ("src/vao/decisions/pilot.py","src/vao/decisions/context_value.py"):
        helpers[path]=sha(blob(manifest["git_sha"],path))
    for ref in refs:
        for path,expected in helpers.items():
            if sha(blob(ref,path))!=expected:
                raise ValueError("A shared helper changed across collection segments: "+path)
            shared.append({"git_commit":ref,"source_path":path,"sha256":expected})
    metadata={"original_manifest_sha256":identity,"runtime_snapshot":runtime,"sources":entries,
              "recovery_segments":len(recoveries),"semantic_collector_archived":semantic is not None,
              "unchanged_shared_helpers":shared,
              "scope":"Collection source provenance only. No new model calls, scoring, analysis or changes to source journals.",
              "note":"Original manifest identifies the experimental freeze; prefix and recovery collectors are separately pinned. Additional transitive helpers are anchored by that frozen Git commit, not an invented runtime hash."}
    (output/"source-map.json").write_text(json.dumps(metadata,sort_keys=True,indent=2)+"\n")
    (output/"checksums.json").write_text(json.dumps({str(p.relative_to(output)):sha(p.read_bytes())
        for p in sorted(output.rglob("*")) if p.is_file()},sort_keys=True,indent=2)+"\n")
    return metadata


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--forecasts",type=Path)
    a=p.parse_args();m=export(a.input,a.output,a.forecasts)
    print(json.dumps({"archived_sources":len(m["sources"]),"hash_anchors_verified":sum(r["anchor"]=="recorded_sha256" for r in m["sources"]),
                      "unchanged_helper_checks":len(m["unchanged_shared_helpers"]),
                      "manifest_sha256":m["original_manifest_sha256"],"output":str(a.output)}))
