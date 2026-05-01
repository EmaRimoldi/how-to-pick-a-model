"""Audit configured benchmark profile splits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.stateful_query_engine.harness.run_benchmark import load_instance_config

from vao.profile_splits import load_profile_splits, split_for_profile, summarize_profile_splits


def build_audit(profile_config: Path) -> dict[str, Any]:
    splits = load_profile_splits(profile_config)
    benchmark_profiles = load_instance_config()["profiles"]
    summary = summarize_profile_splits(splits, benchmark_profiles)
    profile_ids = sorted({profile_id for profiles in splits.values() for profile_id in profiles})
    summary["profile_details"] = {
        profile_id: {
            "split": split_for_profile(profile_id, splits),
            "seed": benchmark_profiles[profile_id]["seed"],
            "initial_size": benchmark_profiles[profile_id]["initial_size"],
            "key_space": benchmark_profiles[profile_id]["key_space"],
            "trace_length": benchmark_profiles[profile_id]["trace_length"],
            "families": benchmark_profiles[profile_id]["families"],
        }
        for profile_id in profile_ids
        if profile_id in benchmark_profiles
    }
    return summary


def write_markdown(audit: dict[str, Any], out: Path) -> None:
    lines = [
        "# Profile Split Audit",
        "",
        f"- Dev profiles: {', '.join(audit['splits'].get('dev', []))}",
        f"- Holdout profiles: {', '.join(audit['splits'].get('holdout', []))}",
        f"- Dev/holdout overlap: {audit['dev_holdout_overlap'] or 'none'}",
        f"- Dev/holdout seed overlap: {audit['dev_holdout_seed_overlap'] or 'none'}",
        "",
        "| profile | split | seed | initial_size | key_space | trace_length | families |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for profile_id, detail in sorted(audit["profile_details"].items()):
        lines.append(
            "| {profile} | {split} | {seed} | {initial_size} | {key_space} | {trace_length} | {families} |".format(
                profile=profile_id,
                split=detail["split"],
                seed=detail["seed"],
                initial_size=detail["initial_size"],
                key_space=detail["key_space"],
                trace_length=detail["trace_length"],
                families=", ".join(detail["families"]),
            )
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles_config", default="configs/profiles.yaml")
    parser.add_argument("--out", default="artifacts/profile_split_audit.json")
    parser.add_argument("--md_out", default="artifacts/profile_split_audit.md")
    args = parser.parse_args(argv)

    audit = build_audit(Path(args.profiles_config))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(audit, Path(args.md_out))
    print(json.dumps({"profiles": audit["counts"], "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
