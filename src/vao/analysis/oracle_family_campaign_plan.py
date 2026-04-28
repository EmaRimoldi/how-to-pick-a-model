"""Plan and materialize a statistically powered oracle-family campaign."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from vao.analysis.task_mode_decomposition import load_attempt_records


def build_campaign_plan(config_path: Path, *, roots: list[Path], out_dir: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    campaign = dict(config.get("campaign") or {})
    models = list(((config.get("models") or {}).get("include") or []))
    task_modes = list(campaign.get("task_modes") or [])
    pilot_seeds = [int(item) for item in (campaign.get("pilot_seeds") or [])]
    holdout_seeds = [int(item) for item in (campaign.get("holdout_seeds") or [])]
    target_trials = int(campaign.get("target_trials_per_cell") or 30)
    output_root = str(((config.get("output") or {}).get("root")) or "runs/oracle_family_5model")

    completed = load_attempt_records(
        roots,
        success_threshold=float(campaign.get("success_threshold") or 0.95),
        success_mode=str(campaign.get("success_mode") or "relative_improvement"),
        improvement_threshold=float(campaign.get("improvement_threshold") or 0.05),
    )
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    existing_seeds: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    for record in completed:
        campaign_model = record.model_alias or record.model_id
        key = (record.split, record.task_mode_true, campaign_model)
        counts[key] += 1
        if record.instance_seed is not None:
            existing_seeds[key].add(int(record.instance_seed))

    rows: list[dict[str, Any]] = []
    commands_by_group: dict[tuple[str, str], dict[str, Any]] = {}
    missing_rows: list[dict[str, Any]] = []
    for split, seed_pool in [("pilot", pilot_seeds), ("holdout", holdout_seeds)]:
        for model in models:
            selected_seeds: set[int] = set()
            families_needed: set[str] = set()
            missing_by_family: dict[str, list[int]] = {}
            for task_mode in task_modes:
                key = (split, task_mode, model)
                complete = counts.get(key, 0)
                missing = max(0, target_trials - complete)
                available = [seed for seed in seed_pool if seed not in existing_seeds.get(key, set())]
                chosen = available[:missing]
                missing_by_family[task_mode] = chosen
                if chosen:
                    selected_seeds.update(chosen)
                    families_needed.add(task_mode)
                rows.append(
                    {
                        "split": split,
                        "task_mode_true": task_mode,
                        "model_id": model,
                        "completed_trials": complete,
                        "target_trials": target_trials,
                        "missing_trials": missing,
                        "available_new_seeds": len(available),
                        "planned_new_seeds": len(chosen),
                    }
                )
                for seed in chosen:
                    missing_rows.append(
                        {
                            "split": split,
                            "task_mode_true": task_mode,
                            "model_id": model,
                            "seed": seed,
                        }
                    )
            if selected_seeds and families_needed:
                commands_by_group[(split, model)] = {
                    "split": split,
                    "model": model,
                    "families": sorted(families_needed),
                    "seeds": sorted(selected_seeds),
                }

    out_dir.mkdir(parents=True, exist_ok=True)
    status_frame = pd.DataFrame(rows)
    missing_frame = pd.DataFrame(missing_rows)
    status_frame.to_csv(out_dir / "campaign_status.csv", index=False)
    missing_frame.to_csv(out_dir / "missing_runs.csv", index=False)

    commands = [
        _command_for_group(group, config_path=config_path, output_root=output_root)
        for _, group in sorted(commands_by_group.items())
    ]
    (out_dir / "run_commands.sh").write_text("\n".join(commands) + ("\n" if commands else ""), encoding="utf-8")

    result = {
        "config_path": str(config_path),
        "output_root": output_root,
        "target_trials_per_cell": target_trials,
        "models": models,
        "task_modes": task_modes,
        "planned_command_count": len(commands),
        "planned_additional_runs": int(status_frame["missing_trials"].sum()) if not status_frame.empty else 0,
        "status_rows": rows,
    }
    (out_dir / "campaign_plan.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_report(result, status_frame, out_dir / "report.md")
    return result


def _command_for_group(group: dict[str, Any], *, config_path: Path, output_root: str) -> str:
    families = ",".join(group["families"])
    seeds = ",".join(str(item) for item in group["seeds"])
    run_prefix = "oracle_family_5model"
    return (
        "PYTHONPATH=src:. python3 -m vao.analysis.oracle_family_pilot "
        f"--config {config_path} "
        f"--models {group['model']} "
        f"--families {families} "
        f"--seeds {seeds} "
        f"--split {group['split']} "
        "--steps 1 "
        f"--run-prefix {run_prefix} "
        f"--output-root {output_root}"
    )


def _write_report(result: dict[str, Any], frame: pd.DataFrame, path: Path) -> None:
    lines = [
        "# Oracle-Family 5-Model Campaign Plan",
        "",
        f"- Target trials per cell: `{result['target_trials_per_cell']}`",
        f"- Planned command count: `{result['planned_command_count']}`",
        f"- Planned additional runs: `{result['planned_additional_runs']}`",
        "",
        "## Cell Status",
        "",
    ]
    for _, row in frame.sort_values(["split", "task_mode_true", "model_id"]).iterrows():
        lines.append(
            f"- `{row['split']} / {row['task_mode_true']} / {row['model_id']}`: "
            f"completed=`{row['completed_trials']}`, missing=`{row['missing_trials']}`, "
            f"planned=`{row['planned_new_seeds']}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    result = build_campaign_plan(
        Path(args.config),
        roots=[Path(item) for item in args.runs],
        out_dir=Path(args.out_dir),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
