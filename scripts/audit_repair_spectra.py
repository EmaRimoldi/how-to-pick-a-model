"""Offline public-spectrum feasibility on frozen exposed development artifacts.

collect executes only local sandboxed cases; replay executes no candidate code.
Neither command imports a model client or prepares a provider request.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from vao.repair.diagnostics import binding
from vao.repair.environment import canonical
from vao.repair.spectra import CoverageVerifier, acquire_spectrum, analyze_spectrum

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("experiments/python-repair/checkpoint-environment/results/acquisition-preparation-20261027/evidence.zip")
SOURCE_SHA = "353394a00c57f206c7f29d647ba722cc3731f1c61083bb39672f814c674f00e3"
SLUGS = ("scrapy-002", "scrapy-036", "luigi-010", "tornado-005", "thefuck-022", "thefuck-029", "scrapy-026", "scrapy-040")
GENERATED_SOURCE = Path("experiments/python-repair/checkpoint-environment/results/contract-gemma27b-20261026/evidence.zip")
GENERATED_SHA = "f2a3b228425ee98a8a5bbc0422f6bdb486d44eeb1a2a86d4cabeba309103c913"
GENERATED_SLUGS = ("youtube-dl-003", "youtube-dl-011", "youtube-dl-013", "youtube-dl-020",
                   "youtube-dl-027", "youtube-dl-031", "youtube-dl-032", "youtube-dl-033",
                   "youtube-dl-042", "youtube-dl-043", "httpie-005", "tornado-009")
GENERATED_FAILURES = tuple(x for i, x in enumerate(GENERATED_SLUGS) if i in (0, 2, 3, 5, 7, 8, 9, 10))
RUNTIME = ("scripts/audit_repair_spectra.py", "src/vao/repair/coverage_worker.py", "src/vao/repair/spectra.py",
           "src/vao/repair/verifier.py", "src/vao/repair/diagnostics.py", "src/vao/repair/environment.py",
           "src/vao/decisions/verification.py")


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generated_inputs():
    """Project the twelve original JSON candidates using public fields only.

    Do not import the study preparer: its records carry private evaluator cases
    and full-pass labels. Neither field is read for eligibility or acquisition.
    """
    archive = ROOT / GENERATED_SOURCE
    manifest = json.loads(archive.with_name("evidence-manifest.json").read_text())
    if digest(archive) != GENERATED_SHA or manifest["archive_sha256"] != GENERATED_SHA:
        raise ValueError("Closed generated-artifact source changed")
    records = []
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist()) != len(set(z.namelist())) or set(z.namelist()) != set(manifest["files"]):
            raise ValueError("Generated source archive members differ")
        for name, expected in manifest["files"].items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise ValueError("Generated source member changed")
        packet = json.loads(z.read("collection/manifest.json"))["freeze"]["packet"]
        rows = [json.loads(x) for x in z.read("collection/observations.jsonl").splitlines()]
        if "collection/pilot-completion.json" not in z.namelist() or len(rows) != 36:
            raise ValueError("Generated source must be the complete closed bank")
        for row in sorted(rows, key=lambda r: r["task_index"]):
            if row["contract"] != "json_current":
                continue
            prefix = f"collection/cells/{row['attempt_id']}/objects/"
            public = packet["tasks"][row["task_index"]]["public"]
            public["files"] = json.loads(z.read(prefix + row["artifact"] + ".json"))["files"]
            public["provenance"] = {"kind": "previously_exposed_model_generated_candidate"}
            result = json.loads(z.read(prefix + row["public"] + ".json"))["result"]
            feedback = {k: result[k] for k in ("passed", "passed_cases", "total_cases", "cases")}
            records.append({"id": public["task_id"].rsplit("/", 1)[-1], "public": public,
                            "source_attempt_id": row["attempt_id"], "source_artifact": row["artifact"],
                            "source_public_result": row["public"],
                            "stored": {"binding": binding(public, public["files"]), "feedback": feedback,
                                       "verifier_seconds": result["verifier_seconds"]}})
    if [r["id"] for r in records] != list(GENERATED_SLUGS):
        raise ValueError("All twelve original JSON candidates must be retained")
    if [r["id"] for r in records if not r["stored"]["feedback"]["passed"]] != list(GENERATED_FAILURES):
        raise ValueError("Historical public-only eligibility changed")
    return records


def inventory(records):
    return [{"id": r["id"], "binding": r["stored"]["binding"],
             "public_passed": r["stored"]["feedback"]["passed"],
             "public_passed_cases": r["stored"]["feedback"]["passed_cases"],
             "public_total_cases": r["stored"]["feedback"]["total_cases"],
             "eligibility": "public_pass_no_trigger" if r["stored"]["feedback"]["passed"] else "public_failure"}
            for r in records]


def source_inputs(bank="original"):
    if bank == "generated":
        return generated_inputs()
    if bank != "original":
        raise ValueError("Unknown source bank")
    archive = ROOT / SOURCE
    if digest(archive) != SOURCE_SHA:
        raise ValueError("Source archive changed")
    records = []
    with zipfile.ZipFile(archive) as z:
        for slug in SLUGS:
            name = f"preparation/{slug}/public.json"
            raw = z.read(name)
            public = json.loads(raw)
            # Exclude upstream fixed-file links/hashes, evaluator pools, old model
            # outcomes and fault annotations from the diagnostic input.
            public["provenance"] = {"kind": "previously_exposed_original_bug", "source_member": name}
            records.append({"id": slug, "source_member": name, "source_member_sha256": hashlib.sha256(raw).hexdigest(),
                            "public": public, "stored": json.loads(z.read(f"preparation/{slug}/observation.json"))})
    return records


def summarize(evidence):
    generated = evidence.get("bank", "original") == "generated"
    expected_ids = GENERATED_FAILURES if generated else SLUGS
    if [r["id"] for r in evidence["records"]] != list(expected_ids):
        raise ValueError("The complete eight-artifact denominator must be preserved")
    rows = [{"id": r["id"], **analyze_spectrum(r["public"], r["acquisition"])} for r in evidence["records"]]
    available = [r for r in rows if r["available"]]
    report = {"schema_version": 1, "kind": "offline_diagnostic_feasibility", "api_calls": 0,
            "artifacts": len(rows), "available": len(available),
            "distinguishes_failing_executed_lines": sum(r["metrics"]["distinguishes_failing_executed_lines"] for r in available),
            "all_public_cases": sum(r["public_cases"] for r in rows),
            "additional_executions": sum(r["additional_executions"] for r in rows),
            "execution_seconds": sum(r["seconds"] for r in rows),
            "preflight_executions": 1, "records": rows,
            "limits": ["Original buggy artifacts, not model-generated failed checkpoints; all development-exposed.",
                       "Ranks correlate line execution with existing public labels; they do not locate a known fault.",
                       "No reference patch or private evaluator used; no repair, selection or benefit measured.",
                       "Only single-threaded entrypoint calls after module import are instrumented.",
                       "Python line events do not show sub-line data dependencies, C internals or absent code.",
                       "No truncated coverage or partial suite is scored; all failures remain in the denominator.",
                       "Elapsed time is machine-specific and is not a model cost or equal-total-budget experiment.",
                       "Retain whole tie groups; a small top tie group is not a criterion to enable model collection."]}
    if generated:
        report.update(bank="generated", source_candidates=12, no_public_trigger=4,
                      candidate_inventory=evidence["candidate_inventory"])
        report["limits"][0] = "Previously exposed Gemma 3 27B json_current failed candidates; eight public failures out of twelve candidates, not unseen policy evaluation."
        report["limits"].append("Different bugs and source states from the original-bug audit; no causal comparison between the two audits.")
    return report


def render(report):
    lines = ["# Public coverage feasibility audit", "", "Offline development audit; no model calls or efficacy inference.", "",
             "| Original bug | Pass/fail cases | Failing-executed lines | Positive score groups | Top-score tie |",
             "| --- | ---: | ---: | ---: | ---: |"]
    if report.get("bank") == "generated":
        lines[0] = "# Public coverage on model-generated failed checkpoints"
        lines[4] = lines[4].replace("Original bug", "Generated checkpoint")
        lines[2] += " Twelve source candidates retained; four pass public tests and do not trigger acquisition."
    for r in report["records"]:
        if not r["available"]:
            lines.append(f"| {r['id']} | unavailable | — | — | — |")
            continue
        m = r["metrics"]
        lines.append(f"| {r['id']} | {m['passing_cases']}/{m['failing_cases']} | {m['failing_executed_lines']} | {m['positive_score_groups']} | {m['top_tie_lines']} |")
    lines += ["", f"{report['available']}/{report['artifacts']} complete spectra; "
              f"{report['distinguishes_failing_executed_lines']}/{report['artifacts']} distinguish scores among lines executed by failing cases.",
              f"{report['all_public_cases']} public cases; {report['additional_executions']} additional executions plus one sandbox preflight; "
              f"{report['execution_seconds']:.3f} seconds in the saved acquisition.", "", *[f"- {s}" for s in report["limits"]], ""]
    return "\n".join(lines)


def collect(output, bank="original"):
    candidates = source_inputs(bank)
    records = [r for r in candidates if not r["stored"]["feedback"]["passed"]]
    source, source_sha = (GENERATED_SOURCE, GENERATED_SHA) if bank == "generated" else (SOURCE, SOURCE_SHA)
    runtime = {p: digest(ROOT / p) for p in RUNTIME}
    output.mkdir(parents=True, exist_ok=False)
    save(output / "plan.json", {"source_archive": str(source), "source_sha256": source_sha,
                               "bank": bank, "candidate_inventory": inventory(candidates),
                               "ids": [r["id"] for r in records], "runtime": runtime, "api_calls_enabled": False,
                               "recorded_before_execution": datetime.now(timezone.utc).isoformat()})
    verifier = CoverageVerifier()
    preflight = verifier.preflight()
    for record in records:
        record["acquisition"] = acquire_spectrum(record["public"], record["stored"], verifier)
        save(output / f"{record['id']}.json", record)
        print(json.dumps({"id": record["id"], "executions": record["acquisition"]["additional_executions"]}), flush=True)
    if runtime != {p: digest(ROOT / p) for p in RUNTIME}:
        raise ValueError("Runtime changed during local acquisition")
    evidence = {"schema_version": 1, "source_archive": str(source), "source_sha256": source_sha,
                "bank": bank, "candidate_inventory": inventory(candidates),
                "runtime": runtime, "python": sys.version, "preflight": preflight, "records": records}
    save(output / "evidence.json", evidence)
    report = summarize(evidence)
    save(output / "analysis.json", report)
    (output / "REPORT.md").write_text(render(report))
    source_dir = output / "source"
    source_dir.mkdir()
    for name in RUNTIME:
        (source_dir / (name.replace("/", "__") + ".txt")).write_bytes((ROOT / name).read_bytes())
    save(output / "manifest.json", {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob("*")) if p.is_file()})
    return report


def replay(output):
    if (output / "evidence.zip").exists():
        outer = json.loads((output / "archive-manifest.json").read_text())
        if outer != {p.name: digest(p) for p in output.iterdir() if p.is_file() and p.name != "archive-manifest.json"}:
            raise ValueError("Published audit archive changed")
        with zipfile.ZipFile(output / "evidence.zip") as z:
            if len(z.namelist()) != len(set(z.namelist())):
                raise ValueError("Repeated archive members")
            data = {name: z.read(name) for name in z.namelist()}
        for name in ("analysis.json", "REPORT.md"):
            if (output / name).read_bytes() != data[name]:
                raise ValueError("Visible report differs from archived evidence")
    else:
        data = {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    manifest = json.loads(data["manifest.json"])
    actual = {name: hashlib.sha256(raw).hexdigest() for name, raw in data.items() if name != "manifest.json"}
    if actual != manifest:
        raise ValueError("Audit evidence files changed")
    evidence = json.loads(data["evidence.json"])
    candidates = source_inputs(evidence.get("bank", "original"))
    originals = [r for r in candidates if not r["stored"]["feedback"]["passed"]]
    if "candidate_inventory" in evidence and evidence["candidate_inventory"] != inventory(candidates):
        raise ValueError("Source eligibility inventory changed")
    for recorded, original in zip(evidence["records"], originals):
        if {k: v for k, v in recorded.items() if k != "acquisition"} != original:
            raise ValueError("Published public input differs from the source archive")
    report = summarize(evidence)
    if canonical(report) != canonical(json.loads(data["analysis.json"])):
        raise ValueError("Saved analysis does not reproduce")
    if render(report) != data["REPORT.md"].decode():
        raise ValueError("Saved report does not reproduce")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("collect", "replay"))
    parser.add_argument("--bank", choices=("original", "generated"), default="original",
                        help="Collection source; replay always uses the saved source identity")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = collect(args.output, args.bank) if args.mode == "collect" else replay(args.output)
    print(json.dumps({k: v for k, v in report.items() if k not in {"records", "limits"}}, indent=2))


if __name__ == "__main__":
    main()
