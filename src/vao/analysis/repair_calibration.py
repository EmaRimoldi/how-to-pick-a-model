"""Audit terminal repair-calibration segments and report descriptive diagnostics.

No model calls, training, stopping decisions or claim of held-out policy value.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import json
import hashlib
import re
import subprocess
import zipfile
from pathlib import Path

import numpy as np

from vao.repair.pilot import audit, comparisons, file_hashes, rows
from vao.repair.records import save


POLICIES = ("continue_one", "restart_one", "continue_two_public_select",
            "restart_two_public_select", "mixed_two_public_select")


def read_json(path):
    return json.loads(path.read_text())


def lineage(leaf: Path) -> list[Path]:
    chain, seen = [], set()
    while True:
        if leaf.resolve() in seen:
            raise ValueError("Cyclic segment lineage")
        seen.add(leaf.resolve())
        chain.append(leaf)
        manifest = read_json(leaf / "manifest.json")
        link = manifest.get("freeze", {}).get("config", {}).get("continuation")
        if not link:
            return list(reversed(chain))
        leaf = Path(link["parent_run"])


def group_estimate(candidates: list[dict], draws: int) -> dict:
    """Missing action outcomes are bounded, never silently converted to failures."""
    if draws < 1 or any(type(r["full_pass"]) is not bool for r in candidates):
        raise ValueError("Require positive draws and observed boolean outcomes")
    outcomes = {(r["action"], r["draw"]): r["full_pass"] for r in candidates}
    if len(outcomes) != len(candidates) or any(a not in ("continue", "restart") or not 0 <= d < draws for a, d in outcomes):
        raise ValueError("Duplicate or undeclared action/draw")
    result = {}
    for action in ("continue", "restart"):
        values = [outcomes[action, draw] for draw in range(draws) if (action, draw) in outcomes]
        missing, correct = draws - len(values), sum(values)
        result[action] = {"observed": len(values), "correct": correct, "missing": missing,
                          "lower": correct / draws, "upper": (correct + missing) / draws}
    complete = len(outcomes) == 2 * draws
    differences = [int(outcomes["continue", d]) - int(outcomes["restart", d]) for d in range(draws)] if complete else None
    result.update(complete=complete,
        difference_lower=result["continue"]["lower"] - result["restart"]["upper"],
        difference_upper=result["continue"]["upper"] - result["restart"]["lower"],
        paired_draw_differences=differences,
        repeated_preference=("continue" if all(d > 0 for d in differences) else
                             "restart" if all(d < 0 for d in differences) else "none") if complete else None)
    return result


def mean(values):
    return float(np.mean(values)) if values else None


def descriptive_interval(values: list[float]) -> list[float] | None:
    """Resample bug-level paired means, not correlated checkpoint observations."""
    if len(values) < 2:
        return None
    rng = np.random.default_rng(261026)
    sampled = rng.choice(np.asarray(values, dtype=float), size=(5000, len(values)), replace=True).mean(axis=1)
    return [float(x) for x in np.quantile(sampled, [0.025, 0.975])]


def analyze(leaf: Path, *, allow_interrupted=False) -> dict:
    if not (leaf / "pilot-completion.json").exists():
        if not allow_interrupted or not (leaf / "interruption.json").exists():
            raise ValueError("Latest segment must be completed, or explicitly accepted as terminal/interrupted")
    paths = lineage(leaf)
    manifests = [read_json(p / "manifest.json") for p in paths]
    audits = [audit(p) for p in paths]
    modes = {m["mode"] for m in manifests}
    if len(modes) != 1:
        raise ValueError("Never pool scripted and model evidence")
    model_results = manifests[0]["model_results"]
    expected = manifests[0]["provenance"]
    if any(m["provenance"]["tasks"] != expected["tasks"] or m["provenance"]["design"] != expected["design"] for m in manifests):
        raise ValueError("Different tasks or sampling designs")
    design = expected["design"]
    observations, all_groups, policy_rows, trajectories = [], [], [], {}
    task_names, seen_attempts, generation_ids, admissions = {}, set(), set(), set()
    replay_timings, progress_rows = [], []
    for path, manifest in zip(paths, manifests):
        if path != leaf and not (path / "interruption.json").exists():
            raise ValueError("A predecessor must be a terminal interrupted segment")
        for event in rows(path / "ledger.jsonl"):
            if event["event"] == "reserve":
                if event["attempt_id"] in admissions:
                    raise ValueError("Repeated admission across segments")
                admissions.add(event["attempt_id"])
        for directory in sorted((path / "trajectories").glob("*")):
            if directory.name in trajectories:
                raise ValueError("A trajectory was restarted across segments")
            event = read_json(directory / "events" / "000000.json")
            task_obj = read_json(directory / "objects" / (event["objects"][0] + ".json"))
            index = int(directory.name.split("-")[1])
            task_hash = expected["tasks"][index]
            task_names[task_hash] = task_obj["public"]["task_id"]
            trajectories[directory.name] = {"path": directory, "task_hash": task_hash,
                "finished": (directory / "completion.json").exists(), "original_files": task_obj["public"]["files"]}
        for row in rows(path / "observations.jsonl"):
            if row["attempt_id"] in seen_attempts:
                raise ValueError("Repeated observation across segments")
            seen_attempts.add(row["attempt_id"])
            receipt = read_json(path / "receipts" / (row["attempt_id"] + ".json"))
            if model_results:
                if receipt["generation_id"] in generation_ids:
                    raise ValueError("Repeated provider generation identity")
                generation_ids.add(receipt["generation_id"])
            directory = trajectories[row["trajectory"]]["path"]
            public_pass = (read_json(directory / "objects" / (row["public"] + ".json"))["result"]["passed"]
                           if row["public"] else False)
            def obj(ref):
                return read_json(directory / "objects" / (ref + ".json"))
            checkpoint = obj(row["checkpoint_before"])
            before = obj(checkpoint["evaluation"])["result"]
            after = obj(row["public"])["result"] if row["public"] else None
            branch = obj(row["branch"])
            progress_rows.append({"attempt_id": row["attempt_id"], "task_hash": row["task_hash"],
                "trajectory": row["trajectory"], "phase": row["phase"], "action": branch["action"],
                "public_passed_before": before["passed_cases"],
                "public_passed_after": after["passed_cases"] if after else None,
                "public_total_cases": before["total_cases"],
                "public_change": after["passed_cases"] - before["passed_cases"] if after else None,
                "no_op_from_supplied_artifact": row["artifact"] == branch["starting_artifact"] if row["artifact"] else None,
                "status": row["status"]})
            observations.append({**row, "public_pass": public_pass, "segment": str(path)})
        all_groups.extend(rows(path / "groups.jsonl"))
        for row in comparisons(path):
            replay_timings.append({"group": row["group"], "policy": row["policy"],
                                   "seconds": row.pop("replay_selection_seconds")})
            policy_rows.append(row)
    by_id = {r["attempt_id"]: r for r in observations}
    groups = []
    for group in all_groups:
        candidates = [r for r in observations if r.get("group") == group["group"]]
        task_hash = trajectories[group["trajectory"]]["task_hash"]
        trajectory = trajectories[group["trajectory"]]
        object_root = trajectory["path"] / "objects"
        checkpoint = read_json(object_root / (group["checkpoint"] + ".json"))
        current_files = read_json(object_root / (checkpoint["artifact"] + ".json"))["files"]
        groups.append({"group": group["group"], "task_hash": task_hash,
                       "identical_action_input_files": current_files == trajectory["original_files"],
                       "trajectory": group["trajectory"], "depth": group["depth"],
                       **group_estimate(candidates, design["draws_per_action"])})
    by_group = {g["group"]: g for g in groups}
    if len(by_group) != len(groups):
        raise ValueError("Duplicate checkpoint group")
    common = {g["group"] for g in groups if g["complete"]}
    task_table = []
    for index, task_hash in enumerate(expected["tasks"]):
        prefixes = [r for r in observations if r["task_hash"] == task_hash and r["phase"] == "prefix"]
        task_trajectories = [t for t in trajectories.values() if t["task_hash"] == task_hash]
        scoped = [g for g in groups if g["task_hash"] == task_hash]
        changes = [r for r in progress_rows if r["task_hash"] == task_hash and r["phase"] == "prefix"]
        task_table.append({"task_index": index, "task_hash": task_hash,
            "prefix_attempts_observed": len(prefixes),
            "prefix_public_improvements": sum(r["public_change"] is not None and r["public_change"] > 0 for r in changes),
            "prefix_public_regressions": sum(r["public_change"] is not None and r["public_change"] < 0 for r in changes),
            "prefix_no_ops": sum(r["no_op_from_supplied_artifact"] is True for r in changes),
            "task": task_names.get(task_hash, f"unobserved-task-{index:03d}"),
            "planned_prefixes": design["prefix_replicates"], "started_prefixes": len(task_trajectories),
            "finished_trajectories": sum(t["finished"] for t in task_trajectories),
            "prefix_successes_observed": len({r["trajectory"] for r in prefixes if r["full_pass"]}),
            "prefix_format_errors": sum(r["status"] == "format_error" for r in prefixes),
            "prefix_public_false_positives": sum(r["public_pass"] and not r["full_pass"] for r in prefixes),
            "eligible_checkpoints": len(scoped), "complete_checkpoints": sum(g["complete"] for g in scoped),
            "continue_minus_restart_lower": mean([g["difference_lower"] for g in scoped]),
            "continue_minus_restart_upper": mean([g["difference_upper"] for g in scoped])})
    policy_table = []
    selected_false_positives = {}
    baseline = {r["group"]: r for r in policy_rows if r["policy"] == "continue_one" and r["group"] in common}
    for policy in POLICIES:
        selected = [r for r in policy_rows if r["policy"] == policy and r["group"] in common]
        per_bug = defaultdict(list)
        for row in selected:
            per_bug[by_group[row["group"]]["task_hash"]].append(row)
        success = [mean([int(r["full_pass"]) for r in values]) for values in per_bug.values()]
        costs = [mean([float(r["cost_usd"]) for r in values]) for values in per_bug.values()]
        differences = [mean([int(r["full_pass"]) - int(baseline[r["group"]]["full_pass"]) for r in values]) for values in per_bug.values()]
        selected_false_positives[policy] = sum(by_id[r["selected_attempt"]]["public_pass"] and not r["full_pass"] for r in selected)
        policy_table.append({"policy": policy, "common_complete_checkpoints": len(selected), "bugs": len(per_bug),
            "bug_balanced_success": mean(success), "bug_balanced_prefix_plus_candidate_cost_usd": mean(costs),
            "difference_from_continue_one": mean(differences),
            "descriptive_95pct_bug_bootstrap_difference": descriptive_interval(differences),
            "selected_public_false_positives": selected_false_positives[policy]})
    own_commitments = [Decimal(a["conservative_committed_usd"]) - Decimal(a["carried_committed_usd"]) for a in audits]
    total = sum(own_commitments, Decimal(0))
    if total != Decimal(audits[-1]["conservative_committed_usd"]):
        raise ValueError("Cumulative accounting was omitted or counted twice")
    known = sum((Decimal(a["settled_usd"]) for a in audits), Decimal(0))
    pending = {key: amount for a in audits for key, amount in a["pending"].items()}
    preference = Counter(g["repeated_preference"] for g in groups if g["complete"])
    return {"schema_version": 1, "model_results": model_results,
        "evidence_status": "incomplete_development_calibration" if pending or len(common) != len(groups) or not (leaf / "pilot-completion.json").exists() or any(not t["finished"] for t in trajectories.values()) or len(trajectories) < len(expected["tasks"])*design["prefix_replicates"] else "development_calibration",
        "segments": [{"path": str(p), "mode": m["mode"], "audit": a,
                      "source_commit": m.get("freeze", {}).get("source_commit"), "file_hashes": file_hashes(p)} for p, m, a in zip(paths, manifests, audits)],
        "tasks": len(expected["tasks"]), "planned_prefixes": len(expected["tasks"])*design["prefix_replicates"],
        "started_prefixes": len(trajectories), "finished_trajectories": sum(t["finished"] for t in trajectories.values()),
        "admitted_calls": len(admissions), "observations": len(observations), "unknown_reservations": pending,
        "currency": manifests[0]["currency"], "known_generation_charges_usd": str(known),
        "conservative_committed_usd": str(total), "cumulative_cap_usd": manifests[0]["limit_usd"],
        "eligible_checkpoints": len(groups), "complete_checkpoints": len(common),
        "repeated_preferences": dict(preference),
        "identical_action_input_checkpoints": sum(g["identical_action_input_files"] for g in groups),
        "progress_rows": progress_rows,
        "task_table": task_table, "group_table": groups, "policy_table": policy_table,
        "policy_rows": policy_rows,
        "replay_selection_timings": replay_timings,
        "timing_note": "Replay timings are fresh machine-dependent measurements; exclude this field from reproducibility equality. No selector inference cost is claimed.",
        "observed_public_false_positives": sum(r["public_pass"] and not r["full_pass"] for r in observations),
        "format_errors": sum(r["status"] == "format_error" for r in observations),
        "limitations": ["All tasks are inspected development adaptations; no held-out selector evaluation.",
            "Selected development tasks cannot establish generalization to other bugs/projects. The intended real pool has ten of twelve bugs from one upstream project.",
            "Policy table uses common complete observed checkpoints, averages within bug then across bugs, and can be biased by missing states.",
            "Missing-outcome bounds condition on observed eligible checkpoints; unobserved future states are not identified.",
            "Bootstrap intervals resample bug-level paired means (5000 draws, seed 261026); descriptive, no confirmatory p-values.",
            "One versus two candidates have the same allowance but different actual spending; these are one-checkpoint diagnostics, not deployed multi-step policies.",
            "Public selection can choose an incorrect candidate. No evaluator oracle is used to select answers.",
            "Two draws and a tiny task pool do not establish learnable or generalizable action complementarity."]}


def render(report: dict) -> str:
    def f(value, places=3):
        return "—" if value is None else f"{value:.{places}f}"
    title = "Gemma 3 4B development calibration" if report["model_results"] else "Scripted engineering report — not model evidence"
    lines = [f"# {title}", "", f"Status: **{report['evidence_status']}**. No fitted or held-out selector result.", "",
        f"{report['observations']} saved responses / {report['admitted_calls']} admissions; "
        f"{report['finished_trajectories']}/{report['planned_prefixes']} complete trajectories across {report['tasks']} selected tasks.",
        f"Known generation charges: {report['known_generation_charges_usd']} {report['currency']}; "
        f"conservative commitment including unknown requests: {report['conservative_committed_usd']} against {report['cumulative_cap_usd']}.", "",
        f"Observed failed checkpoints: {report['eligible_checkpoints']}; complete matched checkpoints: {report['complete_checkpoints']}.",
        f"Format failures: {report['format_errors']}. Public-test false positives among all observed artifacts: {report['observed_public_false_positives']}.", "",
        f"Checkpoints with identical continue/restart input files: {report['identical_action_input_checkpoints']} (retained as controls, not evidence of a distinct artifact intervention).",
        "", "## Per-bug coverage and action difference", "",
        "C−R bounds include missing draws at observed checkpoints; they are not confidence intervals. Prefix successes refer to observed full public+evaluator passes.", "",
        "| Task | Prefix success observed | Finished / planned | Checkpoints complete / observed | C−R lower | C−R upper |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for t in report["task_table"]:
        lines.append(f"| {t['task']} | {t['prefix_successes_observed']} | {t['finished_trajectories']}/{t['planned_prefixes']} | {t['complete_checkpoints']}/{t['eligible_checkpoints']} | {f(t['continue_minus_restart_lower'])} | {f(t['continue_minus_restart_upper'])} |")
    lines += ["", "## Prefix progress", "",
        "Changes compare the generated prefix with its immediately preceding public feedback. Format errors have no score change. No-op means byte-identical supplied files.", "",
        "| Task | Prefix attempts | Improvements | Regressions | No-ops | Format errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for t in report["task_table"]:
        lines.append(f"| {t['task']} | {t['prefix_attempts_observed']} | {t['prefix_public_improvements']} | {t['prefix_public_regressions']} | {t['prefix_no_ops']} | {t['prefix_format_errors']} |")
    lines += ["", "## Costed diagnostic policies", "",
        "Identical common complete checkpoints for all policies; equal weight per contributing bug. Costs include the prefix once and every generated candidate, even the discarded one. Recorded local verifier timings remain in policy_rows; fresh replay-selection timings are separate machine-dependent measurements, excluded from reproducibility equality.", "",
        "| Policy | Bugs | Checkpoints | Selected full success | Mean API cost | Difference from continue-one | Descriptive paired 95% interval |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for p in report["policy_table"]:
        interval = p["descriptive_95pct_bug_bootstrap_difference"]
        interval_text = "—" if interval is None else f"[{f(interval[0])}, {f(interval[1])}]"
        lines.append(f"| {p['policy']} | {p['bugs']} | {p['common_complete_checkpoints']} | {f(p['bug_balanced_success'])} | {f(p['bug_balanced_prefix_plus_candidate_cost_usd'], 6)} | {f(p['difference_from_continue_one'])} | {interval_text} |")
    lines += ["", "## Replication diagnostic", "", "Strict advantage in both paired draws at the same checkpoint: " + json.dumps(report["repeated_preferences"], sort_keys=True) + ". A single differing draw is not a replicated action preference.", "", "## Limits", ""]
    lines.extend("- " + item for item in report["limitations"])
    return "\n".join(lines) + "\n"



def export_evidence(leaf: Path, output: Path) -> dict:
    """Package terminal immutable JSON records and inert, hash-checked sources."""
    paths = lineage(leaf)
    if not ((leaf / "pilot-completion.json").exists() or (leaf / "interruption.json").exists()):
        raise ValueError("Cannot export a live bank")
    entries, source_entries = {}, {}
    for path in paths:
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "runs":
            raise ValueError("Evidence paths must retain safe original runs/ layout")
        audit(path)
        manifest = read_json(path / "manifest.json")
        for file in sorted(path.rglob("*")):
            if file.is_symlink():
                raise ValueError("No symlinks in evidence")
            if file.is_file():
                if file.suffix not in (".json", ".jsonl"):
                    raise ValueError("Only inert JSON records may be packaged")
                entries[file.as_posix()] = file.read_bytes()
        commit = manifest.get("freeze", {}).get("source_commit")
        if commit:
            if not re.fullmatch(r"[a-f0-9]{40}", commit):
                raise ValueError("Invalid source commit")
            for name, expected_hash in manifest["provenance"]["sources"].items():
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Invalid source provenance path")
                content = subprocess.run(["git", "show", f"{commit}:src/vao/{name}"],
                                         check=True, capture_output=True).stdout
                if hashlib.sha256(content).hexdigest() != expected_hash:
                    raise ValueError("Frozen source does not match committed source")
                source_entries[f"frozen-sources/{commit}/{name}.txt"] = content
    entries.update(source_entries)
    if any(re.search(rb"sk-or-v1-[a-f0-9]{64}", data) for data in entries.values()):
        raise ValueError("Credential-shaped text prevents export")
    archive = output / "evidence.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, data)
    manifest = {"leaf": leaf.as_posix(), "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(entries.items())},
                "source_format": "Frozen source files are inert .txt records; do not execute model artifacts.",
                "reproduction": "Verify archive hash, extract into a fresh directory, change to that directory and run the installed report_repair_calibration entry point on leaf. Relative ancestor paths must remain unchanged. Exclude replay_selection_timings from equality."}
    save(output / "evidence-manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-interrupted", action="store_true")
    parser.add_argument("--export-evidence", action="store_true")
    args = parser.parse_args()
    result = analyze(args.input, allow_interrupted=args.allow_interrupted)
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "analysis.json", result)
    (args.output / "REPORT.md").write_text(render(result))
    if args.export_evidence:
        export_evidence(args.input, args.output)
    print(json.dumps({k: result[k] for k in ("evidence_status", "model_results", "observations", "complete_checkpoints", "conservative_committed_usd")}, indent=2))


if __name__ == "__main__":
    main()
