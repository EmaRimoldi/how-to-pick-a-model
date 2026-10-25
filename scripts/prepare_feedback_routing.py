"""Verify the pinned BigCodeBench download and reproduce reference-only eligibility."""

import argparse
import importlib.metadata
import json
from pathlib import Path

from vao.decisions.bigcode import DATA_FILE, PARQUET_SHA256, REVISION, audit_tasks, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, help="Previously downloaded pinned Parquet, never Python code")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    url = f"https://huggingface.co/datasets/bigcode/bigcodebench/resolve/{REVISION}/{DATA_FILE}"
    if args.parquet is None:
        print(json.dumps({"mode": "plan_only", "download": url, "sha256": PARQUET_SHA256,
                          "models": "No model calls; explicit --parquet and --output run sandbox reference checks"}, indent=2))
        return
    if args.output is None:
        parser.error("--parquet requires a fresh --output")
    if args.output.exists():
        raise ValueError("Do not overwrite prior eligibility evidence")
    if sha(args.parquet) != PARQUET_SHA256:
        raise ValueError("Pinned Parquet checksum mismatch")
    if importlib.metadata.version("evalplus") != "0.3.1":
        raise ValueError("Reference reproduction requires EvalPlus 0.3.1")
    from evalplus.data import get_human_eval_plus, get_human_eval_plus_hash, get_mbpp_plus, get_mbpp_plus_hash
    if get_human_eval_plus_hash() != "fe585eb4df8c88d844eeb463ea4d0302" or get_mbpp_plus_hash() != "ee43ecabebf20deef4bb776a405ac5b1":
        raise ValueError("Prior-prompt duplicate screen dataset changed")
    import pandas as pd
    rows = pd.read_parquet(args.parquet).to_dict("records")  # Requires a Parquet engine, e.g. pyarrow.
    if len(rows) != 1140:
        raise ValueError("Unexpected raw task count")
    prior = [t["prompt"] for tasks in (get_human_eval_plus(), get_mbpp_plus()) for t in tasks.values()]
    summary = audit_tasks(rows, args.output, prior)
    print(json.dumps({k: v for k, v in summary.items() if k != "selected_task_ids"}, indent=2))


if __name__ == "__main__":
    main()
