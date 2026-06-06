"""Wrapper around the official SWE-bench evaluation harness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def build_command(
    *,
    dataset_name: str,
    split: str,
    predictions_path: Path,
    run_id: str,
    max_workers: int,
    timeout: int,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        dataset_name,
        "--split",
        split,
        "--predictions_path",
        str(predictions_path),
        "--run_id",
        run_id,
        "--max_workers",
        str(max_workers),
        "--timeout",
        str(timeout),
    ]


def _validate_predictions(path: Path) -> dict[str, int]:
    rows = 0
    missing = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows += 1
            payload = json.loads(line)
            for key in ("instance_id", "model_patch", "model_name_or_path"):
                if key not in payload:
                    missing += 1
    return {"rows": rows, "missing_required_fields": missing}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-name", default="princeton-nlp/SWE-Bench_Verified")
    parser.add_argument("--split", default="test")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--run-id", default="swebench_orchestration_eval")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    predictions_path = Path(args.predictions)
    validation = _validate_predictions(predictions_path)
    command = build_command(
        dataset_name=args.dataset_name,
        split=args.split,
        predictions_path=predictions_path,
        run_id=args.run_id,
        max_workers=args.max_workers,
        timeout=args.timeout,
    )
    result = {
        "prediction_validation": validation,
        "command": command,
        "execute": args.execute,
        "swebench_installed": importlib.util.find_spec("swebench") is not None,
    }
    if validation["missing_required_fields"]:
        raise SystemExit(json.dumps(result, indent=2, sort_keys=True))
    if args.execute:
        if not result["swebench_installed"]:
            raise SystemExit(
                "The `swebench` package is not installed. Install the official harness, "
                "then rerun with --execute. Command:\n" + " ".join(command)
            )
        proc = subprocess.run(command, text=True)
        result["returncode"] = proc.returncode
        print(json.dumps(result, indent=2, sort_keys=True))
        raise SystemExit(proc.returncode)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
