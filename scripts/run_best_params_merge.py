#!/usr/bin/env python3
"""Best-params merge: read agent results.tsv + git history, build merged train.py.

Strategy:
  1. For each agent, parse results/results.tsv (commit_hash, val_bpb, status)
  2. For each accepted ("keep") run, extract hyperparameters from that git commit
  3. Find best val_bpb value per hyperparameter across all agents
  4. Build merged train.py and submit to SLURM

Usage:
    python scripts/run_best_params_merge.py --run-id exp_20260401_120000
    python scripts/run_best_params_merge.py --run-id exp_20260401_120000 --submit
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

TUNABLE = [
    "EMBEDDING_LR",
    "UNEMBEDDING_LR",
    "MATRIX_LR",
    "SCALAR_LR",
    "WEIGHT_DECAY",
    "WARMDOWN_RATIO",
    "WARMUP_RATIO",
    "FINAL_LR_FRAC",
]


def extract_params(train_py: str) -> dict[str, str]:
    """Extract TUNABLE parameter values from train.py source."""
    params = {}
    for p in TUNABLE:
        m = re.search(rf"^{p}\s*=\s*([^\s#\n]+)", train_py, re.M)
        if m:
            params[p] = m.group(1)
    return params


def apply_params(train_py: str, params: dict[str, str]) -> str:
    """Substitute TUNABLE parameter values into train.py source."""
    result = train_py
    for p, v in params.items():
        result = re.sub(rf"^({p}\s*=\s*)[^\s#\n]+", rf"\g<1>{v}", result, flags=re.M)
    return result


def git_show_train(workspace: Path, commit_hash: str) -> str | None:
    """Return train.py content at a given git commit, or None on failure."""
    try:
        r = subprocess.run(
            ["git", "show", f"{commit_hash}:train.py"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def read_results_tsv(tsv_path: Path) -> list[dict]:
    """Parse results/results.tsv into list of dicts."""
    rows = []
    if not tsv_path.exists():
        return rows
    for line in tsv_path.read_text().splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 4:
            continue
        commit_hash, val_bpb_str, peak_vram_str, status = parts[:4]
        description = parts[4] if len(parts) > 4 else ""
        try:
            val_bpb = float(val_bpb_str)
        except ValueError:
            continue
        rows.append({
            "commit": commit_hash,
            "val_bpb": val_bpb,
            "peak_vram": peak_vram_str,
            "status": status,
            "description": description,
        })
    return rows


def poll_job(workspace: Path, job_id: str, interval: int = 30, timeout: int = 900) -> str:
    """Poll check_training.sh until DONE/FAILED. Returns final status line."""
    start = time.monotonic()
    while True:
        r = subprocess.run(
            ["bash", "check_training.sh", job_id],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = r.stdout.strip()
        print(f"  [{int(time.monotonic()-start)}s] {out[:120]}")
        if "TRAINING DONE" in out or "TRAINING FAILED" in out:
            return out
        if time.monotonic() - start > timeout:
            return f"TIMEOUT after {timeout}s"
        time.sleep(interval)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Best-params merge phase.")
    parser.add_argument("--run-id", required=True, help="Experiment run ID (directory under runs/)")
    parser.add_argument("--runs-dir", default="runs", help="Base runs directory")
    parser.add_argument("--submit", action="store_true", help="Submit merged train.py to SLURM")
    parser.add_argument("--slurm-partition", default="pi_tpoggio")
    parser.add_argument("--slurm-gres", default="gpu:1")
    parser.add_argument("--slurm-time", default="00:10:00")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).parents[1].resolve()
    base = (repo_root / args.runs_dir / args.run_id / "mode_parallel").resolve()

    if not base.exists():
        print(f"[merge] ERROR: {base} not found", file=sys.stderr)
        sys.exit(1)

    auto = repo_root / ".git" / "modules" / "autoresearch"
    baseline_train = auto / "train.py"
    if not baseline_train.exists():
        # fallback: check autoresearch submodule directory
        baseline_train = repo_root / "autoresearch" / "train.py"
    baseline_src = baseline_train.read_text()
    baseline_params = extract_params(baseline_src)

    print(f"[merge] Baseline params: {baseline_params}")

    # Collect evidence per agent
    best_per_param: dict[str, tuple[float, str, str]] = {}  # param -> (val_bpb, value, agent_id)
    agent_bests: list[tuple[str, float]] = []

    for agent_dir in sorted(base.glob("agent_*")):
        agent_id = agent_dir.name
        workspace = agent_dir / "workspace"
        tsv_path = agent_dir / "results" / "results.tsv"
        rows = read_results_tsv(tsv_path)

        if not rows:
            print(f"[merge] {agent_id}: no results.tsv rows — skipping")
            continue

        keep_rows = [r for r in rows if r["status"] == "keep"]
        if not keep_rows:
            print(f"[merge] {agent_id}: no 'keep' rows — using all rows")
            keep_rows = rows

        best_row = min(keep_rows, key=lambda r: r["val_bpb"])
        agent_bests.append((agent_id, best_row["val_bpb"]))
        print(f"[merge] {agent_id}: best val_bpb={best_row['val_bpb']:.6f} "
              f"(commit={best_row['commit'][:8]}, {len(keep_rows)} keep rows)")

        # Extract params from each kept commit
        for row in keep_rows:
            train_py = git_show_train(workspace, row["commit"])
            if train_py is None:
                print(f"[merge]   {agent_id}: git show {row['commit'][:8]} failed — skipping")
                continue
            params = extract_params(train_py)
            for pname, pval in params.items():
                current = best_per_param.get(pname)
                if current is None or row["val_bpb"] < current[0]:
                    best_per_param[pname] = (row["val_bpb"], pval, agent_id)

    if not agent_bests:
        print("[merge] No agent data found — cannot merge.")
        sys.exit(1)

    overall_best_agent, overall_best_bpb = min(agent_bests, key=lambda x: x[1])
    print(f"\n[merge] Best individual: {overall_best_agent} val_bpb={overall_best_bpb:.6f}")

    # Build merged train.py
    merged = baseline_src
    changes = {}
    print("\n[merge] Parameter transplants:")
    for pname, (bpb, pval, agent_id) in sorted(best_per_param.items()):
        baseline_val = baseline_params.get(pname)
        if baseline_val is not None and pval != baseline_val:
            merged = apply_params(merged, {pname: pval})
            changes[pname] = {"from": baseline_val, "to": pval, "agent": agent_id, "val_bpb": bpb}
            print(f"  {pname}: {baseline_val} -> {pval}  ({agent_id}, bpb={bpb:.6f})")
        else:
            print(f"  {pname}: unchanged at {baseline_params.get(pname, '?')}")

    # Write outputs
    merge_dir = repo_root / args.runs_dir / args.run_id / "mode_merge"
    candidates_dir = merge_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    (merge_dir / "logs").mkdir(exist_ok=True)
    results_dir = merge_dir / "results"
    results_dir.mkdir(exist_ok=True)

    merged_path = candidates_dir / "candidate_merged.py"
    merged_path.write_text(merged)
    print(f"\n[merge] Merged train.py written to: {merged_path}")

    plan = {
        "strategy": "best_params_per_agent",
        "agent_bests": dict(agent_bests),
        "best_individual_agent": overall_best_agent,
        "best_individual_val_bpb": overall_best_bpb,
        "changes": changes,
    }
    (merge_dir / "merge_plan.json").write_text(json.dumps(plan, indent=2))

    if not args.submit:
        print("[merge] Skipping SLURM submission (no --submit flag).")
        print(f"[merge] Inspect candidate: {merged_path}")
        return

    # Create workspace for merge run
    print("\n[merge] Creating merge workspace and submitting to SLURM...")
    merge_ws = merge_dir / "workspace"
    sys.path.insert(0, str(repo_root / "src"))
    from agent_workflow.utils.workspace import create_workspace

    create_workspace(
        autoresearch_dir=auto,
        workspace_path=merge_ws,
        branch_name=f"claude/{args.run_id}/merge",
        train_budget_seconds=600,
        run_id=args.run_id,
        agent_id="merge",
        results_root=results_dir,
        slurm_partition=args.slurm_partition,
        slurm_gres=args.slurm_gres,
        slurm_time=args.slurm_time,
        use_slurm=True,
    )
    (merge_ws / "train.py").write_text(merged)

    r = subprocess.run(
        ["bash", "submit_training.sh"],
        cwd=str(merge_ws),
        capture_output=True,
        text=True,
        timeout=30,
    )
    job_id = r.stdout.strip()
    print(f"[merge] SLURM job submitted: {job_id}")
    if not job_id.isdigit():
        print(f"[merge] ERROR: unexpected submit output: {r.stdout!r}\n{r.stderr!r}")
        sys.exit(1)

    print("[merge] Polling for completion...")
    status = poll_job(merge_ws, job_id)

    merge_val_bpb = None
    m = re.search(r"val_bpb:\s*([\d.]+)", status)
    if m:
        merge_val_bpb = float(m.group(1))

    results = {
        "best_individual_agent": overall_best_agent,
        "best_individual_val_bpb": overall_best_bpb,
        "merge_val_bpb": merge_val_bpb,
        "merge_won": (merge_val_bpb is not None and merge_val_bpb < overall_best_bpb),
        "delta_val_bpb": (
            round(merge_val_bpb - overall_best_bpb, 6)
            if merge_val_bpb is not None else None
        ),
        "changes": changes,
        "slurm_job_id": job_id,
    }
    (merge_dir / "merge_results.json").write_text(json.dumps(results, indent=2))

    print(f"\n=== MERGE RESULTS ===")
    print(f"  Best individual: {overall_best_agent} val_bpb={overall_best_bpb:.6f}")
    print(f"  Merged val_bpb:  {merge_val_bpb}")
    print(f"  Merge won:       {results['merge_won']}")
    print(f"  Delta:           {results['delta_val_bpb']}")


if __name__ == "__main__":
    main()
