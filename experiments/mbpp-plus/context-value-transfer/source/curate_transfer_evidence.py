"""Export a finished, censored recovery bank with exact provenance; never run models."""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
from pathlib import Path


PRIMARY_FILES = (
    "manifest.json", "frozen-policy.json", "runtime-snapshot.json", "selection.json", "summary.json",
    "prefix-continuation.json", "recovery-continuation.json", "continuation-preflight.json",
    "recovery-continuation-preflight.json", "calls.jsonl", "budget.jsonl", "initial.jsonl",
    "checkpoints.jsonl", "local-predictions.jsonl", "evaluations.jsonl", "branches.jsonl",
    "blocks.jsonl", "continuation-blocks.jsonl", "transport.jsonl",
)
FORECAST_FILES = ("manifest.json", "summary.json", "calls.jsonl", "budget.jsonl", "predictions.jsonl", "transport.jsonl")
FORBIDDEN = {"api_key", "access_token", "refresh_token", "balance_usd", "total_credits", "total_usage", "limit_remaining", "effective_budget"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(path):
    raw=path.read_text()
    if re.search(r"sk-or-v1-[A-Za-z0-9]{30,}",raw):
        raise ValueError("Credential pattern in "+path.name)
    def visit(value):
        if isinstance(value,dict):
            if set(value)&FORBIDDEN:raise ValueError("Private credential/account field in "+path.name)
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    if path.suffix==".json":visit(json.loads(raw))
    else:
        for line in raw.splitlines():visit(json.loads(line))


def analyzer():
    spec=importlib.util.spec_from_file_location("transfer_audit","scripts/analyze_recovery_transfer.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def refresh_checksums(root):
    payload={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob("*"))
             if p.is_file() and p!=root/"checksums.json"}
    (root/"checksums.json").write_text(json.dumps(payload,sort_keys=True,indent=2)+"\n")


def curate(source, output, provenance, prefix_source, stopped_bank, forecasts=None):
    if not (source/"summary.json").exists():
        raise ValueError("Current collection is not finished; refuse publication export")
    summary=json.loads((source/"summary.json").read_text())
    if summary["status"]!="all_unadmitted_jobs_collected_with_censored_cells":
        raise ValueError("Authorized never-admitted collection has not completed")
    a=analyzer();data=a.audit(source)
    root_freeze=Path("experiments/mbpp-plus/context-value-transfer/configs/recovery-continuation-freeze.json")
    lineage=data["recovery_continuation"]
    freeze_path=Path(lineage.get("authorization_freeze_path") or root_freeze)
    frozen=json.loads(freeze_path.read_text())
    if (lineage["source_hashes"]!=frozen["approved_source_sha256"]
            or lineage["authorized_unadmitted_cells"]!=frozen["authorized_unadmitted_cells"]
            or lineage["authorization"]!=frozen["authorization"]
            or lineage["source_collector_sha256"]!=frozen["continuation_source_sha256"]):
        raise ValueError("Recovery lineage differs from the committed authorization freeze")
    key=lambda r:(r["checkpoint_id"],r["model_name"],r["arm"],r["draw"])
    observed={key(r) for r in data["branches"]};unknown={key(r) for r in data["censored_branch_requests"]}
    expected={(id_,m,arm,d) for id_ in data["selected"] for m in data["config"]["target_models"]
              for arm in ("fresh","artifact","feedback","artifact_feedback","distractor")
              for d in range(data["config"]["branch_repeats"])}
    if observed&unknown or observed|unknown!=expected or len(unknown)!=len(data["censored_branch_requests"]):
        raise ValueError("Every frozen planned cell must be observed or uniquely censored")
    if not unknown or len(data["complete"])==len(data["selected"]):
        raise ValueError("Do not silently relabel this censored bank complete")
    for name in PRIMARY_FILES:
        if not (source/name).exists():raise ValueError("Missing evidence file: "+name)
        inspect(source/name)
    history_files=[]
    if (source/"recovery-continuation-history.json").exists():
        history_files.append(Path("recovery-continuation-history.json"))
    history_files.extend(p.relative_to(source) for p in sorted((source/"recovery-history").rglob("*")) if p.is_file())
    for name in history_files:inspect(source/name)
    for name,expected_hash in json.loads((provenance/"checksums.json").read_text()).items():
        if sha(provenance/name)!=expected_hash:raise ValueError("Provenance checksum changed: "+name)
    source_map=json.loads((provenance/"source-map.json").read_text())
    if (source_map["original_manifest_sha256"]!=sha(source/"manifest.json")
            or source_map["recovery_segments"]!=len(data["recovery_lineages"])):
        raise ValueError("Collector provenance belongs to a different segment history")
    archived={(r["git_commit"],r["source_path"],r["sha256"]) for r in source_map["sources"]}
    required={(data["manifest"]["git_sha"],path,value) for path,value in data["manifest"]["source_sha256"].items()}
    required|={(r["source_collector_git_sha"],"src/vao/decisions/transfer_continuation.py",r["source_collector_sha256"])
                for r in data["recovery_lineages"]}
    prefix=json.loads((source/"prefix-continuation.json").read_text())
    required.add((prefix["new_collector_git_sha"],"src/vao/decisions/transfer.py",prefix["new_collector_sha256"]))
    if forecasts is not None:
        f=json.loads((forecasts/"manifest.json").read_text())
        required.add((f["git_sha"],"src/vao/decisions/transfer_forecast.py",f["source_file_sha256"]))
    if not required<=archived:raise ValueError("An actual collector source is absent from provenance")
    if json.loads((prefix_source/"summary.json").read_text())!=json.loads((source/"prefix-continuation.json").read_text())["source_summary"]:
        raise ValueError("Original prefix stop summary differs")
    if sha(stopped_bank/"summary.json")!=data["recovery_lineages"][0]["source_hashes"]["summary.json"]:
        raise ValueError("Stopped bank summary hash differs")
    semantic=None
    if forecasts is not None:
        if not (forecasts/"summary.json").exists():raise ValueError("Forecast collection still active")
        for name in FORECAST_FILES:
            if (forecasts/name).exists():inspect(forecasts/name)
        semantic,_=a.analyze_semantic(data,forecasts)  #Checks identity, matching, billing and no outcome leakage.
    if output.exists():raise FileExistsError("Never overwrite an evidence bundle")
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".recovery-export-",dir=output.parent) as temp:
        stage=Path(temp)
        for name in PRIMARY_FILES:shutil.copyfile(source/name,stage/name)
        for name in history_files:
            (stage/name).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/name,stage/name)
        shutil.copytree(provenance,stage/"provenance"/"collector-sources")
        stops=stage/"provenance"/"stops";stops.mkdir()
        shutil.copyfile(prefix_source/"summary.json",stops/"prefix-summary.json")
        shutil.copyfile(stopped_bank/"summary.json",stops/"first-bank-summary.json")
        if forecasts is not None:
            target=stage/"semantic-control";target.mkdir()
            for name in FORECAST_FILES:
                if (forecasts/name).exists():shutil.copyfile(forecasts/name,target/name)
        metadata={"coverage":{"selected_states":len(data["selected"]),"complete_30cell_states":len(data["complete"]),
            "observed_recovery_draws":len(observed),"censored_recovery_draws":len(unknown),"expected_recovery_draws":len(expected)},
            "interpretation":"Incomplete descriptive bank; retain all selected states in missing-state bounds.",
            "collection":data["collection"],"semantic_collection":semantic["collection"] if semantic else None,
            "root_authorization_freeze_sha256":sha(root_freeze),"latest_segment_authorization_freeze_sha256":sha(freeze_path),
            "recovery_segments":len(data["recovery_lineages"]),"source_files_preserved_byte_for_byte":True,
            "scope":"Finished collection export only; no credentials, account balances, model requests or candidate execution."}
        (stage/"curation.json").write_text(json.dumps(metadata,sort_keys=True,indent=2)+"\n")
        refresh_checksums(stage)
        a.audit(stage)
        if output.exists():raise FileExistsError("Evidence output appeared during export")
        stage.rename(output)
    return metadata


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--provenance",type=Path,required=True);p.add_argument("--prefix-source",type=Path,required=True)
    p.add_argument("--stopped-bank",type=Path,required=True);p.add_argument("--forecasts",type=Path)
    args=p.parse_args()
    print(json.dumps(curate(args.source,args.output,args.provenance,args.prefix_source,args.stopped_bank,args.forecasts),sort_keys=True))
