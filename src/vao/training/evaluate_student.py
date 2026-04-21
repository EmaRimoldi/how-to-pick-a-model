"""Post-trained student evaluation scaffold."""

from __future__ import annotations

import argparse
import json


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            {
                "status": "not_started",
                "reason": "student evaluation scaffold; run vao.orchestrator with an adapter-backed model when weights are available",
                "adapter": args.adapter,
                "config": args.config,
                "out": args.out,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
