#!/usr/bin/env python3
"""Lightweight availability smoke test for the AutoResearch model menu.

This script intentionally avoids importing the project Python packages so it can
run on the gateway host even when the repo's runtime Python version differs
from the system interpreter. It validates the configured model menu by issuing a
single tiny completion through the configured CLI backends.
"""

import argparse
import json
import subprocess
import sys

from pathlib import Path

import yaml

CODEX_PROMPT = 'Reply with a one-line JSON object: {"ok": true, "backend": "codex"}'
CLAUDE_PROMPT = 'Reply with a one-line JSON object: {"ok": true, "backend": "claude"}'


def load_yaml(path):
    with open(path, "r") as handle:
        return yaml.safe_load(handle)


def run_smoke(adapter, model_id):
    if adapter == "codex_cli":
        cmd = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--model",
            model_id,
            "--dangerously-bypass-approvals-and-sandbox",
            CODEX_PROMPT,
        ]
    elif adapter == "claude_haiku":
        cmd = [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--permission-mode",
            "bypassPermissions",
            "--model",
            model_id,
            CLAUDE_PROMPT,
        ]
    else:
        raise RuntimeError("unsupported_adapter:%s" % adapter)
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, universal_newlines=True)
    if completed.returncode != 0:
        raise RuntimeError("exit_%s:%s" % (completed.returncode, completed.stderr.strip() or completed.stdout.strip()))
    return completed.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--models-config", default="configs/models.yaml")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    experiment = load_yaml(args.config) or {}
    registry = (load_yaml(args.models_config) or {}).get("models", {})
    include = (((experiment.get("models") or {}).get("include")) or [])

    results = []
    for model_key in include:
        entry = registry.get(model_key, {})
        adapter = entry.get("adapter")
        model_id = entry.get("model_id")
        record = {
            "model_key": model_key,
            "adapter": adapter,
            "model_id": model_id,
        }
        try:
            record["response"] = run_smoke(adapter, model_id)
            record["ok"] = True
        except Exception as exc:  # noqa: BLE001
            record["ok"] = False
            record["error"] = "%s:%s" % (type(exc).__name__, exc)
        results.append(record)

    payload = {
        "config": args.config,
        "models_config": args.models_config,
        "python": sys.version,
        "results": results,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
