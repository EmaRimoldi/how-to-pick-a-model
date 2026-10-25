"""Build an anonymous NeurIPS 2026 supplementary ZIP.

The builder is intentionally whitelist-based and non-invasive: it reads from the
development workspace and writes a clean export under ``dist/`` without touching
live campaigns, raw run directories, or git metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NAME = "neurips2026_anonymous_artifact"

TEXT_SUFFIXES = {
    ".bib",
    ".cfg",
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sh",
    ".tex",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

COMMON_EXCLUDES = {
    ".DS_Store",
    ".git",
    ".github",
    ".gitmodules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "Archive",
    "artifacts",
    "campaigns",
    "dist",
    "docs",
    "legacy",
    "paper_figures",
    "paper_overleaf",
    "runs",
    "tmp",
}

TREE_EXCLUDES = {
    "autoresearch/benchmark/cifar10/data",
    "autoresearch/scripts/make_neurips2026_artifact.py",
}

SOURCE_WHITELIST = {
    "src/vao/__init__.py",
    "src/vao/agents/__init__.py",
    "src/vao/agents/base.py",
    "src/vao/agents/autoresearch_local_stub_adapter.py",
    "src/vao/logging_utils.py",
    "src/vao/schemas.py",
    "src/vao/structured_edits.py",
    "src/vao/taxonomy.py",
}

FIGURE_WHITELIST = {
    "certified_resource_summary_unified.png",
    "deployment_mix_sensitivity.png",
    "diag_z_signal_ablation.png",
    "first_hit_ecdf_by_mode.png",
    "quality_vs_certified_resource.png",
    "router_shift_lookup_summary.png",
    "threeworker_cost_to_tau_by_mode_worker.png",
    "threeworker_crossover_applicability.png",
    "threeworker_deployment_frontier.png",
    "threeworker_frozen_confirmation_frontier.png",
    "threeworker_improvement_distribution.png",
    "threeworker_negative_controls.png",
    "threeworker_relative_improvement_trajectories.png",
    "threeworker_router_paired_gain.png",
    "threeworker_router_selection_regret.png",
    "threeworker_tau_distribution.png",
    "threeworker_threshold_sensitivity.png",
    "threeworker_worker_cost_quality_diagnostics.png",
}

PROCESSED_RESULTS = {
    "autoresearch/campaigns/h20_delta005_20260505/accounting/threeworker_n34_final_analysis.json": "results/threeworker_final_analysis.json",
}

LEAK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"erimoldi",
        r"EmaRimoldi",
        r"/home/",
        r"/Users/",
        r"/orcd/",
        r"openclaw_remote",
        r"git\.overleaf\.com",
        r"github\.com/Ema",
        r"OPENAI_API_KEY\s*=",
        r"ANTHROPIC_API_KEY\s*=",
        r"HF_TOKEN\s*=",
        r"WANDB_API_KEY\s*=",
        r"AIza[0-9A-Za-z_-]+",
        r"hf_[0-9A-Za-z_-]+",
        r"sk-[0-9A-Za-z_-]{20,}",
        r"BEGIN [A-Z ]*PRIVATE KEY",
    ]
]

REDACTIONS = [
    (re.compile(r"/home/erimoldi/openclaw_remote/projects/NeurIPS_2026"), "."),
    (re.compile(r"/orcd/home/002/erimoldi/openclaw_remote/projects/NeurIPS_2026"), "."),
    (re.compile(r"/Users/emanuelerimoldi/Documents/GitHub/NeurIPS_2026"), "."),
    (re.compile(r"https://git@git\.overleaf\.com/[0-9a-fA-F]+"), "[anonymous-overleaf-remote-removed]"),
    (re.compile(r"https://git\.overleaf\.com/[0-9a-fA-F]+"), "[anonymous-overleaf-remote-removed]"),
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def should_skip(path: Path) -> bool:
    rp = rel(path)
    parts = set(path.relative_to(ROOT).parts)
    if parts & COMMON_EXCLUDES:
        return True
    return any(rp == excluded or rp.startswith(f"{excluded}/") for excluded in TREE_EXCLUDES)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if is_text_file(src):
        text = src.read_text(encoding="utf-8", errors="replace")
        for pattern, replacement in REDACTIONS:
            text = pattern.sub(replacement, text)
        dst.write_text(text, encoding="utf-8")
    else:
        shutil.copy2(src, dst)


def copy_tree(src_rel: str, out: Path, include: Iterable[str] | None = None) -> None:
    src_root = ROOT / src_rel
    allowed = set(include) if include is not None else None
    for src in sorted(src_root.rglob("*")):
        if src.is_dir() or should_skip(src):
            continue
        rp = rel(src)
        if allowed is not None and rp not in allowed:
            continue
        copy_file(src, out / rp)


def write_readme(out: Path) -> None:
    readme = """# Anonymous NeurIPS 2026 Supplementary Code

This archive contains anonymized code, processed results, and figure
reproduction scripts for the NeurIPS 2026 submission.

## Contents

- `src/`: minimal implementation needed for the deterministic local harness.
- `autoresearch/`: CIFAR-10 edit--verify task code, prompts, configs, tests,
  and reproduction scripts.
- `results/`: processed, anonymized aggregate outputs used for paper figures.
- `figures/paper/`: paper-facing figures copied from the processed analysis.

Raw trajectories, scheduler logs, API transcripts, git history, paper-editing
metadata, execution-environment paths, and large CIFAR-10 data files are
intentionally excluded.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -e .[dev]
```

The benchmark uses CIFAR-10. The raw dataset is not bundled to keep the archive
small; standard CIFAR-10 download mechanisms in PyTorch/torchvision or a local
data mirror can be used for full training runs.

## Reproduce main figures from processed results

```bash
python autoresearch/scripts/reproduce_main_figures_from_processed.py \\
  --input results/threeworker_final_analysis.json \\
  --out-dir figures/reproduced
```

This reproduces the compact worker-frontier, router-validation, and
negative-control plots from processed aggregate data, without requiring API
access or raw agent trajectories.

## Run smoke tests

```bash
pytest -q autoresearch/tests/test_autoresearch_cifar10_task_spec.py \\
  autoresearch/tests/test_autoresearch_cifar10_local_stub.py
```

These tests exercise the task specification and deterministic local stub. Full
agentic experiments require external model APIs, wall-clock budget, and compute;
the archive therefore provides processed aggregate results for the paper figures.

## Reproducibility Notes

The paper's promoted quantitative comparison uses a fixed three-worker panel
with 34 trajectories per mode--worker cell, pooled as 10 pilot trajectories plus
24 frozen holdout trajectories. The processed JSON in `results/` contains the
aggregate frontier and router-validation quantities used to regenerate the main
figures. Raw logs are omitted because they contain provider transcripts,
execution-environment paths, and live-campaign metadata not suitable for
anonymous review.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")


def write_sanitized_pyproject(out: Path) -> None:
    pyproject = """[project]
name = "anonymous-budget-aware-orchestration"
version = "0.1.0"
description = "Anonymous artifact for budget-aware orchestration on checked agentic tasks"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2",
    "pyyaml",
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "tqdm",
    "rich",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src", "."]
include = ["vao*", "autoresearch*"]

[tool.setuptools.package-data]
autoresearch = ["benchmark/cifar10/metadata/*.json", "prompts/*.txt"]

[tool.pytest.ini_options]
testpaths = ["autoresearch/tests"]
python_files = ["test_*.py"]
pythonpath = ["src", "."]
"""
    (out / "pyproject.toml").write_text(pyproject, encoding="utf-8")


def write_helper_scripts(out: Path) -> None:
    smoke = """#!/usr/bin/env bash
set -euo pipefail
if python -m pytest --version >/dev/null 2>&1; then
  python -m pytest -q autoresearch/tests/test_autoresearch_cifar10_task_spec.py autoresearch/tests/test_autoresearch_cifar10_local_stub.py
else
  PYTHONPATH=src:. python - <<'PY'
from pathlib import Path
from autoresearch.benchmark.cifar10.task_spec import classify_edit_mode, profile_summary, single_workload_instance_overrides, validate_solution_source
from vao.agents.autoresearch_local_stub_adapter import AutoResearchLocalStubAdapter
source = Path("autoresearch/benchmark/cifar10/solution_template.py").read_text(encoding="utf-8")
summary = profile_summary("autoresearch_cifar10", single_workload_instance_overrides("mlp_flat", seed=99, max_train_steps=7))
assert summary["workload_id"] == "mlp_flat"
modified = source.replace("LEARNING_RATE = 5e-4", "LEARNING_RATE = 1e-3")
primary, secondary, details = classify_edit_mode(source, modified)
assert primary == "topk"
assert validate_solution_source("import subprocess\\n" + source)["passed"] is False
assert AutoResearchLocalStubAdapter.__name__ == "AutoResearchLocalStubAdapter"
print("fallback smoke tests passed")
PY
fi
"""
    figures = """#!/usr/bin/env bash
set -euo pipefail
python autoresearch/scripts/reproduce_main_figures_from_processed.py \
  --input results/threeworker_final_analysis.json \
  --out-dir figures/reproduced
"""
    for name, content in {
        "scripts/run_smoke_tests.sh": smoke,
        "scripts/reproduce_main_figures.sh": figures,
    }.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def copy_processed_results(out: Path) -> None:
    for src_rel, dst_rel in PROCESSED_RESULTS.items():
        src = ROOT / src_rel
        dst = out / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(src.read_text(encoding="utf-8"))
        if isinstance(data.get("router"), dict):
            data["router"]["router_path"] = "[omitted: raw router records are not included in the anonymous artifact]"
        dst.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")


def copy_figures(out: Path) -> None:
    src_dir = ROOT / "autoresearch" / "paper_figures" / "current"
    dst_dir = out / "figures" / "paper"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(FIGURE_WHITELIST):
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, dst_dir / name)


def sanitize_text(text: str) -> str:
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    text = text.replace(str(ROOT), ".")
    text = text.replace(str(ROOT / ".venv"), ".venv")
    return text


def remove_runtime_caches(out: Path) -> None:
    for path in sorted(out.rglob("__pycache__")):
        if path.is_dir():
            shutil.rmtree(path)
    for path in sorted(out.rglob("*.pyc")):
        path.unlink()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(out: Path) -> None:
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(out).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
    total_bytes = sum(item["bytes"] for item in files)
    manifest = {"files": files, "file_count": len(files), "total_bytes": total_bytes}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def scan_for_leaks(out: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in sorted(out.rglob("*")):
        if not path.is_file() or not is_text_file(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in LEAK_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        {
                            "path": path.relative_to(out).as_posix(),
                            "line": str(lineno),
                            "pattern": pattern.pattern,
                            "text": line[:240],
                        }
                    )
                    break
    return findings


def make_zip(out: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=f"{out.name}/{path.relative_to(out).as_posix()}")


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.returncode, proc.stdout


def run_smoke_tests(out: Path) -> tuple[int, str]:
    code, output = run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "autoresearch/tests/test_autoresearch_cifar10_task_spec.py",
            "autoresearch/tests/test_autoresearch_cifar10_local_stub.py",
        ],
        out,
    )
    if code == 0 or "No module named pytest" not in output:
        return code, output

    smoke = r"""
import sys
from pathlib import Path
sys.path[:0] = ["src", "."]
from autoresearch.benchmark.cifar10.task_spec import classify_edit_mode, profile_summary, single_workload_instance_overrides, validate_solution_source
source = Path("autoresearch/benchmark/cifar10/solution_template.py").read_text(encoding="utf-8")
summary = profile_summary("autoresearch_cifar10", single_workload_instance_overrides("mlp_flat", seed=99, max_train_steps=7))
assert summary["workload_id"] == "mlp_flat"
modified = source.replace("LEARNING_RATE = 5e-4", "LEARNING_RATE = 1e-3")
primary, secondary, details = classify_edit_mode(source, modified)
assert primary == "topk"
assert validate_solution_source("import subprocess\n" + source)["passed"] is False
print("fallback smoke tests passed")
"""
    return run([sys.executable, "-c", smoke], out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=f"dist/{DEFAULT_NAME}")
    parser.add_argument("--zip", default=f"dist/{DEFAULT_NAME}.zip")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    out = ROOT / args.out_dir
    zip_path = ROOT / args.zip
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    write_readme(out)
    write_sanitized_pyproject(out)
    (out / "requirements.txt").write_text(
        "\n".join(["pydantic>=2", "pyyaml", "numpy", "pandas", "matplotlib", "scipy", "tqdm", "rich", ""]) ,
        encoding="utf-8",
    )
    copy_tree("src", out, include=SOURCE_WHITELIST)
    copy_tree("autoresearch", out)
    copy_processed_results(out)
    copy_figures(out)
    write_helper_scripts(out)
    write_manifest(out)

    leaks = scan_for_leaks(out)
    (out / "SANITIZATION_REPORT.json").write_text(json.dumps({"findings": leaks}, indent=2), encoding="utf-8")
    if leaks:
        print(json.dumps({"status": "failed", "reason": "sanitization_findings", "findings": leaks[:20]}, indent=2))
        sys.exit(2)

    tests: dict[str, object] = {"skipped": bool(args.skip_tests)}
    if not args.skip_tests:
        code, output = run_smoke_tests(out)
        tests = {"exit_code": code, "output": sanitize_text(output[-4000:])}
        if code != 0:
            (out / "TEST_REPORT.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")
            print(json.dumps({"status": "failed", "reason": "tests_failed", "tests": tests}, indent=2))
            sys.exit(code)

        code, output = run(
            [
                sys.executable,
                "autoresearch/scripts/reproduce_main_figures_from_processed.py",
                "--input",
                "results/threeworker_final_analysis.json",
                "--out-dir",
                "figures/reproduced",
            ],
            out,
        )
        tests["figure_reproduction"] = {"exit_code": code, "output": sanitize_text(output[-4000:])}
        if code != 0:
            (out / "TEST_REPORT.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")
            print(json.dumps({"status": "failed", "reason": "figure_reproduction_failed", "tests": tests}, indent=2))
            sys.exit(code)

    (out / "TEST_REPORT.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")
    remove_runtime_caches(out)
    write_manifest(out)
    leaks = scan_for_leaks(out)
    (out / "SANITIZATION_REPORT.json").write_text(json.dumps({"findings": leaks}, indent=2), encoding="utf-8")
    if leaks:
        print(json.dumps({"status": "failed", "reason": "post_test_sanitization_findings", "findings": leaks[:20]}, indent=2))
        sys.exit(2)
    make_zip(out, zip_path)
    size = zip_path.stat().st_size
    print(
        json.dumps(
            {
                "status": "ok",
                "artifact_dir": str(out.relative_to(ROOT)),
                "zip": str(zip_path.relative_to(ROOT)),
                "zip_bytes": size,
                "zip_mb": round(size / (1024 * 1024), 3),
                "under_100mb": size < 100 * 1024 * 1024,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
