"""Generate TSV task manifests for AutoResearch CIFAR-10 Slurm arrays."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_MODES = ["cnn_compact", "mlp_flat", "resnet_micro"]
DEFAULT_WORKERS = ["gpt_5_3_codex", "gpt_5_4", "gpt_5_4_mini"]


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--modes", default=",".join(DEFAULT_MODES))
    parser.add_argument("--workers", default=",".join(DEFAULT_WORKERS))
    parser.add_argument("--seed-start", type=int, required=True)
    parser.add_argument("--runs-per-cell", type=int, required=True)
    parser.add_argument("--split", default="pilot")
    args = parser.parse_args()

    modes = _csv(args.modes)
    workers = _csv(args.workers)
    seeds = [args.seed_start + offset for offset in range(args.runs_per_cell)]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        handle.write("task_id\tmode\tworker\tseed\tsplit\n")
        task_id = 0
        for mode in modes:
            for worker in workers:
                for seed in seeds:
                    handle.write(f"{task_id}\t{mode}\t{worker}\t{seed}\t{args.split}\n")
                    task_id += 1
    print(f"wrote {task_id} tasks to {output}")


if __name__ == "__main__":
    main()
